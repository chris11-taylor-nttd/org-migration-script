import pathlib
import sys
import logging
import os
import itertools
import shutil
import re
import subprocess
from typing import Callable
import json

from semver import Version
from github import Auth, Github
from github.GithubException import UnknownObjectException

from git.repo import Repo
from git.remote import Remote

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s",
    datefmt="%F %T %Z",
)
logger = logging.getLogger("migration")
logging.getLogger("git").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)

DISCOVERY_FORBIDDEN_DIRECTORIES = [
    ".git",
    "components",
    ".repo",
    "__pycache__",
    ".venv",
    ".terraform",
    ".terragrunt-cache",
]

SOURCE_ORG = "nexient-llc"
DESTINATION_ORG = "launchbynttdata"
MIGRATION_COMMIT_MESSAGE = "Migrate repository from old GitHub organization."

REPLACEMENTS = {
    "nexient-llc": "launchbynttdata",
    "CAF_ENV_FILE = .cafenv": "LCAF_ENV_FILE = .lcafenv",
    "-include $(CAF_ENV_FILE)": "-include $(LCAF_ENV_FILE)",
    "REPO_BRANCH ?= main": "REPO_BRANCH ?= refs/tags/1.0.0",
    ".cafenv": ".lcafenv",
    "lcaf-component-tf-module": "lcaf-component-terraform",
    "lcaf-component-terratest-common": "lcaf-component-terratest",
    "tf-module-skeleton": "lcaf-skeleton-terraform",
    "launch-terragrunt-skeleton": "lcaf-skeleton-terragrunt",
    "lcaf-component-aws-pipelines": "lcaf-component-provider_aws-pipeline_aws",
    "tf-module-resource_name": "tf-launch-module_library-resource_name",
    "tf-azurerm-module-resource_group": "tf-azurerm-module_primitive-resource_group",
    "tf-azureado-module_ref-pipeline": "tf-azureado-module_reference-pipeline",
    # Azure Module Renames
    "tf-azurerm_module-network_manager_admin_rule_collection": "tf-azurerm-module_primitive-network_manager_admin_rule_collection",
    "tf-azurerm_module-network_manager_admin_rule": "tf-azurerm-module_primitive-network_manager_admin_rule",
    "tf-azurerm_module-network_manager_security_admin_configuration": "tf-azurerm-module_primitive-network_manager_security_admin_configuration",
    "tf-azurerm-collection_module-network_group": "tf-azurerm-module_collection-network_group",
    "tf-azurerm-collection_module-network_manager": "tf-azurerm-module_collection-network_manager",
    "tf-azurerm-module_ref-kubernetes_cluster": "tf-azurerm-module_reference-kubernetes_cluster",
    "tf-azurerm-module-dns_zone_record": "tf-azurerm-module_primitive-dns_zone_record",
    "tf-azurerm-module-network_interface_security_group_association": "tf-azurerm-module_primitive-network_interface_security_group_association",
    "tf-azurerm-module-network_interface": "tf-azurerm-module_primitive-network_interface",
    "tf-azurerm-module-network_security_group": "tf-azurerm-module_primitive-network_security_group",
    "tf-azurerm-module-network_security_rule": "tf-azurerm-module_primitive-network_security_rule",
    "tf-azurerm-module-public_ip": "tf-azurerm-module_primitive-public_ip",
    "tf-azurerm-module-role_assignment": "tf-azurerm-module_primitive-role_assignment",
    "tf-azurerm-module-subnet_network_security_group_association": "tf-azurerm-module_primitive-subnet_network_security_group_association",
    "tf-azurerm-module-virtual_machine_extension": "tf-azurerm-module_primitive-virtual_machine_extension",
    "tf-azurerm-module-windows_virtual_machine": "tf-azurerm-module_primitive-windows_virtual_machine",
    "tf-azurerm-wrapper_module-application_gateway": "tf-azurerm-module_collection-application_gateway",
    "tf-azurerm-wrapper_module-frontend": "tf-azurerm-module_collection-frontend",
    "tf-azurerm-wrapper_module-kubernetes_cluster": "tf-azurerm-module_collection-kubernetes_cluster",
    "tf-azurerm-wrapper_module-security_group": "tf-azurerm-module_collection-security_group",
    "tf-azurerm-wrapper_module-windows_virtual_machine": "tf-azurerm-module_collection-windows_virtual_machine",
    "tf-caf-terratest-common": "lcaf-component-terratest",
    "caf-component-terratest-common": "caf-component-terratest",
    "v0.0.0-20230828171431-63fb3d474745": "v1.0.4",
    "v0.0.0-20240117163707-a1dfafae58b4": "v1.0.4",
    "caf-component-terratest v1.0.1": "caf-component-terratest v1.0.4",
    "caf-component-terratest v1.0.2": "caf-component-terratest v1.0.4",
    "tf-azurerm-module-key_vault": "tf-azurerm-module_primitive-key_vault",
    # AWS Module Renames
    "tf-aws-wrapper_module-s3_bucket": "tf-aws-module_collection-s3_bucket",
    "tf-aws-wrapper_module-codebuild": "tf-aws-module_collection-codebuild",
    "tf-aws-module-acm_private_cert": "tf-aws-module_primitive-acm_private_cert",
    "tf-aws-module-appmesh": "tf-aws-module_primitive-appmesh",
    "tf-aws-module-appmesh_gateway_route": "tf-aws-module_primitive-appmesh_gateway_route",
    "tf-aws-module-appmesh_route": "tf-aws-module_primitive-appmesh_route",
    "tf-aws-module-appmesh_virtual_gateway": "tf-aws-module_primitive-virtual_gateway",
    "tf-aws-module-appmesh_virtual_node": "tf-aws-module_primitive-virtual_node",
    "tf-aws-module-appmesh_virtual_router": "tf-aws-module_primitive-virtual_router",
    "tf-aws-module-appmesh_virtual_service": "tf-aws-module_primitive-virtual_service",
    "tf-aws-module-autoscaling_policy": "tf-aws-module_primitive-autoscaling_policy",
    "tf-aws-module-autoscaling_target": "tf-aws-module_primitive-autoscaling_target",
    "tf-aws-module-cloudwatch_log_stream": "tf-aws-module_primitive-cloudwatch_log_stream",
    "tf-aws-module-cloudwatch_log_group": "tf-aws-module_primitive-cloudwatch_log_group",
    "tf-aws-module-cloudwatch_log_subscription_filter": "tf-aws-module_primitive-cloudwatch_subscription_filter",
    "tf-aws-module-cloudwatch_metric_stream": "tf-aws-module_primitive-cloudwatch_metric_stream",
    "tf-aws-module-codeartifact_domain": "tf-aws-module_primitive-codeartifact_domain",
    "tf-aws-module-codeartifact_repository": "tf-aws-module_primitive-codeartifact_repository",
    "tf-aws-module-codepipeline": "tf-aws-module_primitive-codepipeline",
    "tf-aws-module-firehose_delivery_stream": "tf-aws-module_primitive-firehose_delivery_stream",
    "tf-aws-module-private_ca": "tf-aws-module_primitive-private_ca",
    "tf-aws-module-private_dns_namespace": "tf-aws-module_primitive-private_dns_namespace",
    "tf-aws-module-service_discovery_service": "tf-aws-module_primitive-service_discovery_service",
    "tf-aws-module-ssm_parameter": "tf-aws-module_primitive-ssm_parameter",
    "tf-aws-module-wafv2_web_acl_association": "tf-aws-module_primitive-wafv2_web_acl_association",
    "tf-aws-wrapper_module-bulk_lambda_function": "tf-aws-module_collection-bulk_lambda_function",
    "tf-aws-wrapper_module-cloudwatch_logs": "tf-aws-module_collection-cloudwatch_logs",
    "tf-aws-wrapper_module-codepipelines": "tf-aws-module_collection-codepipeline",
    "tf-aws-module_primitive-dns_record": "tf-aws-module_primitive-dns_record",
    "tf-aws-module_primitive-dns_zone": "tf-aws-module_primitive-dns_zone",
    "tf-aws-wrapper_module-ecs_appmesh_app": "tf-aws-module_collection-ecs_appmesh_app",
    "tf-aws-wrapper_module-ecs_appmesh_ingress": "tf-aws-module_collection-ecs_appmesh_ingress",
    "tf-aws-wrapper_module-ecs_appmesh_platform": "tf-aws-module_collection-ecs_appmesh_platform",
    "tf-aws-wrapper_module-ecs_platform": "tf-aws-module_collection-ecs_platform",
    "tf-aws-wrapper_module-iam_assumable_role": "tf-aws-module_collection-iam_assumable_role",
    "tf-aws-wrapper_module-iam_policy": "tf-aws-module_collection-iam_policy",
    "tf-aws-wrapper_module-lambda_function": "tf-aws-module_collection-lambda_function",
    "tf-aws-wrapper_module-load_balancer": "tf-aws-module_collection-load_balancer",
    "tf-aws-wrapper_module-memcached_cluster": "tf-aws-module_collection-memcached_cluster",
    "tf-aws-wrapper_module-sns": "tf-aws-module_collection-sns",
    "tf-aws-wrapper_module-sumo_telemetry_shipper": "tf-aws-module_collection-sumo_telemetry_shipper",
    "tf-aws-wrapper_module-sumologic_observability": "tf-aws-module_reference-sumologic_observability",
    "tf-aws-wrapper_module-activemq_broker": "tf-aws-module_collection-activemq_broker",
    "tf-aws-wrapper_module-ecs_app": "tf-aws-module_collection-ecs_app",
    "tf-aws-wrapper_module-remote_dev_instance": "tf-aws-module_collection-remote_dev_instance",
    "tf-aws-wrapper_module-lambda_layer": "tf-aws-module_collection-lambda_layer",
    "tf-aws-wrapper_module-lambda_application": "tf-aws-module_collection-lambda_application"
}

