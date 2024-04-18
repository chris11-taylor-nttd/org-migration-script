from graphviz import Digraph
import pathlib
import re
from git import Head, TagReference
from dataclasses import dataclass
from typing import Self
from contextlib import suppress
import itertools
import shutil
from functools import cache
import os

from git.repo import Repo
from github import Auth, Github
from github.Repository import Repository
from github.AuthenticatedUser import AuthenticatedUser
from github.Organization import Organization

WORK_DIR = pathlib.Path().cwd().joinpath("work")
DIAGRAM_DIR = pathlib.Path().cwd().joinpath("dependency_diagrams")
SOURCE_RE = re.compile(r'source\s*=\s*"(.+)"', flags=re.IGNORECASE)
MOD_RE = re.compile(r'(tf-[a-z0-9_-]+)', flags=re.IGNORECASE)
URL_RE = re.compile(r"(git::)?(?P<proto>https?)?(://)?github\.com/(?P<org>[a-z0-9_-]+)/(?P<repo>[a-z0-9_-]+)(\.git)?\?ref=(?P<ref>.+)")
ALT_URL_RE = re.compile(r"(git@github.com:)(?P<org>[a-z0-9_-]+)/(?P<repo>[a-z0-9_-]+)(\.git)?\?ref=(?P<ref>.+)")

OrganizationName = str
RepositoryName = str
Revision = str

SplitUrl = tuple[OrganizationName, RepositoryName, Revision | None]

module_cache: dict[str, object] = {}

migrated_repo_names = [
    "tf-module-resource_name",
    "tf-azurerm-module_primitive-resource_group",
    "tf-azurerm-module-network_interface_security_group_association",
    "tf-azurerm-module-virtual_machine_extension",
    "tf-azurerm-module_primitive-monitor_workspace",
    "tf-azurerm-module_primitive-network_interface_security_group_association",
    "tf-azurerm-module_primitive-application_insights",
    "tf-azurerm-module-windows_virtual_machine",
    "tf-azurerm-module_primitive-network_security_rule",
    "tf-azurerm-module_primitive-windows_virtual_machine",
    "tf-azurerm-module_primitive-role_assignment",
    "tf-azurerm-module_primitive-dns_zone",
    "tf-azurerm-module_primitive-network_watcher_flow_log",
    "tf-azurerm-module_primitive-private_dns_zone",
    "tf-azurerm-module-network_interface",
    "tf-azurerm-module_primitive-route",
    "tf-azurerm-wrapper_module-application_gateway",
    "tf-azurerm-module_primitive-virtual_network",
    "tf-azurerm-module_primitive-public_dns_records",
    "tf-azurerm-module_wrapper-application_gateway",
    "tf-azurerm-module_primitive-network_interface",
    "tf-azurerm-module_primitive-private_dns_records",
    "tf-azurerm-module_primitive-subnet_network_security_group_association",
    "tf-azurerm-module_primitive-network_security_group",
    "tf-azurerm-module-subnet_network_security_group_association",
    "tf-azurerm-module_primitive-firewall_policy_rule_collection_group",
    "tf-azurerm-module_primitive-public_ip",
    "tf-azurerm-module-public_ip",
    "tf-azurerm-module_primitive-network_watcher",
    "tf-azurerm-module_primitive-route_table",
    "tf-azurerm-module_primitive-firewall",
    "tf-azurerm-module_wrapper-security_group",
    "tf-azurerm-module_primitive-log_analytics_workspace",
    "tf-azurerm-module_primitive-virtual_machine_extension",
    "tf-azurerm-module_primitive-user_managed_identity",
    "tf-azurerm-wrapper_module-security_group",
    "tf-azurerm-module_primitive-nsg_subnet_association",
    "tf-azurerm-module_primitive-resource_group",
    "tf-azurerm-module_primitive-firewall_policy",
]

DISCOVERY_FORBIDDEN_DIRECTORIES = [
    ".git",
    "components",
    ".repo",
    "__pycache__",
    ".venv",
    ".terraform",
    ".terragrunt-cache"
]

def read_github_token() -> str:
    try:
        return os.environ["GITHUB_TOKEN"]
    except KeyError:
        raise RuntimeError(
            "ERROR: The GITHUB_TOKEN environment variable is not set. You must set this environment variable with the contents of your GitHub Personal Access Token (PAT) to use this script."
        )

def github_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {read_github_token()}"}

def get_github_instance(token: str | None = None) -> Github:
    if not token:
        token = read_github_token()
    auth = Auth.Token(token)
    return Github(auth=auth)

def get_github_repos(g: Github, user_or_org: AuthenticatedUser | Organization | None = None) -> list[Repository]:
    if user_or_org:
        repos = user_or_org.get_repos()
    else:
        repos = g.get_user().get_repos()
    return [repo for repo in repos]

