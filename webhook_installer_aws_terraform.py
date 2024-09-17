import os
import sys

import boto3
from github import Auth, Github


LAMBDA_FUNCTION_PREFIX = "pipe-shared"
SHARED_SECRET_ARN = "arn:aws:secretsmanager:us-east-2:538234414982:secret:github/launchbynttdata/tg-aws-shared-terraform_pipeline20240916213312998700000001"

session = boto3.Session(profile_name='launch-root-admin')

lambda_client = session.client('lambda')
secretsmanager_client = session.client('secretsmanager')

def read_github_token(token_suffix: str | None = None) -> str:
    env_var_name = "GITHUB_TOKEN"
    if token_suffix:
        env_var_name += f"_{token_suffix.replace('-', '_')}"
    try:
        return os.environ[env_var_name]
    except KeyError:
        raise RuntimeError(
            f"ERROR: The {env_var_name} environment variable is not set. You must set this environment variable with the contents of your GitHub Personal Access Token (PAT) to use this script."
        )

def github_headers(token_suffix: str | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {read_github_token(token_suffix=token_suffix)}"}

def get_github_instance(
    token: str | None = None, token_suffix: str | None = None
) -> Github:
    if not token:
        token = read_github_token(token_suffix=token_suffix)
    auth = Auth.Token(token)
    return Github(auth=auth)


def find_lambda_functions_by_prefix(prefix: str|None = None) -> list[dict]:
    if prefix is None:
        prefix = LAMBDA_FUNCTION_PREFIX
    found = []
    marker = None
    end = False

    while not end:
        if marker:
            functions = lambda_client.list_functions(Marker=marker)
        else:
            functions = lambda_client.list_functions()
        
        for f in functions['Functions']:
            if f['FunctionName'].startswith(prefix):
                found.append(f)

        if 'NextMarker' in functions:
            marker = functions["NextMarker"]
        else:
            end = True
    return found

def get_function_url(function_name: str) -> str:
    response = lambda_client.get_function_url_config(FunctionName=function_name)
    return response['FunctionUrl']

def get_shared_secret():
    response = secretsmanager_client.get_secret_value(SecretId=SHARED_SECRET_ARN)
    return response['SecretString']

def configure_webhooks(repo_name: str, function_urls: list[str], shared_secret: str):
    g = get_github_instance()
    repo = g.get_repo(f"launchbynttdata/{repo_name}")
    existing_hooks = [hook for hook in repo.get_hooks()]
    if len(existing_hooks) > 0:
        print("Webhooks already exist for this repository. Exiting.")
        exit(2)

    webhook_definitions = [{
        "name": "web",
        "active": True,
        "events": ["pull_request"],
        "config": {
            "url": url,
            "content_type": "json",
            "secret": shared_secret,
            "insecure_ssl": "0"
        }
    } for url in function_urls]
    for definition in webhook_definitions:
        repo.create_hook(**definition)
        print(f"Created webhook for {definition['config']['url']}")

def usage(exit_code: int = 0):
    print("""Configures webhooks for a given repository to trigger the shared AWS Terraform pipeline.

Usage: python webhook_installer_aws_terraform.py <repo_name>
            
    Where <repo_name> is the name of the repository for which you want to configure webhooks. The repository name must begin with 'tf-aws-'.
""")
    exit(exit_code)

if __name__ == "__main__":
    if len(sys.argv) == 2:
        repo_name = sys.argv[1]
        if repo_name == "--help":
            usage(0)
    else:
        usage(1)
    
    if not repo_name.startswith("tf-aws-"):
        print("This tool can only configure webhooks for the shared AWS Terraform pipeline; your repo name must begin with 'tf-aws-'. Exiting.")
        exit(1)

    function_urls = [get_function_url(f['FunctionName']) for f in find_lambda_functions_by_prefix()]
    shared_secret = get_shared_secret()

    configure_webhooks(repo_name, function_urls, shared_secret)
    print("Done.")