REGULAR_EXPRESSIONS = {
    "go_mod_go_version": re.compile(r"^go \d\.\d+$"),
    "tf_git_reference": re.compile(r"ref=([\w\d\./_-]+)"),
}


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


def create_work_dir(root_path: pathlib.Path = pathlib.Path.cwd()) -> pathlib.Path:
    work_dir = root_path.joinpath("work")
    work_dir.mkdir(exist_ok=True)
    logger.info(f"Using working directory {work_dir}")
    return work_dir


def clone_source_repository(source_repo_name: str, work_dir: pathlib.Path, source_org: str|None = None) -> Repo:
    if not source_org: 
        source_org = SOURCE_ORG
    token = read_github_token(source_org)
    source_repo_url = f"https://{token}:x-oauth-basic@github.com/{source_org}/{source_repo_name}.git"
    source_repo_path = work_dir.joinpath(source_repo_name)
    if source_repo_path.exists():
        logger.error(
            f"Path {source_repo_path} already exists, deleting prior to clone!"
        )
        shutil.rmtree(path=source_repo_path)
    logger.info(f"Cloning https://github.com/{source_org}/{source_repo_name}.git to {source_repo_path}")
    return Repo.clone_from(url=source_repo_url, to_path=source_repo_path)


def source_repo_object(source_repo_path: pathlib.Path) -> Repo:
    return Repo(path=source_repo_path)


