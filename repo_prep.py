from enum import Enum
import logging
import os
import pathlib
import json
import sys

from github import Auth, Github
from github.Repository import Repository
from github.Team import Team
from github.Organization import Organization
from github.GithubException import UnknownObjectException


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s",
    datefmt="%F %T %Z",
)
logger = logging.getLogger("repo_prep")
logging.getLogger("git").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)


class GithubPermission(str, Enum):
    PULL = "pull"
    TRIAGE = "triage"
    PUSH = "push"
    MAINTAIN = "maintain"
    ADMIN = "admin"


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


def create_repo(organization: Organization, repo_name: str) -> Repository:
    created_repo = organization.create_repo(
        name=repo_name,
        visibility="public",
        allow_merge_commit=False,
        allow_rebase_merge=False,
        delete_branch_on_merge=True,
        allow_update_branch=True,
    )
    logger.info(f"Created {created_repo} in {organization}")
    return created_repo


def configure_repo_permissions(
    repository: Repository, team: Team, permission: GithubPermission
):
    logger.info(f"Applying {permission} for {team} to {repository}")
    team.update_team_repository(repo=repository, permission=permission.value)


def update_repo_settings(repository: Repository):
    logger.info(
        f"Setting allow_merge_commit=False, allow_rebase_merge=False, delete_branch_on_merge=True, allow_update_branch=True for {repository}"
    )
    repository.edit(
        allow_merge_commit=False,
        allow_rebase_merge=False,
        delete_branch_on_merge=True,
        allow_update_branch=True,
    )


def get_repositories(
    g: Github, organization: Organization, starts_with: str = ""
) -> list[Repository]:
    return [r for r in organization.get_repos() if r.name.startswith(starts_with)]


def load_repo_map():
    # return json.loads(pathlib.Path("nexient-llc-repos-rename-map.json").read_text())
    rename_map: dict[str, str] = json.loads(pathlib.Path("nexient-llc-repos-rename-map.json").read_text())
    return {k: v for k, v in rename_map.items() if k.startswith("tf-az")}

def assign_permissions_to_existing_repos_in_new_organization(
    organization: Organization,
):
    existing_repos = {
        "lcaf": [
            "launch-common-automation-framework",
            "lcaf-component-container",
            "lcaf-component-platform",
            "lcaf-component-policy",
            "lcaf-component-python",
            "lcaf-component-terragrunt",
            "lcaf-component-terraform",
            "lcaf-component-terratest",
            "lcaf-component-provider_aws-pipeline_aws",
            "lcaf-component-provider_az-pipeline_azdo",
            "common-platform-documentation"
        ],
        "lcaf_tf": [
            "lcaf-skeleton-terragrunt",
            "lcaf-skeleton-terraform"
        ],
        "general": [
            "asdf-regula",
            "actions-helm-resolve_dependencies",
            "actions-asdf-install_tools",
            "actions-helm-inject_chart_version",
            "actions-helm-test",
            "git-repo",
            "magicdust",
            "dso-zsh",
            "launch-cli",
            "git-webhook-lambda"
        ]
    }

    permission_map = {
        "lcaf": {
            organization.get_team_by_slug("platform-team"): GithubPermission.MAINTAIN,
            organization.get_team_by_slug(
                "platform-administrators"
            ): GithubPermission.ADMIN,
            organization.get_team_by_slug(
                "lcaf-administrators"
            ): GithubPermission.ADMIN,
        },
        "lcaf_tf": {
            organization.get_team_by_slug("platform-team"): GithubPermission.MAINTAIN,
            organization.get_team_by_slug(
                "platform-administrators"
            ): GithubPermission.ADMIN,
            organization.get_team_by_slug(
                "terraform-administrators"
            ): GithubPermission.ADMIN,
            organization.get_team_by_slug(
                "lcaf-administrators"
            ): GithubPermission.ADMIN,
        },
        "general": {
            organization.get_team_by_slug("platform-team"): GithubPermission.MAINTAIN,
            organization.get_team_by_slug(
                "platform-administrators"
            ): GithubPermission.ADMIN,
        },
        "tf": {
            organization.get_team_by_slug("platform-team"): GithubPermission.MAINTAIN,
            organization.get_team_by_slug(
                "platform-administrators"
            ): GithubPermission.ADMIN,
            organization.get_team_by_slug(
                "terraform-administrators"
            ): GithubPermission.ADMIN,
        },
    }

    for map_type, map_permissions in permission_map.items():
        if map_type in existing_repos:
            for repo_name in existing_repos[map_type]:
                repository = organization.get_repo(name=repo_name)
                for team, permission in map_permissions.items():
                    configure_repo_permissions(
                        repository=repository, team=team, permission=permission
                    )
                    update_repo_settings(repository=repository)


def assign_migration_group_admin_permissions(
    organization: Organization, repositories: list[Repository]
):
    migration_team = organization.get_team_by_slug("azure-migrations")
    for repository in repositories:
        configure_repo_permissions(
            repository=repository,
            team=migration_team,
            permission=GithubPermission.ADMIN,
        )


