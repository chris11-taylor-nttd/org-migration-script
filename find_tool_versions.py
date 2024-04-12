import itertools
import pathlib

WORK_DIR = pathlib.Path.cwd().joinpath("work")

repo_folders = [folder for folder in WORK_DIR.iterdir() if folder.is_dir()]
repo_tool_versions = [folder.joinpath(".tool-versions") for folder in repo_folders if folder.joinpath(".tool-versions").exists()]
combined_contents = list(itertools.chain.from_iterable([repo_tool_version.read_text().splitlines() for repo_tool_version in repo_tool_versions]))
unique_contents = set(combined_contents)

print("\n".join(unique_contents))
