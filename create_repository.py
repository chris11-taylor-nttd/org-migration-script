from migrate_repo import get_github_instance
import sys


try:
    repo_name = sys.argv[1]
except:
    raise ValueError("Must provide the repo name as the first argument.")

g = get_github_instance(token_suffix="launchbynttdata")
created_repo = g.get_organization("launchbynttdata").create_repo(name=sys.argv[1], private=False, visibility="internal", allow_merge_commit=False, allow_rebase_merge=False, allow_squash_merge=True, allow_update_branch=True, delete_branch_on_merge=True)
print(created_repo.html_url)