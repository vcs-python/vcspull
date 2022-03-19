(config-generation)=

# Config generation

As a temporary solution for `vcspull` not being able to generate {ref}`configuration` through scanning directories or fetching them via API (e.g. gitlab, github, etc), you can write scripts to generate configs in the mean time.

(config-generation-gitlab)=

## Collect repos from Gitlab

Contributed by Andreas Schleifer (a.schleifer@bigpoint.net)

Limitation on both, no pagination support in either, so only returns the
first page of repos (as of Feb 26th this is 100).

````{tab} Shell-script

_Requires [jq] and [curl]._

```{literalinclude} ../../scripts/generate_gitlab.sh
:language: shell
```

```console
$ env GITLAB_TOKEN=mySecretToken \
  /path/to/generate_gitlab.sh gitlab.mycompany.com desired_namespace
```

To be executed from the path where the repos should later be stored. It will use
the current working directory as a "prefix" for the path used in the new config file.

Optional: Set config file output path as additional argument (_will overwrite_)

```console
$ env GITLAB_TOKEN=mySecretToken \
  /path/to/generate_gitlab.sh gitlab.mycompany.com desired_namespace /path/to/config.yaml
```

**Demonstration**

Assume current directory of _/home/user/workspace/_ and script at _/home/user/workspace/scripts/generate_gitlab.sh_:

```console
$ ./scripts/generate_gitlab.sh gitlab.com vcs-python
```

New file _vcspull.yaml_:

```yaml
/my/workspace/:
  g:
    url: "git+ssh://git@gitlab.com/vcs-python/g.git"
    remotes:
      origin: "ssh://git@gitlab.com/vcs-python/g.git"
  libvcs:
    url: "git+ssh://git@gitlab.com/vcs-python/libvcs.git"
    remotes:
      origin: "ssh://git@gitlab.com/vcs-python/libvcs.git"
  vcspull:
    url: "git+ssh://git@gitlab.com/vcs-python/vcspull.git"
    remotes:
      origin: "ssh://git@gitlab.com/vcs-python/vcspull.git"
```

[jq]: https://stedolan.github.io/jq/

[curl]: https://curl.se/

````

````{tab} Python
_Requires [requests] and [pyyaml]._

This confirms file overwrite, if already exists. It also requires passing the protocol/schema
of the gitlab mirror, e.g. `https://gitlab.com` instead of `gitlab.com`.

```{literalinclude} ../../scripts/generate_gitlab.py
:language: python
```

**Demonstration**

Assume current directory of _/home/user/workspace/_ and script at _/home/user/workspace/scripts/generate_gitlab.sh_:

```console
$ ./scripts/generate_gitlab.py https://gitlab.com vcs-python
```

```yaml
/my/workspace/vcs-python:
  g:
    remotes:
      origin: ssh://git@gitlab.com/vcs-python/g.git
    url: git+ssh://git@gitlab.com/vcs-python/g.git
  libvcs:
    remotes:
      origin: ssh://git@gitlab.com/vcs-python/libvcs.git
    url: git+ssh://git@gitlab.com/vcs-python/libvcs.git
  vcspull:
    remotes:
      origin: ssh://git@gitlab.com/vcs-python/vcspull.git
    url: git+ssh://git@gitlab.com/vcs-python/vcspull.git
```

[requests]: https://docs.python-requests.org/en/latest/
[pyyaml]: https://pyyaml.org/

````

### Contribute your own

Post yours on <https://github.com/vcs-python/vcspull/discussions> or create a PR to add
yours to scripts/ and be featured here
