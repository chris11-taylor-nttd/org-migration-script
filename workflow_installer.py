
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
from github.Repository import Repository
from github.Organization import Organization
from github.GithubException import UnknownObjectException

from git.repo import Repo
from git.remote import Remote
from git import Commit

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s",
    datefmt="%F %T %Z",
)
logger = logging.getLogger("tag_bumper")
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

ORG = "launchbynttdata"

TEMPLATES_ROOT = pathlib.Path.cwd().joinpath("templates")

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
        source_org = ORG
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


def tags_to_semantic_versions(repository: Repo) -> list[Version]:
    versions = []
    for tag in repository.tags:
        try:
            versions.append(Version.parse(tag.name))
        except Exception as e:
            logger.warning(f"Couldn't parse tag {tag} as a semantic version: {e}")
    return versions


def get_main_commit(repo: Repo) -> Commit:
    return repo.branches['main'].object

def get_tag_commit(repo: Repo, tag_name: str) -> Commit:
    return repo.tags[tag_name].commit

def latest_version(versions: list[Version]) -> Version:
    return max(versions)

def get_org_repositories(organization: Organization, name_filter: str = "") -> list[Repository]:
    all_repos = [r for r in organization.get_repos()]
    return [r for r in all_repos if name_filter in r.name]

def move_tag_forward(repo: Repo, tag_name: str) -> None:
    repo.git.tag("-d", tag_name)
    repo.git.tag(tag_name)
    repo.git.push("origin", tag_name, "-f")

def install_workflow(repo: Repo) -> bool:
    repo_root = pathlib.Path(repo.working_dir)
    workflow_path_relative = ".github/workflows"
    repo_root.joinpath(workflow_path_relative).mkdir(exist_ok=True, parents=True)
    workflow_dir = repo_root.joinpath(workflow_path_relative)
    if workflow_dir.joinpath("lint-terraform.yaml").exists():
        return False
    shutil.copy(src=TEMPLATES_ROOT.joinpath(workflow_path_relative).joinpath("lint-terraform.yaml"), dst=workflow_dir.joinpath("lint-terraform.yaml"))
    return True


def add_commit_retag_push(repo: Repo, latest_tag_name: str):
    repo.git.add(all=True)
    repo.git.commit("-m", "Automation: add lint-terraform workflow")
    repo.git.tag("-d", latest_tag_name)
    repo.git.tag(latest_tag_name)
    repo.git.push("origin", "main", "-f")
    repo.git.push("origin", latest_tag_name, "-f")

def main() -> int:
    work_dir = create_work_dir()

    try:
        github_object = get_github_instance(token_suffix=ORG)
    except Exception as e:
        logger.exception("Failed to retrieve Github instance!")
        return -1
    
    try:
        all_repositories = get_org_repositories(organization=github_object.get_organization(login=ORG), name_filter="tf-")
    except Exception as e:
        logger.exception("Failed to retrieve Github Repositories!")
        return -2 

    outcomes = []
    for repository in all_repositories:
        try:
            source_repo_object = clone_source_repository(
                source_repo_name=repository.name, work_dir=work_dir
            )
            if not 'main' in source_repo_object.branches:
                outcomes.append(f"{repository.name} has no main branch, no action will be taken!")
                continue

            latest_tag = latest_version(tags_to_semantic_versions(source_repo_object))
            if install_workflow(repo=source_repo_object):
                add_commit_retag_push(repo=source_repo_object, latest_tag_name=str(latest_tag))
        except Exception as e:
            outcomes.append(f"EXCEPTION for {repository.name}: {e}")

    print("\n".join(outcomes))

if __name__ == "__main__":
    result = main()
    exit(code=result)
