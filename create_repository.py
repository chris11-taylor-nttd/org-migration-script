import logging
import sys

from github.Organization import Organization
from github.Repository import Repository

from migrate_repo import get_github_instance

ORGANIZATION = "launchbynttdata"
PERMISSIONS = {
    "platform-team": "maintain",
    "platform-administrators": "admin",
    "terraform-administrators": "admin",
}

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s",
    datefmt="%F %T %Z",
)
logger = logging.getLogger("create_repository")
logging.getLogger("git").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)


def create_repository(org: Organization, repo_name: str) -> Repository:
    repo = org.create_repo(
        name=repo_name,
        private=False,
        visibility="internal",
        allow_merge_commit=False,
        allow_rebase_merge=False,
        allow_squash_merge=True,
        allow_update_branch=True,
        delete_branch_on_merge=True,
        auto_init=True,
    )
    return repo


def set_repository_permissions(org: Organization, repo: Repository) -> None:
    for team_slug, team_permission in PERMISSIONS.items():
        if team_slug == "terraform-administrators" and not repo.name.startswith("tf-"):
            logger.warning(
                f"Skipping setting permissions for team {team_slug} on {org.login}/{repo.name}, doesn't appear to be a Terraform repository. Set this permission manually if required."
            )
            continue
        team = org.get_team_by_slug(team_slug)
        logger.info(
            f"Setting permissions for team {team_slug} on {org.login}/{repo.name}"
        )
        team.update_team_repository(repo=repo, permission=team_permission)
        logger.info(f"Permissions for {team_slug} set to {team_permission}.")


def create_initial_release(repo: Repository) -> None:
    release = repo.create_git_release(
        tag="0.1.0",
        name="0.1.0",
        message="Repository created",
        draft=False,
        prerelease=False,
    )
    logger.info(f"Created initial release and tag: {release}")


if __name__ == "__main__":
    try:
        repo_name = sys.argv[1]
    except Exception:
        raise ValueError("Must provide the repo name as the first argument.")

    g = get_github_instance()
    org = g.get_organization(ORGANIZATION)

    repo = create_repository(org=org, repo_name=repo_name)
    set_repository_permissions(org=org, repo=repo)
    create_initial_release(repo=repo)

    logger.info(f"Created {repo.html_url} and set initial permissions.")
