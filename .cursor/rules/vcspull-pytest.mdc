---
description: 
globs: tests/**/test_*.py
alwaysApply: true
---

# VCSPull Pytest Integration with libvcs

When writing tests for vcspull, leverage libvcs's pytest plugin to efficiently create and manage VCS repositories during testing.

## Available Fixtures from libvcs

libvcs provides a complete set of fixtures that automatically handle the creation and cleanup of VCS repositories:

### Core Repository Creation Fixtures

- `create_git_remote_repo`: Factory fixture that creates a local Git repository
- `create_svn_remote_repo`: Factory fixture that creates a local SVN repository
- `create_hg_remote_repo`: Factory fixture that creates a local Mercurial repository

### Pre-configured Repository Fixtures

- `git_repo`: Pre-made Git repository clone (GitSync instance)
- `svn_repo`: Pre-made SVN repository checkout (SvnSync instance) 
- `hg_repo`: Pre-made Mercurial repository clone (HgSync instance)

### Environment & Configuration Fixtures

- `set_home`: Sets a temporary home directory
- `gitconfig`: Git configuration for test repositories
- `hgconfig`: Mercurial configuration for test repositories
- `git_commit_envvars`: Environment variables for Git commits

## Usage Examples

### Basic Repository Creation

```python
def test_vcspull_with_git(create_git_remote_repo):
    # Create a test git repository on-the-fly
    repo_path = create_git_remote_repo()
    
    # repo_path is now a pathlib.Path pointing to a clean git repo
    # Use this repository in your vcspull tests
```

### Using Pre-configured Repositories

```python
def test_vcspull_sync(git_repo):
    # git_repo is already a GitSync instance with a clean repository
    # Use it directly in your tests
    
    # The repository will be automatically cleaned up after the test
```

### Custom Repository Setup

```python
def test_custom_repo_state(
    create_git_remote_repo,
    git_commit_envvars
):
    # Create a repo with custom initialization
    repo_path = create_git_remote_repo()
    
    # Modify the repository as needed with the correct environment
    import subprocess
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "Custom commit"],
        cwd=repo_path,
        env=git_commit_envvars
    )
```

## Benefits

- **Fast tests**: Repositories are created efficiently and cached appropriately
- **Clean environment**: Each test gets fresh repositories without interference
- **Reduced boilerplate**: No need to manually create/clean up repositories
- **Realistic testing**: Test against actual VCS operations
- **Compatible with pytest-xdist**: Works correctly with parallel test execution

For detailed documentation on all available fixtures, visit:
- https://libvcs.git-pull.com/pytest-plugin.html
- https://github.com/vcs-python/libvcs/blob/master/src/libvcs/pytest_plugin.py
