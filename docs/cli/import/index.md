(cli-import)=

# vcspull import

The `vcspull import` command bulk-imports repositories from remote hosting
services into your vcspull configuration. It connects to the service API,
fetches a list of repositories, and writes them to your config file in a single
step.

Supported services: **GitHub**, **GitLab**, **Codeberg**, **Gitea**,
**Forgejo**, and **AWS CodeCommit**.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: import
    :nosubcommands:
    :nodescription:
```

Choose a service subcommand for details:

- {ref}`cli-import-github` — GitHub or GitHub Enterprise
- {ref}`cli-import-gitlab` — GitLab (gitlab.com or self-hosted)
- {ref}`cli-import-codeberg` — Codeberg
- {ref}`cli-import-gitea` — Self-hosted Gitea instance
- {ref}`cli-import-forgejo` — Self-hosted Forgejo instance
- {ref}`cli-import-codecommit` — AWS CodeCommit

## Basic usage

Import all repositories for a GitHub user into a workspace:

```vcspull-console
$ vcspull import github myuser --workspace ~/code/
→ Fetching repositories from GitHub...
✓ Found 12 repositories
  + project-a [Python]
  + project-b [Rust] ★42
  + dotfiles
  ... and 9 more
Import 12 repositories to ~/.vcspull.yaml? [y/N]: y
✓ Added 12 repositories to ~/.vcspull.yaml
```

## Supported services

| Service    | Aliases          | Self-hosted          | Auth env var(s)                   |
|------------|------------------|----------------------|-----------------------------------|
| GitHub     | `github`, `gh`   | `--url`              | `GITHUB_TOKEN` / `GH_TOKEN`      |
| GitLab     | `gitlab`, `gl`   | `--url`              | `GITLAB_TOKEN` / `GL_TOKEN`      |
| Codeberg   | `codeberg`, `cb` | No                   | `CODEBERG_TOKEN` / `GITEA_TOKEN` |
| Gitea      | `gitea`          | `--url` (required)   | `GITEA_TOKEN`                     |
| Forgejo    | `forgejo`        | `--url` (required)   | `FORGEJO_TOKEN` / `GITEA_TOKEN`  |
| CodeCommit | `codecommit`, `cc`, `aws` | N/A          | AWS CLI credentials               |

For Gitea and Forgejo, `--url` is required because there is no default
instance.

```{toctree}
:maxdepth: 1
:hidden:

github
gitlab
codeberg
gitea
forgejo
codecommit
```

## Import modes

### User mode (default)

Fetch all repositories owned by a user:

```console
$ vcspull import gh myuser --workspace ~/code/
```

### Organization mode

Fetch repositories belonging to an organization or group:

```console
$ vcspull import gh my-org \
    --mode org \
    --workspace ~/code/
```

For GitLab, subgroups are supported with slash notation:

```console
$ vcspull import gl my-group/sub-group \
    --mode org \
    --workspace ~/code/
```

### Search mode

Search for repositories matching a query:

```console
$ vcspull import gh django \
    --mode search \
    --workspace ~/code/ \
    --min-stars 100
```

## Filtering

Narrow results with filtering flags:

```console
$ vcspull import gh myuser \
    --workspace ~/code/ \
    --language python
```

```console
$ vcspull import gh myuser \
    --workspace ~/code/ \
    --topics cli,automation
```

```console
$ vcspull import gh django \
    --mode search \
    --workspace ~/code/ \
    --min-stars 50
```

Include archived or forked repositories (excluded by default):

```console
$ vcspull import gh myuser \
    --workspace ~/code/ \
    --archived \
    --forks
```

Limit the number of repositories fetched:

```console
$ vcspull import gh myuser \
    --workspace ~/code/ \
    --limit 50
```

```{note}
Not all filters work with every service. For example, `--language` may not
return results for GitLab or CodeCommit because those APIs don't expose
language metadata. vcspull warns when a filter is unlikely to work.
```

## Output formats

Human-readable output (default):

```console
$ vcspull import gh myuser --workspace ~/code/
```

JSON for automation:

```console
$ vcspull import gh myuser \
    --workspace ~/code/ \
    --json
```

NDJSON for streaming:

```console
$ vcspull import gh myuser \
    --workspace ~/code/ \
    --ndjson
```

## Dry runs and confirmation

Preview what would be imported without writing to the config file:

```console
$ vcspull import gh myuser \
    --workspace ~/code/ \
    --dry-run
```

Skip the confirmation prompt (useful for scripts):

```console
$ vcspull import gh myuser \
    --workspace ~/code/ \
    --yes
```

## Configuration file selection

vcspull writes to `~/.vcspull.yaml` by default. Override with `-f/--file`:

```console
$ vcspull import gh myuser \
    --workspace ~/code/ \
    --file ~/configs/github.yaml
```

## Protocol selection

SSH clone URLs are used by default. Switch to HTTPS with `--https`:

```console
$ vcspull import gh myuser \
    --workspace ~/code/ \
    --https
```

## Self-hosted instances

Point to a self-hosted GitHub Enterprise, GitLab, Gitea, or Forgejo instance
with `--url`:

```console
$ vcspull import gitea myuser \
    --workspace ~/code/ \
    --url https://git.example.com
```

## Authentication

vcspull reads API tokens from environment variables. Use `--token` to override.
Environment variables are preferred for security. See each service page for
details.

| Service    | Env var(s)                       | Token type            | Min scope / permissions                                          |
|------------|----------------------------------|-----------------------|------------------------------------------------------------------|
| GitHub     | `GITHUB_TOKEN` / `GH_TOKEN`     | PAT (classic or fine) | None (public), `repo` (private)                                  |
| GitLab     | `GITLAB_TOKEN` / `GL_TOKEN`     | PAT                   | `read_api`                                                       |
| Codeberg   | `CODEBERG_TOKEN` / `GITEA_TOKEN` | API token            | None (public), any token (private)                               |
| Gitea      | `GITEA_TOKEN`                    | API token             | `read:repository`                                                |
| Forgejo    | `FORGEJO_TOKEN` / `GITEA_TOKEN`  | API token            | `read:repository`                                                |
| CodeCommit | AWS CLI credentials              | IAM access key        | `codecommit:ListRepositories`, `codecommit:BatchGetRepositories` |

## After importing

1. Run `vcspull fmt --write` to normalize and sort the configuration (see
   {ref}`cli-fmt`).
2. Run `vcspull list` to verify the imported entries (see {ref}`cli-list`).
3. Run `vcspull sync` to clone the repositories (see {ref}`cli-sync`).
