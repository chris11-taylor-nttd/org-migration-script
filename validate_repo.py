import sys
import pathlib

from git.repo import Repo

from migrate_repo import (
    logger,
    clone_source_repository,
    create_work_dir,
    load_repo_rename_map,
    delete_if_present,
    shell_command,
    block_for_user_input,
    block_for_user_input_with_bypass,
    add_and_commit
)

SOURCE_ORG = "launchbynttdata"

def go_mod_terratest_fix(repo: Repo):
    work_dir = pathlib.Path(repo.working_dir)
    go_mod_file = work_dir.joinpath("go.mod")
    go_mod_contents = go_mod_file.read_text()
    
    go_mod_contents_fixed = go_mod_contents.replace(
        "github.com/launchbynttdata/lcaf-component-terratest v1.0.0",
        "github.com/launchbynttdata/lcaf-component-terratest v1.0.4"
    )

    go_mod_contents_fixed = go_mod_contents_fixed.replace(
        "github.com/launchbynttdata/lcaf-component-terratest v1.0.1",
        "github.com/launchbynttdata/lcaf-component-terratest v1.0.4"
    )

    go_mod_contents_fixed = go_mod_contents_fixed.replace(
        "github.com/launchbynttdata/lcaf-component-terratest v1.0.2",
        "github.com/launchbynttdata/lcaf-component-terratest v1.0.4"
    )

    go_mod_contents_fixed = go_mod_contents_fixed.replace(
        "github.com/launchbynttdata/lcaf-component-terratest v1.0.3",
        "github.com/launchbynttdata/lcaf-component-terratest v1.0.4"
    )

    if go_mod_contents != go_mod_contents_fixed:
        logger.info("Performed updates to go.mod, writing new file")
        go_mod_file.write_text(go_mod_contents_fixed)

        delete_if_present(file_path=work_dir.joinpath("go.sum"))
        go_mod_tidy_result = block_for_user_input(
            message="Executing `go mod tidy`",
            retry_function=shell_command,
            command=["go", "mod", "tidy"],
            source_repo=repo,
            raise_on_failure=True
        )
        if go_mod_tidy_result == -999:
            raise RuntimeError(f"User aborted!")


def test_impl_simple_env_var_fix(repo: Repo):
    work_dir = pathlib.Path(repo.working_dir)
    test_impl_file = work_dir.joinpath("tests/testimpl/test_impl.go")
    if not test_impl_file.exists():
        logger.warning(f"{test_impl_file} did not exist, no edits will be made!")
        return
    test_impl_contents = test_impl_file.read_text()
    test_impl_contents_fixed = test_impl_contents.replace("AZURE_SUBSCRIPTION_ID", "ARM_SUBSCRIPTION_ID")
    if test_impl_contents_fixed != test_impl_contents:
        logger.info("Performed env var updates to test_impl.go, writing new file")
        test_impl_file.write_text(test_impl_contents_fixed)


def has_changes(repo: Repo) -> bool:
    return repo.is_dirty(untracked_files=True)

def push_changes_and_move_tag(repo: Repo):
    repo.git.push(["origin", "main"])
    repo.git.tag(["-d", "1.0.0"])
    repo.git.tag(["1.0.0"])
    repo.git.push(["origin", "1.0.0", "-f"])

def main(source_repo_name: str) -> int:
    work_dir = create_work_dir()
    repo_rename_map = load_repo_rename_map()
    if source_repo_name in repo_rename_map:
        source_repo_name = repo_rename_map[source_repo_name]
    source_repo = clone_source_repository(source_repo_name=source_repo_name, work_dir=work_dir, source_org=SOURCE_ORG)
    _ = shell_command(source_repo=source_repo, command=["make", "configure"], raise_on_failure=True)
    
    go_mod_terratest_fix(repo=source_repo)
    test_impl_simple_env_var_fix(repo=source_repo)

    make_check_outcome = block_for_user_input(
        message="Executing `make check`, this may take a while!",
        retry_function=shell_command,
        command=["make", "check"],
        source_repo=source_repo,
        raise_on_failure=True
    )

    if make_check_outcome == -999:
        return make_check_outcome
    
    if has_changes(repo=source_repo):
        add_commit_result = block_for_user_input_with_bypass(
            message="Adding changes and committing",
            retry_function=add_and_commit,
            source_repo=source_repo,
            raise_on_failure=True,
            commit_message="Migration validation fixes for make check"
        )

        if add_commit_result == -999:
            return add_commit_result
        
        push_changes_and_move_tag(repo=source_repo)
    else:
        logger.info("No changes made during validation process, all done!")

if __name__ == "__main__":
    source_repo = sys.argv[1]
    result = main(source_repo_name=source_repo)
    exit(code=result)
