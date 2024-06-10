import os
import itertools

from github import Github, Auth
from github.Organization import Organization
from github.PullRequest import PullRequest

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


def org_outstanding_pull_requests(
        organization: Organization, 
        repo_name_partial: str | None = "",
        user_login_partial: str | None = ""
    ) -> list[PullRequest]:
    repositories = [repo for repo in organization.get_repos() if repo_name_partial in repo.name]
    pull_requests: list[PullRequest] = itertools.chain.from_iterable([repo.get_pulls(state="open") for repo in repositories])
    filtered_by_user = [pull_request for pull_request in pull_requests if user_login_partial in pull_request.user.login]
    return filtered_by_user


def display(pull_requests: list[PullRequest]):
    for pr in pull_requests:
        print(f"{pr.user.login} - {pr.html_url}")


display(
    org_outstanding_pull_requests(
        organization=get_github_instance(token_suffix="launchbynttdata").get_organization("launchbynttdata"),
        repo_name_partial="",
        user_login_partial=""
    )
)