def load_repo_rename_map() -> dict[str, str]:
    return json.loads(pathlib.Path("nexient-llc-repos-rename-map.json").read_text())


def destination_repo_exists_remotely(g: Github, destination_repo: str) -> None:
    full_name = f"{DESTINATION_ORG}/{destination_repo}"
    try:
        destination_repo = g.get_repo(full_name_or_id=full_name)
    except UnknownObjectException as uoe:
        raise RuntimeError(
            f"Destination repo {full_name} does not exist in GitHub yet! Repo must be created in a blank state to migrate."
        ) from uoe
    main_branch_exists = "main" in [
        branch.name for branch in destination_repo.get_branches()
    ]
    if main_branch_exists:
        raise RuntimeError(
            f"Destination repo {full_name} exists but already has a `main` branch and is unsuitable for migration!"
        )


def discover_files(
    root_path: pathlib.Path,
    filename_partial: str = "",
    forbidden_directories: list[str] = None,
) -> list[pathlib.Path]:
    """Recursively discovers files underneath a top level root_path that match a partial name.

    Args:
        root_path (pathlib.Path): Top level directory to search
        filename_partial (str, optional): Case-insensitive part of the filename to search. Defaults to "", which will return all files. This partial search uses an 'in' expression, do not use a wildcard.
        forbidden_directories (list[str], optional): List of strings to match in directory names that will not be traversed. Defaults to None, which forbids traversal of some common directories (.git, .terraform, etc.). To search all directories, pass an empty list.

    Returns:
        list[pathlib.Path]: List of pathlib.Path objects for files matching filename_partial.
    """
    if forbidden_directories is None:
        forbidden_directories = DISCOVERY_FORBIDDEN_DIRECTORIES

    directories = [
        d
        for d in root_path.iterdir()
        if d.is_dir() and not d.name.lower() in forbidden_directories
    ]
    files = [
        f
        for f in root_path.iterdir()
        if not f.is_dir() and filename_partial in f.name.lower()
    ]
    files.extend(
        list(
            itertools.chain.from_iterable(
                [
                    discover_files(
                        root_path=d,
                        filename_partial=filename_partial,
                        forbidden_directories=forbidden_directories,
                    )
                    for d in directories
                ]
            )
        )
    )
    return files


