(cli-import-forgejo)=

# vcspull import forgejo

Import repositories from a self-hosted Forgejo instance.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: import forgejo
```

## Authentication

- **Env vars**: `FORGEJO_TOKEN` (primary; matched when hostname contains
  "forgejo"), `GITEA_TOKEN` (fallback)
- **Token type**: API token
- **Scope**: `read:repository`
- **Create at**: `https://<instance>/user/settings/applications`

Set the token:

```console
$ export FORGEJO_TOKEN=...
```

Then import:

```console
$ vcspull import forgejo myuser \
    --workspace ~/code/ \
    --url https://forgejo.example.com
```
