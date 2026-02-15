(cli-import-gitea)=

# vcspull import gitea

Import repositories from a self-hosted Gitea instance.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: import gitea
```

## Authentication

- **Env var**: `GITEA_TOKEN`
- **Token type**: API token with scoped permissions
- **Scope**: `read:repository` (minimum for listing repos)
- **Create at**: `https://<instance>/user/settings/applications`

```console
$ export GITEA_TOKEN=...
$ vcspull import gitea myuser -w ~/code/ --url https://git.example.com
```
