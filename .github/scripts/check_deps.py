#!/usr/bin/env python
"""Check for undeclared runtime dependencies.

A minimal, zero-dependency script to detect imports in src/ that aren't
declared in pyproject.toml dependencies.

Examples
--------
>>> # Test normalize_package_name
>>> normalize_package_name("PyYAML")
'pyyaml'
>>> normalize_package_name("typing-extensions")
'typing_extensions'
>>> normalize_package_name("Pillow")
'pillow'

>>> # Test parse_dependency_spec
>>> parse_dependency_spec("requests>=2.0")
'requests'
>>> parse_dependency_spec("PyYAML>=6.0")
'pyyaml'
>>> parse_dependency_spec("typing_extensions>=4.0.0;python_version<'3.11'")
'typing_extensions'
>>> parse_dependency_spec("package[extra]>=1.0")
'package'
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import tomllib

# Known package name -> import name mappings
# (where they differ)
PACKAGE_TO_IMPORT: dict[str, str] = {
    "pyyaml": "yaml",
    "pillow": "PIL",
    "beautifulsoup4": "bs4",
    "scikit-learn": "sklearn",
    "opencv-python": "cv2",
    "typing_extensions": "typing_extensions",
}

# Imports to ignore (optional deps, usually wrapped in try/except)
IGNORED_IMPORTS: set[str] = {
    "shtab",  # Optional shell completion
}


def normalize_package_name(name: str) -> str:
    """Normalize package name per PEP 503.

    Parameters
    ----------
    name : str
        Package name from pyproject.toml

    Returns
    -------
    str
        Normalized lowercase name with hyphens as underscores

    Examples
    --------
    >>> normalize_package_name("PyYAML")
    'pyyaml'
    >>> normalize_package_name("typing-extensions")
    'typing_extensions'
    """
    return name.lower().replace("-", "_")


def parse_dependency_spec(spec: str) -> str:
    """Extract package name from dependency specification.

    Parameters
    ----------
    spec : str
        Dependency spec like "requests>=2.0" or "pkg[extra];python_version<'3.11'"

    Returns
    -------
    str
        Normalized package name

    Examples
    --------
    >>> parse_dependency_spec("requests>=2.0")
    'requests'
    >>> parse_dependency_spec("package[extra]>=1.0,<2.0")
    'package'
    >>> parse_dependency_spec("typing_extensions;python_version<'3.11'")
    'typing_extensions'
    """
    # Remove environment markers (;python_version<'3.11')
    name = spec.split(";")[0].strip()
    # Remove extras ([extra])
    name = name.split("[")[0]
    # Remove version specifiers (>=, <=, ==, ~=, !=, <, >)
    for sep in (">=", "<=", "==", "~=", "!=", "<", ">", " "):
        name = name.split(sep)[0]
    return normalize_package_name(name.strip())


def get_declared_deps(pyproject_path: Path) -> dict[str, str]:
    """Get declared dependencies from pyproject.toml.

    Parameters
    ----------
    pyproject_path : Path
        Path to pyproject.toml

    Returns
    -------
    dict[str, str]
        Mapping of normalized package name to expected import name
    """
    data = tomllib.loads(pyproject_path.read_text())
    deps = data.get("project", {}).get("dependencies", [])

    result = {}
    for spec in deps:
        pkg_name = parse_dependency_spec(spec)
        # Use known mapping or assume import name = normalized package name
        import_name = PACKAGE_TO_IMPORT.get(pkg_name, pkg_name)
        result[pkg_name] = import_name

    return result


def get_stdlib_modules() -> set[str]:
    """Get set of standard library module names.

    Returns
    -------
    set[str]
        Standard library top-level module names

    Examples
    --------
    >>> stdlib = get_stdlib_modules()
    >>> "os" in stdlib
    True
    >>> "pathlib" in stdlib
    True
    >>> "requests" in stdlib
    False
    """
    # Python 3.10+ has sys.stdlib_module_names
    if hasattr(sys, "stdlib_module_names"):
        return set(sys.stdlib_module_names)

    # Fallback for older Python (shouldn't hit this for vcspull)
    import sysconfig

    stdlib_path = Path(sysconfig.get_paths()["stdlib"])
    modules = {p.stem for p in stdlib_path.glob("*.py")}
    modules |= {
        p.name
        for p in stdlib_path.iterdir()
        if p.is_dir() and not p.name.startswith("_")
    }
    return modules


def extract_imports(source_dir: Path) -> dict[str, list[tuple[Path, int]]]:
    """Extract all imports from Python files in directory.

    Parameters
    ----------
    source_dir : Path
        Directory to scan for .py files

    Returns
    -------
    dict[str, list[tuple[Path, int]]]
        Mapping of import name to list of (file, line_number) locations
    """
    imports: dict[str, list[tuple[Path, int]]] = {}

    for py_file in source_dir.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(), filename=str(py_file))
        except SyntaxError:
            print(f"Warning: Could not parse {py_file}", file=sys.stderr)
            continue

        for node in ast.walk(tree):
            name = None
            lineno = 0

            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    lineno = node.lineno
                    imports.setdefault(name, []).append((py_file, lineno))

            # Skip relative imports (from . import x)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                name = node.module.split(".")[0]
                lineno = node.lineno
                imports.setdefault(name, []).append((py_file, lineno))

    return imports


def find_first_party_modules(source_dir: Path) -> set[str]:
    """Find first-party module names (the project's own packages).

    Parameters
    ----------
    source_dir : Path
        Source directory (e.g., src/)

    Returns
    -------
    set[str]
        Set of first-party module names
    """
    modules = set()
    for item in source_dir.iterdir():
        if item.is_dir() and (item / "__init__.py").exists():
            modules.add(item.name)
        elif item.suffix == ".py" and item.stem != "__init__":
            modules.add(item.stem)
    return modules


def check_undeclared(
    source_dir: Path,
    pyproject_path: Path,
    ignore: set[str] | None = None,
) -> list[tuple[str, list[tuple[Path, int]]]]:
    """Find imports not declared in dependencies.

    Parameters
    ----------
    source_dir : Path
        Directory containing source code
    pyproject_path : Path
        Path to pyproject.toml
    ignore : set[str], optional
        Additional import names to ignore

    Returns
    -------
    list[tuple[str, list[tuple[Path, int]]]]
        List of (import_name, locations) for undeclared imports
    """
    ignore = (ignore or set()) | IGNORED_IMPORTS

    declared = get_declared_deps(pyproject_path)
    declared_imports = set(declared.values())

    imports = extract_imports(source_dir)
    stdlib = get_stdlib_modules()
    first_party = find_first_party_modules(source_dir)

    undeclared = []
    for name, locations in sorted(imports.items()):
        # Skip if: stdlib, first-party, declared, or ignored
        if name in stdlib:
            continue
        if name in first_party:
            continue
        if name in declared_imports:
            continue
        if name in ignore:
            continue

        undeclared.append((name, locations))

    return undeclared


def main() -> int:
    """Run the dependency checker.

    Returns
    -------
    int
        Exit code (0 = success, 1 = undeclared deps found)
    """
    # Find project root (where pyproject.toml is)
    script_dir = Path(__file__).resolve().parent  # .github/scripts/
    project_root = script_dir.parent.parent  # repo root
    pyproject_path = project_root / "pyproject.toml"
    source_dir = project_root / "src"

    if not pyproject_path.exists():
        print(f"Error: {pyproject_path} not found", file=sys.stderr)
        return 1

    if not source_dir.exists():
        print(f"Error: {source_dir} not found", file=sys.stderr)
        return 1

    undeclared = check_undeclared(source_dir, pyproject_path)

    if not undeclared:
        print("No undeclared dependencies detected.")
        return 0

    print("Undeclared dependencies found:\n")
    for name, locations in undeclared:
        print(f"  {name}")
        for path, lineno in locations[:3]:  # Show first 3 locations
            rel_path = path.relative_to(project_root)
            print(f"    {rel_path}:{lineno}")
        if len(locations) > 3:
            print(f"    ... and {len(locations) - 3} more")
        print()

    return 1


if __name__ == "__main__":
    sys.exit(main())
