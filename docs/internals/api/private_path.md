# PrivatePath – `vcspull._internal.private_path`

:::{warning}
`PrivatePath` is an internal helper. Its import path and behavior may change
without notice. File an issue if you rely on it downstream so we can discuss a
supported API.
:::

`PrivatePath` subclasses `pathlib.Path` and normalizes every textual rendering
(`str()`/`repr()`) so the current user’s home directory is collapsed to `~`.
The class behaves exactly like the standard path object for filesystem ops; it
only alters how the path is displayed. This keeps CLI logs, JSON/NDJSON output,
and tests from leaking usernames while preserving full absolute paths for
internal logic.

```python
from vcspull._internal.private_path import PrivatePath

home_repo = PrivatePath("~/code/vcspull")
print(home_repo)          # -> ~/code/vcspull
print(repr(home_repo))    # -> "PrivatePath('~/code/vcspull')"
```

## Usage guidelines

- Wrap any path destined for user-facing output (logs, console tables, JSON
  payloads) in `PrivatePath` before calling `str()`.
- The helper is safe to instantiate with `pathlib.Path` objects or strings; it
  does not touch relative paths that lack a home prefix.
- Prefer storing raw `pathlib.Path` objects (or strings) in configuration
  models, then convert to `PrivatePath` at the presentation layer. This keeps
  serialization and equality checks deterministic while still masking the home
  directory when needed.

## Why not `contract_user_home`?

The previous `contract_user_home()` helper duplicated the tilde-collapsing logic
in multiple modules and required callers to remember to run it themselves. By
centralizing the behavior in a `pathlib.Path` subclass we get:

- Built-in protection—`str()` and `repr()` automatically apply the privacy
  filter.
- Consistent behavior across every CLI command and test fixture.
- Easier mocking in tests, because `PrivatePath` respects monkeypatched
  `Path.home()` implementations.

If you need alternative redaction behavior, consider composing your own helper
around `PrivatePath` instead of reintroducing ad hoc string munging.

```{eval-rst}
.. automodule:: vcspull._internal.private_path
   :members:
   :show-inheritance:
   :undoc-members:
```
