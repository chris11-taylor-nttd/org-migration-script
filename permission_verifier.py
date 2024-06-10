import sys
from migrate_repo import get_github_instance, clone_source_repository, discover_files
import pathlib
import logging

from github import Github
from github.Repository import Repository
from github.Organization import Organization


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s",
    datefmt="%F %T %Z",
)
logger = logging.getLogger("workflow_installer")
logging.getLogger("git").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)

ORG = "launchbynttdata"

def get_org_repositories(organization: Organization, name_filter: str = "") -> list[Repository]:
    all_repos = [r for r in organization.get_repos()]
    return [r for r in all_repos if name_filter in r.name]


def create_work_dir(root_path: pathlib.Path = pathlib.Path.cwd()) -> pathlib.Path:
    work_dir = root_path.joinpath("work")
    work_dir.mkdir(exist_ok=True)
    logger.info(f"Using working directory {work_dir}")
    return work_dir


def fix_permissions(github_object: Github, repository: Repository, organization: Organization) -> None:
    platform_team = organization.get_team_by_slug("platform-team")
    platform_administrators = organization.get_team_by_slug("platform-administrators")

    platform_team.update_team_repository(repo=repository, permission="maintain")
    platform_administrators.update_team_repository(repo=repository, permission="admin")

    if repository.name.startswith("tf-"):
        terraform_administrators = organization.get_team_by_slug("terraform-administrators")
        terraform_administrators.update_team_repository(repo=repository, permission="admin")
    
    logger.info(f"Finished setting permissions for {repository.name}")

def main(repo_name_prefix: str = "tf-") -> int:
    work_dir = create_work_dir()

    try:
        github_object = get_github_instance(token_suffix=ORG)
    except Exception as e:
        logger.exception("Failed to retrieve Github instance!")
        return -1
    
    organization = github_object.get_organization(login=ORG)

    try:
        all_repositories = get_org_repositories(organization=organization, name_filter=repo_name_prefix)
    except Exception as e:
        logger.exception("Failed to retrieve Github Repositories!")
        return -2 

    user_choice = None
    while str(user_choice).lower().strip() not in ["y", "n"]:
        user_choice = input("Apply permissions to repositories? [y/n]: ").lower().strip()
        if user_choice == "n":
            logger.error("Aborted!")
            return 1   

    outcomes = []
    for repository in all_repositories:
        try:
            fix_permissions(github_object, repository, organization)
        except Exception as e:
            outcomes.append(f"EXCEPTION for {repository.name}: {e}")
    print("\n".join(outcomes))

if __name__ == "__main__":
    try:
        result = main(sys.argv[1])
    except IndexError:
        result = main()
    exit(code=result)
