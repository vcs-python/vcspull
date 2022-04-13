(api)=

# API Reference

:::{seealso}
If you case needs granular control, check out {ref}`libvcs <libvcs:index>` for its [Command API](https://libvcs.git-pull.com/cmd/) and {ref}`States API <libvcs:states>`
and {ref}`Quickstart <libvcs:quickstart>`.
:::

## Internals

:::{warning}
These APIs are purely internal not covered by versioning policies, they can and will break between versions.
If you need an internal API stabilized please [file an issue](https://github.com/vcs-python/libvcs/issues).
:::

## Exceptions

```{eval-rst}
.. autoexception:: vcspull.exc.VCSPullException
```

```{eval-rst}
.. autoexception:: vcspull.exc.MultipleConfigWarning
```
