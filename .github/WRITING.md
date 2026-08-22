# Writing

How this project writes prose, for humans and agents alike. It governs
`README.md`, `CHANGES`, release notes, commit messages, CLI and help text,
error messages, docstrings, source comments, and migration guides — every
surface a reader reaches.

For environment setup, the gates, and pull request workflow, see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Voice

Three surfaces, one voice. A docstring says what a caller may rely on; a
`CHANGES` entry says what changed; prose says what happens. All three are
present tense, lead with the thing being described, and stop. Why it was built
that way belongs in the commit message, which is timestamped and attached to
the diff.

The most useful editing operation is deleting the introductory sentence.

Lead with verbs and name concrete things. Put identifiers in backticks. Prefer
short declarative sentences, one operational fact each. Do not explain Python
to Python developers; do explain this project's semantics.

Type annotations describe shape. Documentation describes meaning. A sentence
that restates a signature has said nothing.

Use MUST, SHOULD, and MAY only where the normative sense is meant. Say what
actually happens rather than that something is "supported".

| Instead of                       | Prefer                             |
| --------------------------------- | ----------------------------------- |
| "We added…"                      | "`vcspull sync` now accepts…"       |
| "New and improved"               | "`vcspull list` now…"               |
| "powerful", "seamless"           | state the capability                |
| "easily", "simply", "just"       | omit                                |
| "simple", "obvious", "intuitive" | omit                                 |
| "robust"                         | name the failure that is handled    |
| "comprehensive"                  | name what is covered                |
| "production-ready"               | state the guarantee                 |
| "optimized", "blazingly fast"    | give the magnitude                  |
| "various fixes"                  | name the components                 |
| "under the hood"                 | omit unless observable              |
| "please note that", "note that"  | state the fact                      |
| "leverage", "utilize"            | "use"                                |
| "delve into"                     | "read", or omit                     |
| "best practices"                 | name the practice                   |
| "in order to"                    | "to"                                 |

## Who you are writing for

The default reader runs `vcspull` from a shell and keeps a configuration file
in YAML or JSON — `~/.vcspull.yaml` or a file under `~/.config/vcspull/`. They
are fluent in git (often hg or svn too) and comfortable at a prompt, but you
cannot assume they read Python, know libvcs, or have heard of `load_configs`,
`extract_repos`, or the internal config reader. Serve them first.

A second, smaller reader writes Python: code against `vcspull.config`, the
modules under `docs/internals/`, or a contribution. Serve them too, but mark
their material opt-in — "for the rarer cases", "advanced" — so the default
reader knows they can stop. Never make the common case pay a comprehension tax
for the advanced one.

Rules that follow:

- **Second person, present tense, active.** "You pin the entry", not "The
  entry is pinned". Address the reader who is doing the thing.
- **Concept before configuration or API surface.** Open by saying what the
  thing *is* and what it does for the reader. The YAML keys or the function
  signature are the last detail they need, not the first. A page that opens
  with "set these keys" or a signature has buried the idea under its
  mechanics.
- **Say when they can stop.** Lead with the default and the reassurance: most
  readers never touch this, the defaults work, everything here is optional.
  Let a skimmer leave after one paragraph.
- **Grant permission, do not demand attention.** "Reach for this when…" tells
  readers they are in the right place without implying they must read on.
- **Progressive disclosure.** Order by how many readers need it: the plain
  `vcspull sync '*'`, then the one flag a few will tune, then the
  per-repository `options:` block, then the Python API. Each step is for a
  smaller audience than the last.
- **Lean on the pipeline.** The reader thinks configuration file → workspace
  root → repository entry → sync; reinforce that chain when you explain where
  a key lives or which repositories a command touches. It is the mental model
  the whole tool hangs on.
- **Name the trade-off.** If an option costs something — `options.shallow`
  trades git history for disk and time, `--exit-on-error` stops the whole run
  at the first failure — say so, and say what it buys. State it; do not sell
  it.