def delete_if_present(file_path: pathlib.Path):
    if file_path.exists():
        logger.info(f"Deleting {file_path}")
        file_path.unlink()


def static_replacements(source_repo: Repo):
    template_path = pathlib.Path.cwd().joinpath("templates")
    destination_path = pathlib.Path(source_repo.working_dir)

    def install_workflows():
        workflow_path_relative = ".github/workflows"
        template_workflow_path = template_path.joinpath(workflow_path_relative)
        repo_workflow_path = destination_path.joinpath(workflow_path_relative)
        shutil.copytree(src=template_workflow_path, dst=repo_workflow_path, dirs_exist_ok=True)

    def replace_static(filename: str):
        src = template_path.joinpath(filename)
        dst = destination_path.joinpath(filename)
        logger.info(
            f"Replacing {dst.relative_to(destination_path.parent)} with {src.relative_to(template_path.parent)}"
        )
        shutil.copy(src=src, dst=dst)

    replace_static(".gitignore")
    replace_static(".lcafenv")
    replace_static(".secrets.baseline")
    replace_static(".tool-versions")
    replace_static("CODEOWNERS")
    replace_static("Makefile")
    replace_static("NOTICE")

    delete_if_present(file_path=destination_path.joinpath("commitlint.config.js"))
    delete_if_present(file_path=destination_path.joinpath("test.tfvars"))
    delete_if_present(file_path=destination_path.joinpath("example.tfvars"))
    delete_if_present(file_path=destination_path.joinpath("tests/test.tfvars"))

    install_workflows()


