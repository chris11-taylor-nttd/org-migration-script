# Migration script for Launch Public GitHub 

Takes our existing repos and migrates them to the new Launch Public GitHub Organization (launchbynttdata) with some defaults.

## Prerequisites

1. Create a fine-grained PAT following the steps [here](https://github.com/nexient-llc/launch-cli/blob/main/docs/generating-a-token.md) for the `nexient-llc` organization.
2. Export the PAT to your shell with the following command:

```sh
export GITHUB_TOKEN_nexient_llc=<YOUR OLD ORGANIZATION PAT HERE>
```

3. Create a fine-grained PAT following the steps [here](https://github.com/nexient-llc/launch-cli/blob/main/docs/generating-a-token.md) for the `launchbynttdata` organization.
4. Export the PAT to your shell with the following command:

```sh
export GITHUB_TOKEN_launchbynttdata=<YOUR NEW ORGANIZATION PAT HERE>
```
5. Clone this repository to your local machine.
6. From the cloned folder, execute the following commands:

```sh
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Migration Workflow

By using this script, you will be effectively performing the following actions:

- Creating a subdirectory called `work` if it does not already exist.
- Creating a GitHub connection to both `nexient-llc` and `launchbynttdata`
- Cloning the source repository to the `work` directory. If it has already been cloned, it will be deleted and recloned fresh.
- Running `make configure` in the source repository.
- Performing static file replacements 
    - Files from the `templates/` directory of this repository are copied into the source repository.
    - Removing some common unused files from the source repository -- commitlint.config.js, test.tfvars and example.tfvars from the root, test.tfvars from the tests folder
- Performing dynamic replacements
    - Updates the `go.mod` version to 1.21 
    - Removes `.git` from the module name in `go.mod` (the .git is not allowed but was sometimes found in our repos)
    - Perform a find-replace on all text (anything that isn't a binary) files in the repository
        - Find/replace values are the keys/values in the globally-scoped `REPLACEMENTS` dictionary in `migrate_repo.py`
        - Find/replace will not descend into directories matching the names of those in the globally-scoped `DISCOVERY_FORBIDDEN_DIRECTORIES` dictionary in `migrate_repo.py`
    - If `go.mod` or `go.sum` are touched as part of this replacement process, `go.sum` is deleted and `go mod tidy` is run to regenerate it.
- `git add` all files and `git commit` with the message "Migrate repository from old GitHub organization."
- Add a remote named `migration_target` to the source repository in the `work` directory, pointing at the `launchbynttdata` destination.
- Push to the `migration_target` remote

## Migrating a Repository

To migrate a repository, call the `migrate_repo.py` script with the name of the repository to be migrated.

If the destination repository's name is different (renamed due to naming conventions), supply the destination name as well.

```sh
python3.11 migrate_repo.py <source_repo_name> [<destination_repo_name>]
```

A blank repository (without any branches) must exist in the `launchbynttdata` organization for the migration to occur. If the repo you wish to migrate does not already exist, please reach out to Chris to have this resolved.

If you run into a failure (see next section) and need to `abort` a migration, the `migrate_repo.py` script will remove the temporary repository it cloned and reclone it on the next run. If you wish to preserve file modifications between runs of the script, you will need to manually add/commit/push your changes to the new organization (not recommended). 

### Handling Migration Failures

The script has some built-in error handling for retrying operations where possible. Since many of our modules rely on other modules (via their examples) that may not yet exist in the new GitHub organization, **some failures during the process are expected**!

Here's what you can expect to see in the logs when a failure occurs during the add/commit phase:

> ...
> 2024-03-20 17:46:24 CDT migration       INFO    Deleting /Users/chris.taylor/code/github/github-scripts/migration/work/tf-azurerm-module_primitive-monitor_diagnostic_setting/go.sum
> 2024-03-20 17:46:24 CDT migration       INFO    About to run go mod tidy in /Users/chris.taylor/code/github/github-scripts/migration/work/tf-azurerm-module_primitive-monitor_diagnostic_setting...
> 2024-03-20 17:46:25 CDT migration       INFO    Successfully ran go mod tidy
> 2024-03-20 17:46:25 CDT migration       INFO    Adding changes and committing
> 2024-03-20 17:46:49 CDT migration       ERROR   Failure when calling <function add_and_commit at 0x107532480>. This operation can be retried or bypassed!
> ...
> Terraform validate.......................................................Failed
> - hook id: terraform_validate
> - exit code: 1
> 
> 'terraform init' failed, 'terraform validate' skipped: examples/diagnostic_setting
> ...
> Error: Failed to download module
> │ 
> │   on main.tf line 25:
> │   25: module "log_analytics_workspace" {
> │ 
> │ Could not download module "log_analytics_workspace" (main.tf:25) source
> │ code from
> │ "git::https://github.com/launchbynttdata/tf-azurerm-module_primitive-log_analytics_workspace.git?ref=0.1.0":
> │ error downloading
> │ 'https://github.com/launchbynttdata/tf-azurerm-module_primitive-log_analytics_workspace.git?ref=0.1.0':
> │ /opt/homebrew/Cellar/git/2.40.1/libexec/git-core/git exited with 128:
> │ Cloning into '.terraform/modules/log_analytics_workspace'...
> │ remote: Repository not found.
> │ fatal: repository
> │ 'https://github.com/launchbynttdata/tf-azurerm-module_primitive-log_analytics_workspace.git/'
> │ not found
> │ 

This repository missing is completely expected, as it hasn't been migrated to the new organization yet. **If all the failures you experience for a single module are failures to download modules like the above, you are clear to continue migrating this repo**. If you experience any other sort of failure, please let Chris know immediately!

At the very bottom of the failure message, you will be prompted for an action:

> ...
> golangci-lint............................................................Passed
> Detect secrets...........................................................Passed'
> Please enter 'abort', 'retry', or 'bypass':

Upon entering `bypass` and pressing Enter, you should receive confirmation that the migration completed:

> Please enter 'abort', 'retry', or 'bypass': bypass
> 2024-03-20 17:50:58 CDT migration       INFO    Adding changes and committing
> 2024-03-20 17:50:58 CDT migration       INFO    Success!
> 2024-03-20 17:50:58 CDT migration       INFO    Added migration_target remote for https://github.com/launchbynttdata/tf-azurerm-module_primitive-monitor_diagnostic_setting.git
> 2024-03-20 17:50:58 CDT migration       INFO    Pushing updated repository to launchbynttdata/tf-azurerm-module_primitive-monitor_diagnostic_setting
> 2024-03-20 17:50:59 CDT migration       INFO    Success!
> 2024-03-20 17:50:59 CDT migration       INFO    Setting archived = True for nexient-llc/tf-azurerm-module_primitive-monitor_diagnostic_setting
> 2024-03-20 17:51:00 CDT migration       INFO    Migration complete! Repo is now available at launchbynttdata/tf-azurerm-module_primitive-monitor_diagnostic_setting

### Abort and Retry

If you wanted to halt the migration rather than proceeding (say you got a different error and need to investigate), you can provide `abort` and the script will exit without completing the migration. 

If you think you can resolve an error by making changes on the filesystem, simply allow the script to wait for input, make your changes, and then issue `retry` to have the script reattempt the given step.