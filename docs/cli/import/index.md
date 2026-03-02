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

## Syncing existing entries

By default, repositories that already exist in your configuration are
**skipped** — even if the remote URL has changed. This prevents accidental
updates when re-importing from a service.

For example, suppose your team migrated from HTTPS to SSH. Without
`--sync`, the old HTTPS URLs stay in your config:

```vcspull-console
$ vcspull import gh myorg \
    --mode org \
    --workspace ~/code/
→ Fetching repositories from GitHub...
✓ Found 8 repositories
  + new-project [Python]
  ⊘ api-server (already in config)
  ⊘ web-frontend (already in config)
  ... and 5 more
Import 1 new repository to ~/.vcspull.yaml? [y/N]: y
✓ Added 1 repository to ~/.vcspull.yaml
! Skipped 7 existing repositories
```

Pass `--sync` to fully reconcile your config with the remote — update changed
URLs, and remove entries no longer on the remote:

```console
$ vcspull import gh myorg \
    --mode org \
    --workspace ~/code/ \
    --sync
```

`--sync` does three things:

1. **Add** new repositories (same as without `--sync`)
2. **Update URLs** for existing entries whose URL has changed
3. **Prune** entries that are no longer on the remote

When syncing, vcspull replaces only the `repo` URL. All other metadata is
preserved:

- `options` (including pins)
- `remotes`
- `shell_command_after`
- `worktrees`

For example, given this config before the import:

```yaml
~/code/:
  api-server:
    repo: "git+https://github.com/myorg/api-server.git"
    remotes:
      upstream: "git+https://github.com/upstream/api-server.git"
    shell_command_after:
      - make setup
```

After `vcspull import gh myorg --workspace ~/code/ --sync`, the `repo` URL
is updated to SSH while `remotes` and `shell_command_after` are kept:

```yaml
~/code/:
  api-server:
    repo: "git+git@github.com:myorg/api-server.git"
    remotes:
      upstream: "git+https://github.com/upstream/api-server.git"
    shell_command_after:
      - make setup
```

### Provenance tracking

When `--sync` (or `--prune`) is used, vcspull tags each imported repo with
a `metadata.imported_from` field recording the import source:

```yaml
~/code/:
  api-server:
    repo: "git+git@github.com:myorg/api-server.git"
    metadata:
      imported_from: "github:myorg"
```

The tag format is `"{service}:{target}"` — e.g. `"github:myorg"`,
`"gitlab:mygroup"`, `"codeberg:myuser"`.

Provenance tags scope the prune step: only entries tagged with the **same**
import source are candidates for removal. This means:

- Manually added repos (no `metadata.imported_from`) are never pruned
- Repos imported from a different source (e.g. `"github:other-org"`) are
  never pruned when syncing `"github:myorg"`

Pruning is **config-only** — cloned directories on disk are not deleted.

### Pruning stale entries

To remove stale entries without updating URLs, use `--prune`:

```console
$ vcspull import gh myorg \
    --mode org \
    --workspace ~/code/ \
    --prune
```

Preview what would be pruned with `--dry-run`:

```console
$ vcspull import gh myorg \
    --mode org \
    --workspace ~/code/ \
    --prune \
    --dry-run
```

`--sync` and `--prune` can be combined — `--sync` alone already includes
pruning, so `--sync --prune` behaves identically to `--sync`.

| Flags | Add new | Update URLs | Prune stale | Prune untracked |
|-------|---------|-------------|-------------|-----------------|
| (none) | yes | no | no | no |
| `--sync` | yes | yes | yes | no |
| `--prune` | yes | no | yes | no |
| `--sync --prune` | yes | yes | yes | no |
| `--sync --prune-untracked` | yes | yes | yes | yes |
| `--prune --prune-untracked` | yes | no | yes | yes |

### Pruning untracked entries

Standard `--sync` / `--prune` only removes entries tagged with the current
import source. Manually added repos — entries without any
`metadata.imported_from` tag — are left untouched. To also remove these
"untracked" entries, add `--prune-untracked`:

```console
$ vcspull import gh myorg \
    --mode org \
    --workspace ~/code/ \
    --sync \
    --prune-untracked
```

`--prune-untracked` requires `--sync` or `--prune` — it cannot be used alone.

Safety rails:

- **Pinned entries** are always preserved (regardless of provenance)
- **Entries tagged from a different source** (e.g. `"gitlab:other"`) are
  preserved — they are "tracked" by that other import
- **Only workspaces the import targets** are scanned — entries in other
  workspaces are untouched
- A **confirmation prompt** lists exactly what would be removed before
  proceeding (use `--yes` to skip, `--dry-run` to preview)

Preview with dry-run:

```console
$ vcspull import gh myorg \
    --mode org \
    --workspace ~/code/ \
    --prune \
    --prune-untracked \
    --dry-run
```

### Pin-aware behavior

Repositories protected by a pin are **exempt** from both URL updates and
pruning. The following configurations all prevent `--sync` from modifying
an entry:

- `options.pin: true` — blocks all operations
- `options.pin.import: true` — blocks import only
- `options.allow_overwrite: false` — shorthand for `pin: {import: true}`

Pinned repositories are skipped with an informational message showing the
`pin_reason` (if set):

```vcspull-console
$ vcspull import gh myorg \
    --mode org \
    --workspace ~/code/ \
    --sync
→ Fetching repositories from GitHub...
✓ Found 8 repositories
  ↻ api-server (URL changed)
  ⊘ internal-fork (pinned to company mirror)
  ... and 6 more
Import 7 repositories to ~/.vcspull.yaml? [y/N]: y
✓ Updated 6 repositories in ~/.vcspull.yaml
! Skipped 1 pinned repository
```

For example, this entry cannot be updated or pruned regardless of `--sync`:

```yaml
~/code/:
  internal-fork:
    repo: "git+ssh://git@corp.example.com/team/internal-fork.git"
    options:
      pin:
        import: true
      pin_reason: "pinned to company mirror — update manually"
```

See {ref}`config-pin` for full pin configuration.

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