def dynamic_replacements(source_repo: Repo):
    source_repo_path = pathlib.Path(source_repo.working_dir)

    def repo_find_replace(
        top_level_directory: pathlib.Path, replacements: dict[str, str]
    ) -> bool:
        should_tidy = False
        all_files = discover_files(root_path=top_level_directory)
        logger.info(f"About to perform a find/replace on {len(all_files)} files.")
        for file_path in all_files:
            performed_replace = file_find_replace(
                file_path=file_path, replacements=replacements
            )
            if performed_replace and (
                file_path.name in ["go.mod", "go.sum"] or ".go" in file_path.name
            ):
                should_tidy = True
        return should_tidy

    def update_terraform_tag_references(top_level_directory: pathlib.Path):
        def version_replacer(input: re.Match) -> str:
            return "ref=1.0.0"

        tf_main_files = discover_files(
            root_path=top_level_directory, filename_partial="main.tf"
        )
        for tf_main_file in tf_main_files:
            logger.info(
                f"Discovered main.tf file at {tf_main_file.relative_to(top_level_directory)}, performing version updates."
            )
            tf_main_contents = tf_main_file.read_text()
            new_contents = re.sub(
                pattern=REGULAR_EXPRESSIONS["tf_git_reference"],
                repl=version_replacer,
                string=tf_main_contents,
            )
            tf_main_file.write_text(new_contents)

    def file_find_replace(
        file_path: pathlib.Path, replacements: dict[str, str]
    ) -> bool:
        try:
            write = False
            contents = file_path.read_text()
            lines = contents.splitlines()
            for line_number, line in enumerate(lines):
                for find_value, replace_value in replacements.items():
                    if find_value in line:
                        write = True
                        logger.info(
                            f"{file_path.relative_to(source_repo_path)}:{line_number+1}: Found '{find_value}', replacing with '{replace_value}'"
                        )
                        lines[line_number] = lines[line_number].replace(
                            find_value, replace_value
                        )
            if write:
                reconstituted_lines = "\n".join(lines) + "\n"
                new_size = file_path.write_text(reconstituted_lines)
                logger.info(
                    f"Wrote {new_size} bytes to {file_path.relative_to(source_repo_path)}"
                )
                return True
            else:
                logger.debug(
                    f"{file_path.relative_to(source_repo_path)} did not contain any find/replace values."
                )
                return False
        except UnicodeDecodeError:
            logger.warning(
                f"Cannot find/replace on binary file {file_path.relative_to(source_repo_path)}"
            )
            return False

    def update_go_mod_module_git(top_level_directory: pathlib.Path) -> bool:
        go_mod_file = top_level_directory.joinpath("go.mod")
        go_mod_contents = go_mod_file.read_text()
        go_mod_lines = go_mod_contents.splitlines()
        if ".git" in go_mod_lines[0]:
            go_mod_lines[0].replace(".git", "")
            go_mod_file.write_text("\n".join(go_mod_lines) + "\n")
            return True
        return False

    def update_go_mod_go_version(top_level_directory: pathlib.Path) -> bool:
        go_mod_file = top_level_directory.joinpath("go.mod")
        go_mod_contents = go_mod_file.read_text()
        go_mod_contents_updated = re.sub(
            pattern=REGULAR_EXPRESSIONS["go_mod_go_version"],
            repl="go 1.21",
            string=go_mod_contents,
        )
        if go_mod_contents != go_mod_contents_updated:
            go_mod_file.write_text(go_mod_contents_updated)
            return True
        return False

    should_tidy = repo_find_replace(
        top_level_directory=source_repo_path, replacements=REPLACEMENTS
    )
    updated_go_module = update_go_mod_module_git(top_level_directory=source_repo_path)
    updated_go_version = update_go_mod_go_version(top_level_directory=source_repo_path)
    update_terraform_tag_references(top_level_directory=source_repo_path)

    if updated_go_module or updated_go_version or should_tidy:
        delete_if_present(file_path=source_repo_path.joinpath("go.sum"))
        go_mod_tidy_result = block_for_user_input_with_bypass(
            message="Executing `go mod tidy`",
            retry_function=shell_command,
            command=["go", "mod", "tidy"],
            source_repo=source_repo,
            raise_on_failure=True,
        )
        if go_mod_tidy_result == -999:
            logger.error("User aborted!")
            raise RuntimeError(f"User aborted!")