def sync_repo(target_directory: pathlib.Path, clone_url: str, repo_ref: str | None = None) -> Repo | None:
    """Sync a Git repository.

    Args:
        target_directory (pathlib.Path): Where this repository will be placed. Ensure that this isn't a parent directory; should contain the name of the repo in this path.
        clone_url (str): HTTPS URL to clone from
        repo_ref (str | None, optional): Revision to check out. Defaults to None, which will try to check out 'main' (or 'master' if 'main' is not found)

    Returns:
        bool: Success (True) or Failure (False)
    """
    if target_directory.exists():
        shutil.rmtree(target_directory)
    try:
        repo = Repo.clone_from(url=clone_url, to_path=target_directory)
    except:
        repo = Repo.clone_from(url=clone_url, to_path=target_directory)

    if repo_ref is None:
        try:
            repo.git.checkout("main")
        except:
            try:
                repo.git.checkout("master")
            except:
                print(f"Failed to fully clone {clone_url}, cannot check out expected branches of 'main' and 'master'")
                return
    else:
        try:
            repo.git.checkout(repo_ref)
        except:
            print(f"Failed to fully clone {clone_url}, cannot check out '{repo_ref}'")
            return
    return repo


def discover_files(root_path: pathlib.Path, filename_partial: str) -> list[pathlib.Path]:
    directories = [d for d in root_path.iterdir() if d.is_dir() and not d.name.lower() in DISCOVERY_FORBIDDEN_DIRECTORIES]
    files = [f for f in root_path.iterdir() if not f.is_dir() and filename_partial in f.name.lower()]
    files.extend(list(itertools.chain.from_iterable([discover_files(root_path=d, filename_partial=filename_partial) for d in directories])))
    return files

def discover_directories(root_path: pathlib.Path, dirname_partial: str) -> list[pathlib.Path]:
    directories = [d for d in root_path.iterdir() if d.is_dir() and dirname_partial in d.name and not d.name.lower() in DISCOVERY_FORBIDDEN_DIRECTORIES]
    directories.extend(list(itertools.chain.from_iterable([discover_directories(root_path=d, dirname_partial=dirname_partial) for d in directories])))
    return directories

@dataclass
class ExternalTerraformModule:
    name: str

    def __hash__(self) -> int:
        return hash(self.name)
    
    def prettyprint(self, tabs: int = 0):
        print()
        print(f"{'  '*tabs}ExternalTerraformModule {self.name}")

