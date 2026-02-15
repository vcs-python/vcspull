(cli-import-codeberg)=

# vcspull import codeberg

Import repositories from Codeberg.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: import codeberg
```

## Authentication

- **Env vars**: `CODEBERG_TOKEN` (primary), `GITEA_TOKEN` (fallback)
- **Token type**: API token
- **Scope**: no scopes needed for public repos; token required for private repos
- **Create at**: <https://codeberg.org/user/settings/applications>

```console
$ export CODEBERG_TOKEN=...
$ vcspull import codeberg myuser -w ~/code/
```
