(config-generation)=

# Config generation

The `vcspull import` command can generate configuration by fetching
repositories from remote services. See {ref}`cli-import` for details.

Supported services: GitHub, GitLab, Codeberg, Gitea, Forgejo,
AWS CodeCommit.

Example — import all repos from a GitLab group:

```console
$ vcspull import gitlab my-group \
    --workspace ~/code \
    --mode org
```