def unassign_migration_group_admin_permissions(
    organization: Organization, repositories: list[Repository]
):
    migration_team = organization.get_team_by_slug("azure-migrations")
    for repository in repositories:
        logger.info(f"Removing {migration_team} from {repository}")
        migration_team.remove_from_repos(repo=repository)


def create_migration_targets(organization: Organization):
    repo_map = load_repo_map()
    permission_map = {
        organization.get_team_by_slug("platform-team"): GithubPermission.MAINTAIN,
        organization.get_team_by_slug(
            "platform-administrators"
        ): GithubPermission.ADMIN,
        organization.get_team_by_slug(
            "terraform-administrators"
        ): GithubPermission.ADMIN,
    }
    for new_repo in repo_map.values():
        try:
            created_repo = create_repo(organization=organization, repo_name=new_repo)
        except Exception as e:
            logger.warning(f"Failed to create_repo: {e}, trying to use existing")
            try:
                created_repo = organization.get_repo(name=new_repo)
            except Exception as e:
                logger.critical(f"Failed to handle {e}")
        for team, permission in permission_map.items():
            configure_repo_permissions(
                repository=created_repo, team=team, permission=permission
            )


def get_existing_repositories(
    organization: Organization, repo_names: list[str]
) -> list[Repository]:
    found_repos = []
    for repo_name in repo_names:
        try:
            found_repos.append(organization.get_repo(name=repo_name))
        except UnknownObjectException:
            logger.warning(
                f"Repository '{repo_name}' didn't exist within {organization}"
            )
    return found_repos


def initiate_migration(old_organization: Organization, new_organization: Organization):
    repo_map = load_repo_map()
    old_org_repositories = get_existing_repositories(
        organization=old_organization, repo_names=list(repo_map.keys())
    )
    create_migration_targets(organization=new_organization)
    new_org_repositories = get_existing_repositories(
        organization=new_organization, repo_names=list(repo_map.values())
    )
    assign_migration_group_admin_permissions(
        organization=old_organization, repositories=old_org_repositories
    )
    assign_migration_group_admin_permissions(
        organization=new_organization, repositories=new_org_repositories
    )


def migration_status(old_organization: Organization, new_organization: Organization):
    repo_map = load_repo_map()
    migrated_repo_names = set([])
    for old_repo_name, new_repo_name in repo_map.items():
        old_repo = old_organization.get_repo(old_repo_name)
        new_repo = new_organization.get_repo(new_repo_name)
        print(
            wide_display(
                old_repo=old_repo,
                new_repo=new_repo,
            )
        )
        if len([b for b in new_repo.get_branches()]):
            migrated_repo_names.add(new_repo.name)
            migrated_repo_names.add(old_repo.name)
    
    print("MIGRATED: ")
    print("\n".join(migrated_repo_names))


def wide_display(old_repo: Repository, new_repo: Repository):
    old_is_archived = f"Archived: {old_repo.archived}"
    try:
        new_has_main = f"Has Main: {new_repo.get_branch('main')}"
    except:
        new_has_main = f"Has Main: NOT FOUND"
    text_lines = []
    text_lines.append(f"{old_repo.name.rjust(80)} => {new_repo.name.ljust(80)}")
    text_lines.append(f"{old_is_archived.rjust(80)}    {new_has_main.ljust(80)}")
    return "\n".join(text_lines) + "\n"


def complete_migration(old_organization: Organization, new_organization: Organization):
    repo_map = load_repo_map()
    old_org_repositories = get_existing_repositories(
        organization=old_organization, repo_names=list(repo_map.keys())
    )
    new_org_repositories = get_existing_repositories(
        organization=new_organization, repo_names=list(repo_map.values())
    )
    unassign_migration_group_admin_permissions(
        organization=old_organization, repositories=old_org_repositories
    )
    unassign_migration_group_admin_permissions(
        organization=new_organization, repositories=new_org_repositories
    )


def reset_migration(old_organization: Organization, new_organization: Organization):
    repo_map = load_repo_map()
    old_org_repositories = get_existing_repositories(
        organization=old_organization, repo_names=list(repo_map.keys())
    )
    new_org_repositories = get_existing_repositories(
        organization=new_organization, repo_names=list(repo_map.values())
    )
    unassign_migration_group_admin_permissions(
        organization=old_organization, repositories=old_org_repositories
    )
    for new_repository in new_org_repositories:
        logger.info(f"Deleting repository {new_repository}")
        new_repository.delete()


def main(cmd: str) -> None:
    old_github = get_github_instance(token_suffix="nexient-llc")
    old_org = old_github.get_organization("nexient-llc")
    new_github = get_github_instance(token_suffix="launchbynttdata")
    new_org = new_github.get_organization("launchbynttdata")

    if cmd == "begin":
        initiate_migration(old_organization=old_org, new_organization=new_org)
    elif cmd == "complete":
        complete_migration(old_organization=old_org, new_organization=new_org)
    elif cmd == "status":
        migration_status(old_organization=old_org, new_organization=new_org)
    elif cmd == "reset":
        reset_migration(old_organization=old_org, new_organization=new_org)
    else:
        print("Unrecognized command!")
        migration_status(old_organization=old_org, new_organization=new_org)


if __name__ == "__main__":
    try:
        cmd = sys.argv[1]
    except:
        cmd = "status"
    main(cmd=cmd)
