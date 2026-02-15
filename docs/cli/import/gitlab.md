(cli-import-gitlab)=

# vcspull import gitlab

Import repositories from GitLab or a self-hosted GitLab instance.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: import gitlab
```

## Group flattening

When importing a GitLab group with `--mode org`, vcspull preserves subgroup
structure as nested workspace directories by default. Use `--flatten-groups` to
place all repositories directly in the base workspace:

```console
$ vcspull import gl my-group --mode org -w ~/code/ --flatten-groups
```

## Authentication

- **Env vars**: `GITLAB_TOKEN` (primary), `GL_TOKEN` (fallback)
- **Token type**: Personal access token
- **Scope**: `read_api` (minimum for listing projects; **required** for search
  mode)
- **Create at**: <https://gitlab.com/-/user_settings/personal_access_tokens>
  (self-hosted: `https://<instance>/-/user_settings/personal_access_tokens`)

Set the token:

```console
$ export GITLAB_TOKEN=glpat-...
```

Then import:

```console
$ vcspull import gl myuser -w ~/code/
```
