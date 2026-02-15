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
```

## Basic usage

Import all repositories for a GitHub user into a workspace:

```vcspull-console
$ vcspull import github myuser -w ~/code/
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

## Import modes

### User mode (default)

Fetch all repositories owned by a user:

```console
$ vcspull import gh myuser -w ~/code/
```

### Organization mode

Fetch repositories belonging to an organization or group:

```console
$ vcspull import gh my-org --mode org -w ~/code/
```

For GitLab, subgroups are supported with slash notation:

```console
$ vcspull import gl my-group/sub-group --mode org -w ~/code/
```

### Search mode

Search for repositories matching a query:

```console
$ vcspull import gh django --mode search -w ~/code/ --min-stars 100
```

## Filtering

Narrow results with filtering flags:

```console
$ vcspull import gh myuser -w ~/code/ --language python
```

```console
$ vcspull import gh myuser -w ~/code/ --topics cli,automation
```

```console
$ vcspull import gh django --mode search -w ~/code/ --min-stars 50
```

Include archived or forked repositories (excluded by default):

```console
$ vcspull import gh myuser -w ~/code/ --archived --forks
```

Limit the number of repositories fetched:

```console
$ vcspull import gh myuser -w ~/code/ --limit 50
```

```{note}
Not all filters work with every service. For example, `--language` may not
return results for GitLab or CodeCommit because those APIs don't expose
language metadata. vcspull warns when a filter is unlikely to work.
```

## Output formats

Human-readable output (default):

```console
$ vcspull import gh myuser -w ~/code/
```

JSON for automation:

```console
$ vcspull import gh myuser -w ~/code/ --json
```

NDJSON for streaming:

```console
$ vcspull import gh myuser -w ~/code/ --ndjson
```

## Dry runs and confirmation

Preview what would be imported without writing to the config file:

```console
$ vcspull import gh myuser -w ~/code/ --dry-run
```

Skip the confirmation prompt (useful for scripts):

```console
$ vcspull import gh myuser -w ~/code/ --yes
```

## Configuration file selection

vcspull writes to `~/.vcspull.yaml` by default. Override with `-f/--file`:

```console
$ vcspull import gh myuser -w ~/code/ -f ~/configs/github.yaml
```

## Protocol selection

SSH clone URLs are used by default. Switch to HTTPS with `--https`:

```console
$ vcspull import gh myuser -w ~/code/ --https
```

## Group flattening

When importing a GitLab group with `--mode org`, vcspull preserves subgroup
structure as nested workspace directories by default. Use `--flatten-groups` to
place all repositories directly in the base workspace:

```console
$ vcspull import gl my-group --mode org -w ~/code/ --flatten-groups
```

## AWS CodeCommit

CodeCommit does not require a target argument. Use `--region` and `--profile`
to select the AWS environment:

```console
$ vcspull import codecommit -w ~/code/ --region us-east-1 --profile work
```

## Self-hosted instances

Point to a self-hosted GitHub Enterprise, GitLab, Gitea, or Forgejo instance
with `--url`:

```console
$ vcspull import gitea myuser -w ~/code/ --url https://git.example.com
```

## Authentication

vcspull reads API tokens from environment variables. Use `--token` to override.
Environment variables are preferred for security.

### GitHub

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

### GitLab

- **Env vars**: `GITLAB_TOKEN` (primary), `GL_TOKEN` (fallback)
- **Token type**: Personal access token
- **Scope**: `read_api` (minimum for listing projects; **required** for search
  mode)
- **Create at**: <https://gitlab.com/-/user_settings/personal_access_tokens>
  (self-hosted: `https://<instance>/-/user_settings/personal_access_tokens`)

```console
$ export GITLAB_TOKEN=glpat-...
$ vcspull import gl myuser -w ~/code/
```

### Codeberg

- **Env vars**: `CODEBERG_TOKEN` (primary), `GITEA_TOKEN` (fallback)
- **Token type**: API token
- **Scope**: no scopes needed for public repos; token required for private repos
- **Create at**: <https://codeberg.org/user/settings/applications>

```console
$ export CODEBERG_TOKEN=...
$ vcspull import codeberg myuser -w ~/code/
```

### Gitea

- **Env var**: `GITEA_TOKEN`
- **Token type**: API token with scoped permissions
- **Scope**: `read:repository` (minimum for listing repos)
- **Create at**: `https://<instance>/user/settings/applications`

```console
$ export GITEA_TOKEN=...
$ vcspull import gitea myuser -w ~/code/ --url https://git.example.com
```

### Forgejo

- **Env vars**: `FORGEJO_TOKEN` (primary; matched when hostname contains
  "forgejo"), `GITEA_TOKEN` (fallback)
- **Token type**: API token
- **Scope**: `read:repository`
- **Create at**: `https://<instance>/user/settings/applications`

```console
$ export FORGEJO_TOKEN=...
$ vcspull import forgejo myuser -w ~/code/ --url https://forgejo.example.com
```

### AWS CodeCommit

- **Auth**: AWS CLI credentials (`aws configure`) — no token env var
- **CLI args**: `--region`, `--profile`
- **IAM permissions required**:
  - `codecommit:ListRepositories` (resource: `*`)
  - `codecommit:BatchGetRepositories` (resource: repo ARNs or `*`)
- **Dependency**: AWS CLI must be installed (`pip install awscli`)

```console
$ aws configure
$ vcspull import codecommit -w ~/code/ --region us-east-1
```

### Summary

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
