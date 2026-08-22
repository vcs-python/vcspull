# AGENTS.md

vcspull manages and synchronizes many git, svn, and mercurial repositories
from a single YAML or JSON configuration file, via the `vcspull` CLI.

Follow the conventions already in the tree, and keep a change scoped to what
was asked for.

## What is here

| Path | What it is |
| ---- | ---------- |
| `src/vcspull/cli/` | CLI subcommands: `sync`, `add`, `discover`, `import`, `list`, `search`, `status`, `fmt`, `migrate`, `worktree` |
| `src/vcspull/config.py` | Load and parse the YAML/JSON workspace configuration |
| `src/vcspull/_internal/` | Implementation detail; no stability guarantee across versions |
| `src/vcspull/exc.py` | Exceptions |
| `src/vcspull/log.py` | CLI logging setup and formatters |
| `tests/` | pytest suite |
| `docs/` | Sphinx documentation source |
| `docs/_ext/` | Custom Pygments lexers and doctested extension code |
| `scripts/` | Runtime dependency smoke test |
| `CHANGES` | Changelog, rendered at `docs/history.md` |

## Which policy applies

- Documentation, user-facing text, `CHANGES`, release notes, commit messages,
  docstrings, and source comments:
  [.github/WRITING.md](.github/WRITING.md)
- Environment, the gates, tests, documentation builds, releases, and pull
  requests: [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md)

Each of those is the single home for its subject. Where a rule seems to be
stated twice, the file listed above is the one that governs.

## Change discipline

- Make the smallest coherent change that solves the verified problem; keep
  unrelated cleanup out of it.
- Reuse an existing file, helper, API, or test before adding a new one.
- Add a file only for a durable boundary — a distinct responsibility,
  independent reuse, or splitting an oversized module — not for a single-use
  helper or a one-line re-export.
- Add a test for every user-visible behaviour change, and a `CHANGES` entry
  for every change to the public API, CLI, configuration, or output.
- A passing gate is evidence only once it has been shown capable of failing.
  Pair a new test with a deliberate break that proves it bites.

vcspull's release cadence is coupled to `libvcs`, which does the actual git,
svn, and hg work; `[tool.uv.exclude-newer-package]` in `pyproject.toml`
exempts `libvcs` and the documentation toolchain from the `exclude-newer`
cooldown so `uv sync` is never blocked on it. Never discard uncommitted work
without an explicit `--write`/`--yes`/confirmation from the caller — see
[the destructive-operation invariant](.github/WRITING.md#cli-output-and-error-messages).

## References

- Changelog: `CHANGES` (rendered at <https://vcspull.git-pull.com/history.html>)
- Documentation: <https://vcspull.git-pull.com>
- Upstream VCS layer: [libvcs](https://github.com/vcs-python/libvcs)
