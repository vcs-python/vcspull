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

## Subgroup targeting

Use slash notation to target a specific subgroup or sub-subgroup directly:

```console
$ vcspull import gl my-group/my-subgroup \
    --mode org \
    --workspace ~/code/
```

```console
$ vcspull import gl my-group/my-subgroup/my-leaf \
    --mode org \
    --workspace ~/code/
```

The `TARGET` argument accepts any depth of slash-separated group path.

## Group flattening

When importing a GitLab group with `--mode org`, vcspull preserves subgroup
structure as nested workspace directories by default. Use `--flatten-groups` to
place all repositories directly in the base workspace:

```console
$ vcspull import gl my-group \
    --mode org \
    --workspace ~/code/ \
    --flatten-groups
```

### Workspace structure by target and flag

Given a group tree `my-group → sub → leaf`, importing from `~/code/`:

| Target | `--flatten-groups` | Workspace sections written |
|--------|:-----------------:|---------------------------|
| `my-group` | no | `~/code/`, `~/code/sub/`, `~/code/sub/leaf/` |
| `my-group` | yes | `~/code/` only |
| `my-group/sub` | no | `~/code/`, `~/code/leaf/` |
| `my-group/sub` | yes | `~/code/` only |
| `my-group/sub/leaf` | no | `~/code/` only (leaf — no further nesting) |
| `my-group/sub/leaf` | yes | `~/code/` only |

When the target is already the deepest group (a leaf), `--flatten-groups` has
no effect — all repositories already land in the base workspace.

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
$ vcspull import gl myuser --workspace ~/code/
```
