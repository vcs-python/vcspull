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

```console
$ export FORGEJO_TOKEN=...
$ vcspull import forgejo myuser -w ~/code/ --url https://forgejo.example.com
```
