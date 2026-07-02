# Config reader - `vcspull._internal.config_reader`

:::{warning}
Be careful with these! Internal APIs are **not** covered by version policies. They can break or be removed between minor versions!

If you need an internal API stabilized please [file an issue](https://github.com/vcs-python/vcspull/issues).
:::

{mod}`vcspull._internal.config_reader` turns raw YAML or JSON text into
Python dictionaries — the low-level reader beneath {mod}`vcspull.config`,
including the duplicate-aware loader that preserves repeated workspace roots
for merging.

```{eval-rst}
.. automodule:: vcspull._internal.config_reader
   :members:
   :show-inheritance:
   :undoc-members:
```
