(releasing)=

# Releasing

## Version policy

vcspull follows [semantic versioning](https://semver.org/). Internal APIs
(everything under `_internal/`) carry no stability guarantee.

## Release checklist

1. Update `CHANGES` with the new version and date.
2. Bump the version in `src/vcspull/__about__.py`.
3. Create a signed tag: `git tag -s v<version>`.
4. Push the tag: `git push --tags`.
5. Publish to PyPI: `uv build && uv publish`.
