# Documentation voice

This file covers the *voice* of prose under `docs/` — how to frame a
page so a reader meets the idea before its configuration. It
complements the repository-root `AGENTS.md`, which already governs
code blocks, shell-command formatting, changelog conventions, and MyST
roles. When the two overlap, the root file wins; this one only answers
the question it leaves open: how should the prose sound?

## Who you are writing for

The default reader runs vcspull from a shell and keeps a configuration
file in YAML or JSON — `~/.vcspull.yaml` or a file under
`~/.config/vcspull/`. They are fluent in git (often hg or svn too) and
comfortable at a prompt, but you cannot assume they read Python, know
libvcs, or have heard of `load_configs`, `extract_repos`, or the
internal config reader.

A second, smaller reader writes Python: code against `vcspull.config`,
the modules under `docs/internals/`, or a contribution. Serve them
too, but mark their material opt-in ("for the rarer cases",
"advanced") so the default reader knows they can stop. Never make the
common case pay a comprehension tax for the advanced one.

## Voice

- **Second person, present tense, active.** "You pin the entry", not
  "The entry is pinned". Address the reader who is doing the thing.
- **Concept before configuration.** Open by saying what the thing *is*
  and what it does for the reader. The YAML surface — the keys, the
  flags — is the last detail they need, not the first. A page that
  opens with "set these keys" has buried the idea under its mechanics.
- **Say when they can stop.** Lead with the default and the
  reassurance: most readers never touch this, the defaults work,
  everything here is optional. Let a skimmer leave after one sentence.
- **Progressive disclosure.** Order by how many readers need it: the
  plain `vcspull sync '*'` → the one flag a few will tune → the
  per-repository `options:` block → the Python API. Each step is for
  a smaller audience than the last.
- **Lean on the pipeline.** The reader thinks configuration file →
  workspace root → repository entry → sync; reinforce that chain when
  you explain where a key lives or which repositories a command
  touches. It is the mental model the whole tool hangs on.
- **Name the trade-off.** If an option costs something —
  `options.shallow` trades git history for disk and time,
  `--exit-on-error` stops the whole run at the first failure — say
  so, and say what it buys. State it; don't sell it.
- **Frame by concept, not by mechanism.** Don't headline a feature as
  "the `--dry-run` flag" or "the `options:` block" in prose; that
  names the implementation surface, which is the reader's last
  concern. Name the concept: previewing a sync, pinning an entry. The
  mechanics vocabulary — a pin-key table, the generated flag listing —
  is correct in a reference table, and only there.

## What stays precise

Warm the framing, never the facts. Config search-order lists, pin-key
tables, exact warning strings ("No repo found in config(s) for …"),
YAML schema fragments, and class or function cross-references carry
meaning in their exact form — leave them alone. The friendly voice
belongs in the sentences *around* a precise block, introducing it,
not inside it paraphrasing it into vagueness.

## Examples that stay honest

Sphinx does not execute code blocks under `docs/`. Pytest checks the
Markdown fence conventions and parses documented `vcspull ...` commands with
the real argparse tree, but it does not run mutating, networked, or VCS
commands from the pages. Honesty is still manual: copy commands and output
from a run you actually made, keep YAML consistent with the real schema
(workspace root → repository entry), and re-check a page's examples whenever
the flags or keys they show change.

## Console blocks and reference pages

Two mechanical conventions, separate from voice:

- **Console blocks** come in three flavors: ```` ```console ```` for
  a command at a `$` prompt (the root `AGENTS.md` shape),
  ```` ```vcspull-console ```` for a command *plus* vcspull's styled
  output, and ```` ```vcspull-output ```` for output alone. The last
  two are custom lexers registered from `docs/_ext`.
- **Reference blocks are generated.** CLI pages embed the live parser
  with an `{eval-rst}` block wrapping `.. argparse::`, and the
  `docs/internals/api/**` pages document modules with
  `.. automodule::`. Introduce them in prose; never paraphrase their
  content into sentences that will drift.

## Cross-references

Point the advanced reader at the deep-dive rather than inlining it,
and put the link where their interest peaks — on the phrase that made
them curious ("pin the entry", "bulk import") — not as a standalone
footnote the eye skips. Use the MyST roles listed in the root
`AGENTS.md` (`{class}`, `{meth}`, `{func}`, `{exc}`, `{attr}`,
`{ref}`, `{doc}`). A `{ref}` must match its target's anchor exactly —
page anchors are hyphenated (`cli-sync`, `config-pin`) except for a
few underscore holdouts in the internals (`api_cli`).
`just build-docs` catches a broken cross-reference; nothing else
does — so build the docs before you commit.

Link the first prose mention of any symbol that has a useful destination on
that page. This includes Python objects, vcspull APIs, libvcs APIs, CLI
command pages, configuration pages, and external tools or projects. Use the
most specific target available: `{class}`, `{meth}`, `{func}`, `{mod}`,
`{exc}`, or `{attr}` for API objects; `{ref}` or `{doc}` for documentation
pages and section anchors; and a Markdown link or reference link for external
projects. After the first linked mention on a page, later mentions can stay
plain unless the distance or context makes another link useful.

Do not rely on a later reference section to satisfy the first-mention rule.
If the first occurrence would be a heading, grid-card teaser, or introductory
sentence, link that occurrence or retitle the heading so the first prose
mention can carry the link. Leave command examples, code blocks, and literal
configuration values as code; link the surrounding prose instead.

## A page that does this

`docs/cli/add.md` is the worked example: a concept-first intro that
says what the command does for you — register a checkout in your
configuration — before any flag, an early note routing the bulk cases
to the `cli-discover` and `cli-import` targets right when the reader
would wonder, the generated argparse reference left exact, sections
ordered basic usage → overrides → automation, real output shown in
`vcspull-console` blocks, and honest behavior notes (it prompts before
writing; dry runs still show merge diagnostics). Read it before
reshaping another page.

## Before you commit

- Does the page open with what the feature *is*, or with how to
  configure it?
- Can a reader who needs only the default stop after the first
  paragraph?
- Is anything framed as "the keys/flags" that should be named by
  concept instead?
- Are the advanced and Python-only parts clearly marked opt-in?
- Did you leave every table, warning string, and cross-reference
  exact — and does every console example match a run you actually made?
- Did `just build-docs` stay clean — no new warning, no broken
  cross-reference?