@dataclass
class GitEnabledTerraformModule:
    url: str
    path: pathlib.Path
    name: str
    revision: Head
    tags: list[TagReference]
    examples: list[Self]
    dependencies: list[Self|ExternalTerraformModule]

    def __hash__(self) -> int:
        return hash(self.name)

    @staticmethod
    def build_repo_path(repo_name: str):
        return WORK_DIR.joinpath(repo_name)
    
    @staticmethod
    def split_github_url(url: str) -> SplitUrl:
        result = URL_RE.match(string=url)
        if result is None:
            result = ALT_URL_RE.match(string=url)
        if result is None:
            print(f"Failure to parse GitHub URL: {url=}")
            breakpoint()
        ref = None
        with suppress(Exception):
            ref = result['ref']
        return result['org'], result['repo'], ref

    @staticmethod
    def extract_examples(target_dir: pathlib.Path) -> list[Self]:
        examples_path = target_dir.joinpath("examples")
        if examples_path.exists():
            examples_folders = [d for d in examples_path.iterdir() if d.is_dir() and d.joinpath("main.tf").exists()]
            return [GitEnabledTerraformModule.from_directory(directory=example_folder) for example_folder in examples_folders]

    @staticmethod
    def extract_dependencies(target_dir: pathlib.Path) -> list[Self|ExternalTerraformModule]:
        deps = []
        main_tf = target_dir.joinpath("main.tf")
        if not main_tf.exists():
            return deps
        main_tf_contents = main_tf.read_text()
        dependency_references = re.findall(pattern=SOURCE_RE, string=main_tf_contents)
        with suppress(ValueError):
              dependency_references.remove("../..")
              dependency_references = [d.replace("git::", "") for d in dependency_references]
        for dep_ref in dependency_references:
            if 'github.com' in dep_ref:
                github_org, github_repo, github_ref = GitEnabledTerraformModule.split_github_url(dep_ref)
                if not f"{github_org}/{github_repo}" in module_cache:
                    try:
                        remote_repo = g.get_repo(full_name_or_id=f"{github_org}/{github_repo}")
                    except Exception as e:
                        print(f"Failed to acquire remote_repo {github_org}/{github_repo}")
                        raise
                    try:
                        github_module = GitEnabledTerraformModule.from_directory(directory=WORK_DIR.joinpath(github_repo))
                    except Exception as e:
                        github_module = GitEnabledTerraformModule.from_repository(repository=remote_repo, ref=github_ref)
                    finally:
                        if not f"{github_org}/{github_repo}" in module_cache:
                            module_cache[f"{github_org}/{github_repo}"] = github_module
                deps.append(module_cache[f"{github_org}/{github_repo}"])
            else:
                deps.append(ExternalTerraformModule(name=dep_ref))
        return deps

    @staticmethod
    def head_or_tag(local_repo: Repo) -> Head | TagReference:
        active_revision = local_repo.head
        for t in local_repo.tags:
            if active_revision.commit == t.commit:
                return t
        return active_revision
    
    @classmethod
    @cache
    def from_repository(cls, repository: Repository, ref: str|None = None):
        target_directory = GitEnabledTerraformModule.build_repo_path(repo_name=repository.name)
        
        if target_directory.exists():
           shutil.rmtree(target_directory)
           target_directory.mkdir(exist_ok=False)

        try:
            local_repo = sync_repo(target_directory=target_directory, clone_url=repository.clone_url, repo_ref=ref)
        except:
            local_repo = sync_repo(target_directory=target_directory, clone_url=repository.clone_url, repo_ref=ref)

        if not local_repo:
            raise RuntimeError(f"Failed to construct GitEnabledTerraformModule from {repository.name} {repository.git_url}")
        local_path = pathlib.Path(local_repo.working_tree_dir)
        return cls(
            url=repository.git_url, 
            path=local_path, 
            name=local_path.name,
            revision=GitEnabledTerraformModule.head_or_tag(local_repo=local_repo), 
            tags=list(local_repo.tags), 
            examples=GitEnabledTerraformModule.extract_examples(target_dir=target_directory), 
            dependencies = GitEnabledTerraformModule.extract_dependencies(target_dir=target_directory)
        )
    
    @classmethod
    @cache
    def from_directory(cls, directory: pathlib.Path):
        git_directory = directory
        if not git_directory.exists():
            raise RuntimeError(f"Supplied directory {directory} does not exist!")
        while not git_directory.joinpath(".git").exists():
            if git_directory == WORK_DIR:
                raise RuntimeError("Directory search exhausted")
            git_directory = git_directory.parent
        local_repo = Repo(path=git_directory)
        url = local_repo.remote().url
        path = directory
        name = directory.name
        revision = GitEnabledTerraformModule.head_or_tag(local_repo=local_repo)
        tags = list(local_repo.tags)
        examples = []
        dependencies = GitEnabledTerraformModule.extract_dependencies(target_dir=directory)
        return cls(
            url=url, 
            path=path, 
            name=name, 
            revision=revision, 
            tags=tags, 
            examples=examples, 
            dependencies=dependencies
        )
    
    def prettyprint(self, tabs: int = 0):
        print()
        print(f"{'  '*tabs}GitEnabledTerraformModule {self.name}")
        print(f"{'  '*tabs}{self.url=}")
        print(f"{'  '*tabs}{self.path=}")
        print(f"{'  '*tabs}{self.name=}")
        print(f"{'  '*tabs}{self.revision=}")
        print(f"{'  '*tabs}{self.tags=}")
        if self.examples:
            print(f"{'  '*tabs}self.examples=")
            for ex in self.examples:
                ex.prettyprint(tabs=tabs+1)
        if self.dependencies:
            print(f"{'  '*tabs}self.dependencies=")
            for dep in self.dependencies:
                dep.prettyprint(tabs=tabs+1)
    
    def get_viz_deps(self, in_example: bool = False):
        dag: dict[str, set[str]] = {self.name: set([d.name for d in self.dependencies])}
        for dependency in self.dependencies:
            if isinstance(dependency, GitEnabledTerraformModule):
                for k, v in dependency.get_viz_deps(True).items():
                    dag[k] = v
        if self.examples is not None and not in_example:
            for example in self.examples:
                if isinstance(example, GitEnabledTerraformModule):
                    for k, v in example.get_viz_deps(True).items():
                        dag[k] = v
        return dag



def build_viz_from_dag(viz: Digraph, dag: dict[str, set[str]]) -> Digraph:
    for key, value in dag.items():
        if 'depr' in key:
            viz.node(key, fillcolor="red", style="filled")
        else:
            viz.node(key)
        for v in value:
            if 'depr' in v:
                viz.node(v, fillcolor="red", style="filled")
            elif v in migrated_repo_names:
                viz.node(v, fillcolor="darkolivegreen2", style="filled")
            elif v.count("/") == 2:
                viz.node(v, fillcolor="darkolivegreen1", style="filled")
            else:
                viz.node(v)
            viz.edge(v, key)
    return viz

def main():
    WORK_DIR.mkdir(exist_ok=True)

    tf_repos = [r for r in g.get_organization('nexient-llc').get_repos() if r.name.startswith('tf-aws')]
    for tf_repo in tf_repos:
        print(f"Processing graph for {tf_repo.name.ljust(80)}", end="")
        try:
            repo = GitEnabledTerraformModule.from_repository(repository=tf_repo)
            dag = repo.get_viz_deps()
            if all([len(v) == 0 for v in dag.values()]):
                print(f"no dependencies to render.")
                continue
            viz = Digraph(comment=f"Terraform Dependencies for {repo.name}")
            viz = build_viz_from_dag(viz=viz, dag=dag)
            viz.render(str(DIAGRAM_DIR.joinpath(f"tf-dag-{repo.name}")), format="png", cleanup=True)
        except Exception as e:
            print(f"failed: {e}!")
            continue
        print("rendered.")

g = get_github_instance()

if __name__ == "__main__":
    main()
    # debug()