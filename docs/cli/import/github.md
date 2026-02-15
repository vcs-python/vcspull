(cli-import-github)=

# vcspull import github

Import repositories from GitHub or GitHub Enterprise.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: import github
```

## Authentication

- **Env vars**: `GITHUB_TOKEN` (primary), `GH_TOKEN` (fallback)
- **Token type**: Personal access token (classic) or fine-grained PAT
- **Permissions**:
  - Classic PAT: no scopes needed for public repos; `repo` scope for private
    repos; `read:org` for org repos
  - Fine-grained PAT: "Metadata: Read-only" for public; add "Contents:
    Read-only" for private
- **Create at**: <https://github.com/settings/tokens>

```console
$ export GITHUB_TOKEN=ghp_...
$ vcspull import gh myuser -w ~/code/
```