- **Frame by concept, not by mechanism.** Do not headline a feature as "the
  `--dry-run` flag" or "the `options:` block" in prose; that names the
  implementation surface, which is the reader's last concern. Name the
  concept: previewing a sync, pinning an entry. The mechanics vocabulary — a
  pin-key table, the generated flag listing — is correct in a reference table,
  and only there.

### What stays precise

Warm the framing, never the facts. Config search-order lists, pin-key tables,
exact warning strings (`No repo found in config(s) for …`), YAML schema
fragments, exit-status meanings, and class or function cross-references carry
meaning in their exact form — leave them alone. The friendly voice belongs in
the sentences *around* a precise block, introducing it, not inside it
paraphrasing it into vagueness.

## README

A README is the shortest path from "what is this?" to competent use, not the
project's autobiography.

The first sentence is a contract. It says what abstraction the reader has been
handed, concretely enough to tell this package apart from the neighbouring
one.

Get to a runnable command or snippet before anything the reader can skip. A
logo, a mission statement, a comparison matrix and three paragraphs of history
in front of the install line all cost the same thing.

State the minimum Python version and meaningful platform constraints in prose,
not only in badges. `requires-python` in `pyproject.toml` is the authority;
the README must agree with it.

Name the distribution, the import, and the executable separately wherever
they differ. That distinction prevents a Python-specific class of confusion.

