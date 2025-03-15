# VCSPull Configuration Migration Guide

VCSPull has updated its configuration format to provide a cleaner, more maintainable, and better validated structure. This guide will help you migrate your existing configuration files to the new format.

## Configuration Format Changes

### Old Format (v1)

The old configuration format used a nested directory structure where paths were mapped to repository groups:

```yaml
# Old format (v1)
/home/user/projects:
  repo1: git+https://github.com/user/repo1.git
  repo2:
    url: git+https://github.com/user/repo2.git
    remotes:
      upstream: git+https://github.com/upstream/repo2.git

/home/user/work:
  work-repo: 
    url: git+https://github.com/company/work-repo.git
    rev: main
```

### New Format (v2)

The new format is flatter and more structured, with explicit sections for settings, repositories, and includes:

```yaml
# New format (v2)
settings:
  sync_remotes: true
  default_vcs: git
  depth: null

repositories:
  - name: repo1
    path: /home/user/projects/repo1
    url: https://github.com/user/repo1.git
    vcs: git
  
  - name: repo2
    path: /home/user/projects/repo2
    url: https://github.com/user/repo2.git
    vcs: git
    remotes:
      upstream: https://github.com/upstream/repo2.git
  
  - name: work-repo
    path: /home/user/work/work-repo
    url: https://github.com/company/work-repo.git
    vcs: git
    rev: main

includes:
  - ~/other-config.yaml
```

## Migration Tool

VCSPull includes a built-in migration tool to help you convert your configuration files to the new format.

### Using the Migration Command

The migration command is available as a subcommand of vcspull:

```bash
vcspull migrate [OPTIONS] [CONFIG_PATHS...]
```

If you don't specify any configuration paths, the tool will search for configuration files in the standard locations:
- `~/.config/vcspull/`
- `~/.vcspull/`
- Current working directory

### Options

| Option | Description |
|--------|-------------|
| `-o, --output PATH` | Path to save the migrated configuration (if not specified, overwrites the original) |
| `-n, --no-backup` | Don't create backup files of original configurations |
| `-f, --force` | Force migration even if files are already in the latest format |
| `-d, --dry-run` | Show what would be migrated without making changes |
| `-c, --color` | Colorize output |

### Examples

#### Migrate a specific configuration file

```bash
vcspull migrate ~/.vcspull/config.yaml
```

#### Preview migrations without making changes

```bash
vcspull migrate -d -c
```

#### Migrate to a new file without overwriting the original

```bash
vcspull migrate ~/.vcspull/config.yaml -o ~/.vcspull/new-config.yaml
```

#### Force re-migration of already migrated configurations

```bash
vcspull migrate -f
```

## Migration Process

When you run the migration command, the following steps occur:

1. The tool detects the version of each configuration file
2. For each file in the old format (v1):
   - The paths and repository names are converted to explicit path entries
   - VCS types are extracted from URL prefixes (e.g., `git+https://` becomes `https://` with `vcs: git`)
   - Remote repositories are normalized
   - The new configuration is validated
   - If valid, the new configuration is saved (with backup of the original)

## Manual Migration

If you prefer to migrate your configurations manually, follow these guidelines:

1. Create a new YAML file with the following structure:
   ```yaml
   settings:
     sync_remotes: true  # or other settings as needed
     default_vcs: git    # default VCS type if not specified
   
   repositories:
     - name: repo-name
       path: /path/to/repo
       url: https://github.com/user/repo.git
       vcs: git  # or hg, svn as appropriate
   ```

2. For each repository in your old configuration:
   - Create a new entry in the `repositories` list
   - Use the parent path + repo name for the `path` field
   - Extract the VCS type from URL prefixes if present
   - Copy remotes, revisions, and other settings

3. If you have included configurations, add them to the `includes` list

## Troubleshooting

### Common Migration Issues

1. **Invalid repository configurations**: Repositories that are missing required fields (like URL) will be skipped during migration. Check the log output for warnings about skipped repositories.

2. **Path resolution**: The migration tool resolves relative paths from the original configuration file. If your migrated configuration has incorrect paths, you may need to adjust them manually.

3. **VCS type detection**: The tool infers VCS types from URL prefixes (`git+`, `hg+`, `svn+`) or from URL patterns (e.g., GitHub URLs are assumed to be Git). If the VCS type is not correctly detected, you may need to add it manually.

### Getting Help

If you encounter issues with the migration process, please:

1. Run the migration with verbose logging:
   ```bash
   vcspull migrate -d -c
   ```

2. Check the output for error messages and warnings

3. If you need to report an issue, include:
   - Your original configuration (with sensitive information redacted)
   - The error message or unexpected behavior
   - The version of vcspull you're using

```{currentmodule} libtmux

```

```{include} ../MIGRATION

```
