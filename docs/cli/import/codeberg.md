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

Set the token:

```console
$ export CODEBERG_TOKEN=...
```

Then import:

```console
$ vcspull import codeberg myuser --workspace ~/code/
```
