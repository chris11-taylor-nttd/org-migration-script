import pathlib

from github.Organization import Organization
from github.Repository import Repository

from git.repo import Repo

from migrate_repo import (
    get_github_instance,
    clone_source_repository,
    shell_command,
    logger
)

ORG_NAME = "launchbynttdata"
WORK_DIR = pathlib.Path().cwd().joinpath("work")

def get_repositories(
        organization: Organization, 
        repo_name_partial: str = ""
    ) -> list[Repository]:
    return [
        repo 
        for repo 
        in organization.get_repos() 
        if repo_name_partial in repo.name
    ]

def clone(repository: Repository) -> Repo:
    return clone_source_repository(
        source_repo_name=repository.name,
        work_dir=WORK_DIR,
        source_org=ORG_NAME
    )

def make_check_succeeds(repo: Repo) -> bool:
    try:
        shell_command(source_repo=repo, command=["make", "configure"], raise_on_failure=True)
    except Exception as e:
        print(f"{repo} failed to make configure: {e}")
        return False
    try:
        shell_command(source_repo=repo, command=["make", "check"], raise_on_failure=True)
    except Exception as e:
        print(f"{repo} failed to make check: {e}")
        return False
    return True

def has_an_example(repo: Repo) -> bool:
    example_folder = pathlib.Path(repo.working_dir).joinpath("examples")
    if not example_folder.exists():
        logger.error(f"No directory found at {example_folder}")
        return False
    examples_subdirs = [f for f in example_folder.iterdir() if f.is_dir()]
    if not examples_subdirs:
        logger.error(f"No examples directories found in {example_folder}")
        return False
    return any([folder.joinpath("main.tf").exists() for folder in examples_subdirs])

def has_modern_tests(repo: Repo) -> bool:
    tests_folder = pathlib.Path(repo.working_dir).joinpath("tests")
    if not tests_folder.exists():
        logger.error(f"No directory found at {tests_folder}")
        return False
    post_deploy_functional_folder = tests_folder.joinpath("post_deploy_functional")
    if not post_deploy_functional_folder.exists():
        logger.error(f"No directory found at {post_deploy_functional_folder}")
        return False
    post_deploy_functional_main = post_deploy_functional_folder.joinpath("main_test.go")
    if not post_deploy_functional_main.exists():
        logger.error(f"No main_test.go found in {post_deploy_functional_folder}")
        return False
    post_deploy_functional_readonly_folder = tests_folder.joinpath("post_deploy_functional_readonly")
    if not post_deploy_functional_readonly_folder.exists():
        logger.error(f"No directory found at {post_deploy_functional_readonly_folder}")
        return False
    post_deploy_functional_readonly_main = post_deploy_functional_readonly_folder.joinpath("main_test.go")
    if not post_deploy_functional_readonly_main.exists():
        logger.error(f"No main_test.go found in {post_deploy_functional_readonly_folder}")
        return False
    testimpl_folder = tests_folder.joinpath("testimpl")
    if not testimpl_folder.exists():
        logger.error(f"No directory found at {testimpl_folder}")
        return False
    test_implementation = testimpl_folder.joinpath("test_impl.go")
    if not test_implementation.exists():
        logger.error(f"No test_impl.go found in {testimpl_folder}")
        return False
    return True

def main(filter_repos_to: list[str] | None = None) -> None:
    results: dict[Repository, tuple[bool, bool, bool]] = {}
    org = get_github_instance(token_suffix=ORG_NAME).get_organization(login=ORG_NAME)
    tf_repos = get_repositories(organization=org, repo_name_partial="tf-")
    if filter_repos_to:
        tf_repos = [repo for repo in tf_repos if repo.name in filter_repos_to]
    try:
        for repo in tf_repos:
            local_repo = clone(repository=repo)
            results[repo] = (
                has_an_example(repo=local_repo),
                has_modern_tests(repo=local_repo),
                make_check_succeeds(repo=local_repo)
            )
    except KeyboardInterrupt:
        print("\nCtrl-C\n")
    finally:
        print("repo_name,repo_url,has_example,has_tests,make_check")
        for repo, results in results.items():
            print(f"{repo.name},{repo.html_url},{results[0]},{results[1]},{results[2]}")

if __name__ == "__main__":
    # repo_name_list = [
    #     "tf-azurerm-module_collection-hubspoke_monitor",
    #     "tf-azurerm-module_primitive-network_interface_security_group_association",
    #     "tf-azurerm-module_primitive-public_ip"
    # ]
    # main(filter_repos_to=repo_name_list)
    main()