Examples are executable or, where the file is not collected by pytest,
honest — never `vcspull <some-options>`. See
[Documented examples that run](#documented-examples-that-run) for which
blocks are checked and how.

Document the semantic model, not the flag list. `--help` already enumerates
flags; what it cannot say is precedence, filesystem effects, what goes to
stdout versus stderr, and what a non-zero exit means.

State defaults explicitly — defaults are API. State negative guarantees where
they exist: "does not modify your configuration file without `--write` or
confirmation", "no network access", "never discards uncommitted changes".
They establish boundaries faster than any amount of description.

Headings stay conventional and stable, because people deep-link them. Badges
are few and load-bearing.

## CLI output and error messages

One console script ships from this package — `vcspull`
(`[project.scripts]` in `pyproject.toml`) — with subcommands for `sync`,
`add`, `discover`, `import`, `list`, `search`, `status`, `fmt`, `migrate`,
`worktree`, and `completion`. The conventions below apply to all of them.

**Exit statuses.**

| Status | Meaning |
| ------ | ------- |
| `0` | Success. This includes `vcspull sync` runs where some repositories failed but `--exit-on-error`/`-x` was not passed — the summary reports the failures, but the process exits clean so a script can inspect per-repository results instead of aborting the batch. |
| `1` | A fatal error: an unrecoverable condition (bad config, `import` handler failure), or `--exit-on-error` stopped a `sync` at the first failure. |
| `2` | argparse rejected the arguments — an unknown flag, a missing required value, or similar usage error. |
| `130` | Interrupted by `SIGINT` (Ctrl-C). On POSIX this is a real signal death (`WIFSIGNALED`), not a plain `SystemExit`, so shells stop a `cmd1; cmd2` sequence the way they would for any other signalled child. |

**stdout versus stderr.** vcspull's own log messages — the `INFO`/`WARNING`
lines a normal run prints — write to stdout by design, interleaved with the
human-readable summary. `--json` and `--ndjson` payloads also write to
stdout. Only three things go to stderr: argparse usage errors, a fatal
`SystemExit` message, and the "Interrupted by user" notice a Ctrl-C prints.
Do not move CLI log output to stderr without updating this table — scripts
that parse stdout depend on the current split.

**Message style.** Lowercase, past tense for events: `"repository cloned"`,
`"vcs command failed"`. No trailing punctuation. Keep the message short; put
identifiers and structured detail in the logging call's `extra`, not the
message string.

**Destructive-operation invariant.** vcspull never discards work without an
explicit signal from the caller:

- Commands that write a configuration file (`add`, `discover`, `import`,
  `fmt --write`) prompt for confirmation before writing, or skip the prompt
  only when `--yes` is passed.
- `fmt` and `migrate` default to a preview; they touch disk only when
  `--write` is passed.
- `--dry-run` never touches disk, on any command that supports it.
- `vcspull sync --include-worktrees` refuses to update a worktree with
  uncommitted changes rather than overwrite them; if the dirty check itself
  fails, vcspull treats the worktree as dirty rather than risk data loss.
- Batch `sync` sets `GIT_TERMINAL_PROMPT=0` so a missing credential fails the
  repository instead of blocking the whole run on stdin.

## Documented examples that run

Examples in this project are tests where the file they live in is collected —
and vcspull collects only part of its documentation, so read this section
before assuming a block runs.

**A fence tag is cosmetic. Only a `>>> ` prompt executes, and only inside a
collected file.** A block written as

    ```python
    server = Server()
    ```

is prose that looks like a test. Nothing collects it, nothing runs it, and it
can be wrong for years. The same block written with prompts is a test — *if*
its file is collected:

    ```python
    >>> server = Server()
    ```

**Where doctests run.** `pyproject.toml` sets
`addopts = "... --doctest-modules"` and `testpaths = ["src/vcspull", "tests",
"docs/_ext", "scripts"]`. A `>>> ` block in a docstring under `src/vcspull`,
`docs/_ext`, or `scripts` is collected and executed by `pytest`. The root
`conftest.py` wires libvcs's `add_doctest_fixtures` into every doctest, so a
docstring example may use `tmp_path`, `create_git_remote_repo` (and
`create_git_remote_repo_bare`), `example_git_repo`, `create_svn_remote_repo`
(and `_bare`), and `create_hg_remote_repo` (and `_bare`) without importing
them — each pair is only added when the matching VCS binary (`git`, `svn` +
`svnadmin`, `hg`) is on `PATH`, so a doctest using one must tolerate that VCS
being absent in some CI environments.

**`README.md` and `docs/*.md` pages are not doctested.** Neither path is in
`testpaths`, so a `>>> ` prompt added to either one is not collected and does
not run — this repository does not use doctested Markdown. Adding one is not
a mistake that breaks anything, but it also does not add the test coverage a
contributor might expect; do not claim a README or docs example is "tested"
on that basis.

**`docs/*.md` command examples are checked structurally instead.** Two pytest
files harvest every `vcspull …` command shown in the docs and in the CLI's own
help text, then feed each one to the real argparse parser
(`create_parser(return_subparsers=False).parse_args(...)`) and fail if
argparse rejects it:

- `tests/docs/test_markdown_conventions.py` reads every Markdown file under
  `docs/`, requires shell commands to use `console` fences (not `bash`, `sh`,
  `shell`, or `zsh`), requires a plain `console` fence to hold only the
  command (mixed output belongs in `vcspull-console` or `vcspull-output`
  instead — see [Markdown](#markdown-and-cross-references)), and parses every
  `$ vcspull …` line it finds in a `console` or `vcspull-console` fence.
- `tests/cli/test_help_examples.py` does the same for every `vcspull …` line
  embedded in the CLI's `*_DESCRIPTION` help-text constants in
  `src/vcspull/cli/__init__.py`.

This catches a renamed flag or a typo'd subcommand. It does **not** run the
command or check its output — a `vcspull sync --dry-run "*"` example that
parses fine can still show output that no longer matches a real run.

**`README.md` examples are checked by neither mechanism.** `README.md` lives
outside `docs/`, so the harvesters above never see it, and it is not in
`testpaths`. A `vcspull …` command in the README is verified only by whoever
last copied it from a real terminal. Copy the command and its output from an
actual run, and re-check the block whenever the flags or output it shows
change — see
[Examples that stay honest](#examples-that-stay-honest).

**`# doctest: +SKIP` is not permitted** in the doctests that do run. It is a
workaround that tests nothing. Use the fixtures, or gate on the VCS binary the
way `add_doctest_fixtures` already does.

**Do not downgrade a doctest to a non-executed block to make it pass.** A
`.. code-block::` or an unprompted fence does not run. If an example cannot
pass, fix the example or fix the code.

**Option flags.** `ELLIPSIS` and `NORMALIZE_WHITESPACE` are enabled globally
for the doctests that do run, so `...` elides variable output and whitespace
differences do not fail a comparison. Reach for an inline `# doctest: +FLAG`
only for the block that needs it.

**Docstring examples** use the NumPy `Examples` section:

    Examples
    --------
    >>> from vcspull.config import extract_repos
    >>> config = {'~/code/': {'myrepo': 'git+https://github.com/user/repo'}}
    >>> repos = extract_repos(config)
    >>> len(repos)
    1

### Examples that stay honest

Sphinx does not execute code blocks under `docs/`, and neither harvester above
checks output. Honesty there is manual: copy commands and output from a run
you actually made, keep YAML consistent with the real schema (workspace root
→ repository entry), and re-check a page's examples whenever the flags or
keys they show change.

## The changelog

`CHANGES` is the changelog. Not `CHANGELOG.md`. It is rendered as the
project's changelog page (`docs/history.md` is a bare
` ```{include} ../CHANGES ``` `). It is modeled on Django's release-notes
shape — deliverables get titles and prose, not bullets.

A ledger, not a narrative. It is scanned, and the question a reader is asking
is whether an entry affects them.

**Release entry boilerplate.** Every release header is
`## vcspull vX.Y.Z (YYYY-MM-DD)` — note the `v` prefix on the version. The
file opens with a `## vcspull vX.Y.Z (unreleased)` placeholder block fenced by
`<!-- KEEP THIS PLACEHOLDER ... -->` and `<!-- END PLACEHOLDER ... -->` HTML
comments. New entries land immediately below the `END` marker, never above
it.

**Open with a multi-sentence lead paragraph.** Plain prose, no italic. Open
with the version as sentence subject ("vcspull vX.Y.Z ships …") so the lead is
self-contained when excerpted. Two to four sentences telling the reader what
shipped and who cares — user-visible takeaways, not internal mechanism.
Cross-reference detail docs with `{ref}` to keep the lead compact.

**Unreleased entries carry no lead paragraph and no version summary.**
Sections only (`### Breaking changes`, `### What's new` deliverables,
`### Fixes`, …). Speaking for the release — what the version "is", "ships",
or "focuses on" — is presumptuous before its scope is final. Only the person
cutting the release writes that, and only when the release is actually
happening. Never write or edit a lead paragraph from a feature branch, and
never ask or imply that a release should happen.

**Each deliverable is a section, not a bullet.** Inside `### What's new`,
every distinct deliverable gets a `#### Deliverable title (#NN)` heading
naming it in user vocabulary, followed by one to three prose paragraphs
explaining what shipped. Do not wrap a paragraph in `- ` — bullets are for
enumerable lists, not paragraph containers. Cross-link detail docs
(`See {ref}\`foo\` for details.`) so prose stays focused.

**The deliverable test.** Before writing an entry, ask: "What's the
deliverable, in user vocabulary?" If you cannot answer in one sentence, the
entry is not ready. Mechanism — helper internals, byte counters, schema
validation locations — belongs in PR descriptions and code comments, not the
changelog.

**Fixed subheadings**, in this order when present: `### Breaking changes`,
`### Dependencies`, `### What's new`, `### Fixes`, `### Documentation`,
`### Development`. Dev tooling (helper scripts, internal automation) lives
under `### Development`. For breaking changes, show the migration path with
concrete inline code (a `# Before` / `# After` fenced block). Dependency floor
bumps use the form ``Minimum `pkg>=X.Y.Z` (was `>=X.Y.W`)``.

**PR refs `(#NN)`** sit in each deliverable's `####` heading.

**When bullets are appropriate.** Catch-all sections (`### Fixes`,
occasionally `### Documentation`) with three or more genuinely small items use
bullets — one line each, never paragraphs. If a bullet swells past two lines,
promote it to a `#### Title (#NN)` heading with prose body.

**Anti-patterns.** Fragile metrics that go stale silently — token ceilings,
third-party version pins, percent benchmarks, exact byte counts. Describe the
capability, not the math. Internal jargon: private symbols (leading-underscore
identifiers), algorithm names exposed for the first time, backend scaffolding.
Walls of text dressed up as bullets. Breaking changes buried mid-entry instead
of given their own subheading at the top.

**Summarizing `CHANGES` on request.** When asked what changed in the latest
version, lead with the entry's lead paragraph (paraphrased if needed),
followed by each `####` deliverable heading under `### What's new` with a
one-sentence summary. Cite `(#NN)` only if source links are requested. Do not
invent versions, dates, or numbers not present in `CHANGES`, and do not quote
line numbers or file offsets — those shift as the file evolves.

## Release notes

`CHANGES` is the permanent ledger; a release page is editorial. Lead with one
paragraph naming the headline change, then three to five highlights, then link
the full changelog.

Numbers over adjectives. "Cold start 41 ms to 6 ms" is a sentence; "much
faster startup" is a smell.

A list of merged commit subjects is a merge log wearing a release-note hat.
Put the hand-written highlights above it.

Versions are PEP 440 identifiers. Semantic-versioning meaning is applied to
the documented public API — which includes command names, options, exit
statuses, configuration keys, environment variables, and serialized formats,
not only imported Python symbols.

## Docstrings

The prime directive: never restate the type. The annotation is the source of
truth; the docstring carries what the annotation cannot.

This is documentation debt wearing a docstring:

    def get_id(repo: Repo) -> str:
        """Get the repo's identifier.

        Parameters
        ----------
        repo : Repo
            The repo.

        Returns
        -------
        str
            The identifier.
        """

Document instead the dimensions the type system cannot encode:

- **Mutation.** What it changes in place.
- **Ownership.** What the caller must close, release, or keep alive.
- **Ordering.** Whether results come back in a guaranteed order.
- **Timing.** What has finished by the time the call returns.
- **Failure.** Which exceptions are raised and what triggers each.
- **Idempotence.** Whether calling twice does anything the second time.
- **Concurrency.** Whether calls are coalesced, queued, or independent.
- **Units and ranges.** What a number means and what values are accepted.
- **Boundary behaviour.** What zero, empty, and the maximum do.
- **Platform.** Behaviour that differs by operating system, VCS binary, or
  dependency version.
- **Security boundary.** What is executed, and what is only read.

The ambiguity worth resolving by example: whether "retry three times" means
three attempts or four. State it.

The first sentence stands alone; tooling truncates there. PEP 257 applies:
triple double quotes, an imperative one-line summary ending in a period, a
blank line before any extended description. Follow the
[NumPy docstring convention](https://numpydoc.readthedocs.io/en/latest/format.html)
throughout — `ruff`'s `pydocstyle` rule enforces the `numpy` convention, so
the dialect is not relitigated in review.

**`NamedTuple` and dataclass fields document every field, in an `Attributes`
section:**

    class ConfigFileResolution(t.NamedTuple):
        """Outcome of deciding which config file ``add`` should write to.

        Attributes
        ----------
        path : pathlib.Path | None
            Config file to write to, or ``None`` when the choice was
            ambiguous.
        """

Autodoc renders every field whether or not you describe it, so an
undocumented `NamedTuple` field ships to the API docs as "Alias for field
number 0", and a dataclass field ships bare. Document all of them — a class
with three fields and two documented still ships a stub for the third.

**Every function and method carries a working doctest.** A doctest is both
documentation and a test; see
[Documented examples that run](#documented-examples-that-run) for the fixtures
available and the collection rules. If a working doctest genuinely cannot be
written for a function, say so in the pull request rather than shipping
`# doctest: +SKIP` or a silently undocumented function.

## Source comments

A comment ships only if it passes all three gates. Fail any: delete or
rewrite. Borderline: delete — borderline means the information is
reconstructible, which is what makes deletion cheap.

**Loss.** Three years from now, would losing this cost a maintainer real time
rediscovering intent, an invariant, a constraint, or a failure mode the code
and tests do not already make obvious?

**Elite.** Would SQLite, Redis, the Go standard library, or CPython write this
comment, at this length? Those projects state the constraint and stop. They do
not argue with an imagined objector.

**Upkeep.** Will it stay true without maintenance? A comment that hand-syncs a
value the code owns — a count, an offset, a line reference, a duplicated
constant — is false the first time that value moves.

### Ceiling

One or two lines. A comment reaching four is either carrying several facts, in
which case split it, or arguing, in which case cut it to the fact.

Rationale, alternatives weighed, and the story of how the code got here belong
in the commit message: timestamped, attached to the exact diff, and free to
maintain.

A comment often holds both a constraint and the deliberation that found it.
Keep the constraint, cut the deliberation. "Runs at most once per second"
survives; "this is the right trade for now" does not.

### Keep

- Why over how: upstream quirks, protocol and compatibility constraints,
  performance tradeoffs still part of the contract.
- Invariants, preconditions, ordering, lifetime, and concurrency requirements
  that types and tests cannot express.
- Code that looks wrong but is not, so a later cleanup does not reintroduce
  the bug.
- A high-level sketch of an algorithm whose local operations do not reveal the
  whole.

### Delete

- Narration of the next lines; code translated into English.
- Restated names, types, defaults, or control flow.
- Values duplicated from the code and hand-synced.
- Justification, hedging, or apology for a choice.
- Speculation about future requirements.
- History version control already holds, including commented-out code.
- Ticket and issue numbers. They say nothing to a reader without tracker
  access, and they rot when the tracker moves. Unfinished work goes in the
  tracker, not the source.
- Transient observations — "currently", "for now", "the latest release" —
  that go stale with no nearby edit.

### The upkeep gate in practice

It reaches values that track our own code. It does not reach frozen external
facts.

Bad (Delete):

    # There are 321 tests to complete for servers.

Good (Keep):

    # git < 2.28 has no --initial-branch, so this falls back to
    # renaming the branch after init.

### Documentation exception

Minimal usage examples, and parameter, return, and raises entries on public
API are exempt from the loss gate — they serve the caller, not the
maintainer. They are exempt from nothing else. Ceiling: a good man page
entry.

## Terminology and capitalization

Pick the domain noun and keep it. The pipeline is configuration file →
workspace root → repository entry → sync; use those four terms and no others
for those four things. Do not call a repository entry a "checkout" in one
paragraph and an "entry" in the next, and do not alternate "sync" with
"clone/update", "pull", or "fetch" for the CLI operation — those words name
what a single sync may do internally (clone if absent, update if present),
not the command itself.

Stable vocabulary is what makes search, deep links, and an agent's retrieval
work at all.

Python and PyPI keep their own capitalisation. Distribution names are written
as they are published.

Do not write counts into prose — how many symbols exist, how many tests there
are. They go stale silently and no reader needs them. Counts that pin a
fixture or guard an invariant are different, and belong in code.

## Markdown and cross-references

Prose wraps at 80 columns. Table rows, badge lines, and long links are
exempt, because breaking them harms rendering. A pull request or issue body
does not wrap at all: GitHub renders a single newline as a space in a file
and as a line break in a comment, so a wrapped comment body arrives as ragged
stubs.

GitHub alert blocks — `> [!NOTE]`, `> [!WARNING]` — render as literal text
outside GitHub, so reserve them for at most one load-bearing warning per
document. Write the sentence so it carries the fact on its own, and a
renderer that drops the marker loses nothing.

Do not use a local absolute path or an email address in anything published.

**Console block flavors.** Three, and they are not interchangeable:
` ```console ` for a command at a `$` prompt and nothing else,
` ```vcspull-console ` for a command plus vcspull's own styled output, and
` ```vcspull-output ` for output alone. The last two are custom Pygments
lexers registered from `docs/_ext`. `tests/docs/test_markdown_conventions.py`
enforces the split — see
[Documented examples that run](#documented-examples-that-run).

**Reference blocks are generated, never paraphrased.** CLI pages embed the
live parser with an `{eval-rst}` block wrapping `.. argparse::`, and the
`docs/internals/api/**` pages document modules with `.. automodule::`.
Introduce them in prose; a sentence that restates their content will drift
out of sync with the code that generates them.

**MyST roles.** Any class, method, function, exception, or attribute that has
its own rendered page is cited with the matching role — `{class}`, `{meth}`,
`{func}`, `{exc}`, `{attr}` — never with plain backticks. `{mod}` covers a
module, `{ref}` an internal anchor, `{doc}` a page without an explicit ref
label. Plain backticks stay correct for code syntax, environment variables,
parameter names, and file paths that are not doc pages.

Link the first prose mention of any symbol that has a useful destination on
that page — Python objects, vcspull APIs, libvcs APIs, CLI command pages,
configuration pages, and external tools or projects. After the first linked
mention on a page, later mentions can stay plain unless distance or context
makes another link useful. Do not rely on a later reference section to
satisfy the first-mention rule: if the first occurrence would be a heading,
grid-card teaser, or introductory sentence, link that occurrence or retitle
the heading so the first prose mention can carry the link. Leave command
examples, code blocks, and literal configuration values as code; link the
surrounding prose instead.

A `{ref}` must match its target's anchor exactly. Page anchors are hyphenated
(`cli-sync`, `config-pin`) except for a few underscore holdouts in the
internals (`api_cli`). `just build-docs` catches a broken cross-reference;
nothing else does — build the docs before committing a change to `docs/`.

## Code blocks

Code blocks are paste-and-run units: pasting one block runs exactly one
intended action. Executed examples are exempt — the test suite runs them,
nobody pastes them.

- **One command per block.** Multiple steps may share a block only when
  explicitly chained with `&&`, `;`, or `\` continuations — the chain is then
  one logical command.
- **Explanations go in prose above the block**, never as `#` comments inside
  it.
- **Command menus are per-command blocks with prose lead-ins**, not tables.
- **Shell commands use the `console` tag with a `$ ` prefix.** This separates
  interactive commands from scripts and enables prompt-aware copy.
- **Split long commands with `\`** — one flag or flag+value pair per indented
  continuation line, positional arguments last.
- **Prefer longform flags** in prose and docs examples — `--workspace` not
  `-w`, `--file` not `-f`. A `--help` listing is the right place for the
  short forms.

Good — show the last ten commits as a graph:

```console
$ git log \
    --max-count=10 \
    --graph \
    --oneline
```

Bad:

```console
# Show the last ten commits as a graph
$ git log --max-count=10 --graph --oneline
```

## Commits

```
Scope(type[detail]): concise description

why: Explanation of necessity or impact.

what:
- Specific technical changes made
- Focused on a single topic
```

Keep the subject to 50 characters or fewer, excluding any trailing `(#NN)`
pull request reference, and wrap body lines at 72. Separate the `why:` and
`what:` blocks with a blank line.

Routine maintenance commits drop the colon and take a capitalised
description, which is what distinguishes them at a glance in
`git log --oneline` — this repo's history uses this form for
`py(deps[dev])`, `ai(rules[AGENTS])`, and `ai(claude[commands])`:

```
py(deps[dev]) Bump dev packages
ai(rules[AGENTS]) Judge comments by three gates
ai(claude[commands]) Add /update-libvcs skill
```

Everything that changes behaviour keeps the colon.

The `why:` is the pragmatic, contextual reason for the change — never cite
`AGENTS.md`, `CLAUDE.md`, or another rule file as the justification. "AGENTS.md
says…" or "CLAUDE.md requires…" is not a reason; look at `git log -n 10 -p`,
the PR description, and the linked issue for the real engineering reason
("function had no doctest coverage", not "the house style requires
doctests").

Common types:

- **feat**: New features or enhancements
- **fix**: Bug fixes
- **refactor**: Code restructuring without functional change
- **docs**: Documentation updates
- **chore**: Maintenance (dependencies, tooling, config)
- **test**: Test-related updates
- **style**: Code style and formatting
- **ci**: Workflow and pipeline changes
- **py(deps)**: Dependencies
- **py(deps[dev])**: Dev dependencies
- **ai(rules[AGENTS])**: AI rule updates
- **ai(claude[commands])**: Claude Code slash-command changes
  (`.claude/commands/`)

For a change under `docs/_ext`, use `docs` as the top-level component:

```
docs(sphinx_argparse_neo[renderer]): Escape asterisks in quoted strings

why: Glob patterns like "django-*" cause RST emphasis issues

what:
- Add _escape_glob_asterisks() helper method
- Call it before RST parsing in _parse_text()
```

Example:

```
cli(add[repo]): Add support for custom remote URLs

why: Enable users to specify alternative remote URLs for repositories

what:
- Add remote_url parameter to add_repo function
- Update CLI argument parser to accept --remote-url option
- Add tests for the new functionality
```

For a multi-line message, use a heredoc so the formatting survives:

```console
$ git commit -m "$(cat <<'EOF'
Scope(feat[detail]): Concise description

why: Explanation of the change.

what:
- First change
- Second change
EOF
)"
```

### Release commits

Never create tags. Never push tags. The owner handles tagging and tag pushes,
because a tag triggers the publish workflow.

A release commit subject is plain and short: `Tag v<version>`. The detailed
why and what go in the body. Do not use the `Scope(type[detail]):` format for
a release — it buries the lede.

## Slop prevention

Treat AI slop as review-hostile noise, not as proof that text or code is
wrong. The goal is to maximise information density.

- **AI signatures.** No "Generated by", no conversational filler, no
  unexplained emoji, no tool metadata.
- **Brittle references.** No hard-coded line numbers, fragile file counts,
  dated "as of" claims, bare SHAs, or local absolute paths — unless they are
  strict evidentiary artefacts, such as a benchmark log, a stack trace, a
  release note, or a lockfile, where the exact count, date, or SHA is the
  evidence.
- **Diff narration.** Do not restate what moved, was renamed, or was removed
  in anything the reader holds alongside the diff: code, docstrings, README,
  or a pull request description. The diff and the commit message already
  carry it.
- **Branch-internal narrative.** Do not mention intermediate states,
  abandoned approaches, or "no longer" behaviour unless users of a published
  release actually experienced the old state — the published-release test
  below.
- **Low-value scaffolding.** No ownerless TODOs, unused future-proofing,
  debug artefacts, or defensive wrappers around failure modes nothing can
  reach.
- **Prose inflation.** The diction table under [Voice](#voice) governs;
  replace an inflated word with a concrete description of behaviour,
  constraints, or trade-offs.
- **Coded labels.** Write rules and findings as plain imperatives. No `[R1]`,
  `Option B`, or any index a reader has to decode.

Preserve the "why". Never delete a comment documenting an invariant, a
protocol constraint, a platform quirk, or an upstream workaround — those are
the facts [Source comments](#source-comments) keeps, and every other comment
is judged by it.

### Durable source links

Link to a pinned revision, never to trunk. A pinned permalink is not a
brittle reference; an unlinked SHA dropped into prose is. `blob/master/…`
links rot silently — the file moves, lines shift, and the anchor lands on
unrelated code while still resolving.

- Prefer a release tag (`blob/v1.66.0/…`). Most durable, and it tells the
  reader which released version the claim held for.
- Otherwise use a 7-character commit ref (`blob/9a29b1a/…`) reachable from
  trunk. Use this when there is no tag or the claim is about unreleased code.
  Never a PR-head SHA — it can be rebased or garbage-collected.
- Reserve `blob/master/…` for living documents meant to always show the
  latest state, such as this file or `CONTRIBUTING.md`.
- Line anchors (`#L120-L145`) are only safe on a pinned ref.

### The published-release test

Long-running branches accumulate tactical decisions — renames, refactors,
attempts-then-reverts. When deciding what counts as branch-internal, use
trunk as the baseline, not an intermediate state inside the current branch.
Ask: did users of the most recently published release ever experience this
old name, old behaviour, or bug? If the answer is no, it is branch-internal
narrative — move it to the commit message and describe only the final state
in the artefact that ships.

Keep in shipped artefacts: deprecations and migration guides for symbols
that actually shipped; `### Fixes` entries for bugs that affected users of a
published release; and comments explaining why the current code looks this
way (invariants, platform quirks) that make sense to a reader who never saw
the previous version.
