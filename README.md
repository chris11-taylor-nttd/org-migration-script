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

## Migrating a Repository

To migrate a repository, call the `migrate_repo.py` script with the name of the repository to be migrated.

If the destination repository's name is different (renamed due to naming conventions), supply the destination name as well.

```sh
python3.11 migrate_repo.py <source_repo_name> [<destination_repo_name>]
```

A blank repository (without any branches) must exist in the `launchbynttdata` organization for the migration to occur. If the repo you wish to migrate does not already exist, please reach out to Chris to have this resolved.
