(config-generation)=

# Config generation

The {ref}`vcspull import <cli-import>` command can generate configuration by
fetching repositories from remote services. See {ref}`cli-import` for details.

Supported services: {ref}`GitHub <cli-import-github>`,
{ref}`GitLab <cli-import-gitlab>`, {ref}`Codeberg <cli-import-codeberg>`,
{ref}`Gitea <cli-import-gitea>`, {ref}`Forgejo <cli-import-forgejo>`,
{ref}`AWS CodeCommit <cli-import-codecommit>`.

Example — import all repos from a GitLab group:

```console
$ vcspull import gitlab my-group \
    --workspace ~/code \
    --mode org
```