def shell_command(
    source_repo: Repo, command: list[str], raise_on_failure: bool = False, bypass: bool = False
) -> int:
    repo_root = pathlib.Path(source_repo.working_dir)
    
    command_display = " ".join(command)
    if bypass:
        logger.debug(f"Bypassing {command_display}")
        return 0
    logger.info(f"About to run {command_display} in {repo_root}...")
    outcome = subprocess.run(
        command, cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if outcome.returncode == 0:
        logger.info(f"Successfully ran {command_display}")
    else:
        logger.error(
            f"Failed to run {command_display}; return code {outcome.returncode}"
        )
        logger.error(outcome.stdout.decode("utf-8"))
        logger.error(outcome.stderr.decode("utf-8"))
        if raise_on_failure:
            raise RuntimeError(
                f"Failed to run {command_display}; return code {outcome.returncode}"
            )
    return outcome.returncode


def add_remote(source_repo: Repo, destination_repo_name: str) -> None:
    destination_repo_url = (
        f"https://github.com/launchbynttdata/{destination_repo_name}.git"
    )
    expected_remote = Remote(name="migration_target", repo=destination_repo_url)
    if not expected_remote in source_repo.remotes:
        source_repo.create_remote(name="migration_target", url=destination_repo_url)
        logger.info(f"Added migration_target remote for {destination_repo_url}")


def add_and_commit(source_repo: Repo, commit_message: str | None = None, bypass: bool = False, **kwargs):
    if not commit_message:
        commit_message = MIGRATION_COMMIT_MESSAGE
    source_repo.git.add(all=True)
    if bypass:
        source_repo.git.commit("-m", f"'{commit_message}'", "--no-verify")
    else:
        source_repo.git.commit("-m", f"'{commit_message}'")


def tags_to_semantic_versions(repository: Repo) -> list[Version]:
    versions = []
    for tag in repository.tags:
        try:
            versions.append(Version.parse(tag.name))
        except Exception as e:
            logger.warning(f"Couldn't parse tag {tag} as a semantic version: {e}")
    return versions


def latest_version(versions: list[Version]) -> Version:
    return max(versions)


def push_main_migration(source_repo: Repo, **kwargs) -> None:
    source_repo.git.push(["migration_target", "main", "-f"])
    existing_tags = tags_to_semantic_versions(repository=source_repo)
    if existing_tags:
        most_recent_tag = latest_version(existing_tags)
    else:
        most_recent_tag = Version(0,0,0)
    new_version = str(most_recent_tag.bump_major())
    logger.info(f"New tag will be {new_version}")
    source_repo.git.tag([new_version])
    source_repo.git.push(["migration_target", new_version])
    logger.info(f"Pushed tag {new_version} to remote")


def block_for_user_input(
    message: str, retry_function: Callable, *args, **kwargs
) -> int:
    user_choice = None
    try:
        logger.info(message)
        retry_function(*args, **kwargs)
        logger.info("Success!")
        return 0
    except Exception as e:
        logger.exception(
            f"Failure when calling {retry_function}. This operation can be retried!"
        )
        while user_choice not in ["retry", "abort"]:
            user_choice = input("Please enter 'abort' or 'retry': ").lower().strip()

        if user_choice == "abort":
            logger.error("User aborted!")
            return -999
        return block_for_user_input(
            message=message, retry_function=retry_function, *args, **kwargs
        )


def block_for_user_input_with_bypass(
    message: str, retry_function: Callable, *args, **kwargs
) -> int:
    user_choice = None
    try:
        logger.info(message)
        retry_function(*args, **kwargs)
        logger.info("Success!")
        return 0
    except Exception as e:
        logger.exception(
            f"Failure when calling {retry_function}. This operation can be retried or bypassed!"
        )
        while user_choice not in ["retry", "abort", "bypass"]:
            user_choice = (
                input("Please enter 'abort', 'retry', or 'bypass': ").lower().strip()
            )
        if user_choice == "abort":
            return -999
        elif user_choice == "bypass":
            kwargs["bypass"] = True
        return block_for_user_input(
            message=message, retry_function=retry_function, *args, **kwargs
        )


def archive_repo(g: Github, org_name: str, repo_name: str):
    repo_full_name = f"{org_name}/{repo_name}"
    repo = g.get_repo(full_name_or_id=repo_full_name)
    logger.info(f"Setting archived = True for {repo_full_name}")
    repo.edit(archived=True)


def main(source_repo_name: str, destination_repo_name: str = None) -> int:
    work_dir = create_work_dir()

    try:
        github_source = get_github_instance(token_suffix="nexient-llc")
        github_destination = get_github_instance(token_suffix="launchbynttdata")
    except Exception as e:
        logger.exception("Failed to retrieve Github instance!")
        return -1

    if not destination_repo_name:
        repo_rename_map = load_repo_rename_map()
        if source_repo_name in repo_rename_map:
            destination_repo_name = repo_rename_map[source_repo_name]
        else:
            destination_repo_name = source_repo_name
    
    source_repo_is_archived = github_source.get_repo(full_name_or_id=f"{SOURCE_ORG}/{source_repo_name}").archived

    if source_repo_is_archived:
        logger.error(f"{SOURCE_ORG}/{source_repo_name} is marked as Archived and will not be migrated again!")
        return 1

    try:
        source_repo_object = clone_source_repository(
            source_repo_name=source_repo_name, work_dir=work_dir
        )
        destination_repo_exists_remotely(
            g=github_destination, destination_repo=destination_repo_name
        )
    except Exception as e:
        logger.exception(
            "Failed to initialize migration: repos are not in the correct state to migrate!"
        )
        return -2

    logger.info(
        f"Migrating {SOURCE_ORG}/{source_repo_name} to {DESTINATION_ORG}/{destination_repo_name}"
    )

    try:
        static_replacements(source_repo=source_repo_object)
    except:
        logger.exception("Failed to perform static replacements on your repo!")
        return -4

    make_configure_result = block_for_user_input(
        message="Executing `make configure`",
        retry_function=shell_command,
        command=["make", "configure"],
        source_repo=source_repo_object,
        raise_on_failure=True,
    )

    if make_configure_result == -999:
        logger.error("User aborted!")
        return make_configure_result

    try:
        dynamic_replacements(source_repo=source_repo_object)
    except:
        logger.exception("Failed to perform dynamic replacements on your repo!")
        return -5

    add_commit_result = block_for_user_input_with_bypass(
        message="Adding changes and committing",
        retry_function=add_and_commit,
        source_repo=source_repo_object,
        raise_on_failure=True,
    )

    if add_commit_result == -999:
        logger.error("User aborted!")
        return add_commit_result

    try:
        add_remote(
            source_repo=source_repo_object, destination_repo_name=destination_repo_name
        )
    except Exception as e:
        logger.exception(f"Failed to add a remote to the local repository!")
        return -7

    push_main_result = block_for_user_input(
        message=f"Pushing updated repository to {DESTINATION_ORG}/{destination_repo_name}",
        retry_function=push_main_migration,
        source_repo=source_repo_object,
        raise_on_failure=True,
    )

    if push_main_result == -999:
        logger.error("User aborted!")
        return push_main_result

    archive_repo(g=github_source, org_name=SOURCE_ORG, repo_name=source_repo_name)

    logger.info(
        f"Migration complete! Repo is now available at {DESTINATION_ORG}/{destination_repo_name}"
    )


if __name__ == "__main__":
    source_repo = sys.argv[1]
    try:
        destination_repo = sys.argv[2]
    except:
        destination_repo = None
    result = main(source_repo_name=source_repo, destination_repo_name=destination_repo)
    exit(code=result)
