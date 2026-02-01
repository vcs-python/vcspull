"""Tests for config reader utilities."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from vcspull._internal.config_reader import DuplicateAwareConfigReader

if TYPE_CHECKING:
    import pathlib


def _write(tmp_path: pathlib.Path, name: str, content: str) -> pathlib.Path:
    file_path = tmp_path / name
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_duplicate_aware_reader_records_yaml_duplicates(tmp_path: pathlib.Path) -> None:
    """YAML duplicate workspace roots are captured without data loss."""
    yaml_content = textwrap.dedent(
        """\
        ~/study/python/:
          repo1:
            repo: git+https://example.com/repo1.git
        ~/study/python/:
          repo2:
            repo: git+https://example.com/repo2.git
        """,
    )
    config_path = _write(tmp_path, "config.yaml", yaml_content)

    reader = DuplicateAwareConfigReader.from_file(config_path)

    assert reader.content == {
        "~/study/python/": {
            "repo2": {"repo": "git+https://example.com/repo2.git"},
        },
    }
    assert "~/study/python/" in reader.duplicate_sections
    captured = reader.duplicate_sections["~/study/python/"]
    assert len(captured) == 2
    assert captured[0] == {
        "repo1": {"repo": "git+https://example.com/repo1.git"},
    }
    assert captured[1] == {
        "repo2": {"repo": "git+https://example.com/repo2.git"},
    }


def test_duplicate_aware_reader_handles_yaml_without_duplicates(
    tmp_path: pathlib.Path,
) -> None:
    """YAML without duplicate keys reports an empty duplicate map."""
    yaml_content = textwrap.dedent(
        """\
        ~/code/:
          repo:
            repo: git+https://example.com/repo.git
        """,
    )
    config_path = _write(tmp_path, "single.yaml", yaml_content)

    reader = DuplicateAwareConfigReader.from_file(config_path)

    assert reader.content == {
        "~/code/": {
            "repo": {"repo": "git+https://example.com/repo.git"},
        },
    }
    assert reader.duplicate_sections == {}


def test_duplicate_aware_reader_passes_through_json(tmp_path: pathlib.Path) -> None:
    """JSON configs remain supported and duplicates remain empty."""
    json_content = textwrap.dedent(
        """\
        {
          "~/code/": {
            "repo": {"repo": "git+https://example.com/repo.git"}
          }
        }
        """,
    )
    config_path = _write(tmp_path, "config.json", json_content)

    reader = DuplicateAwareConfigReader.from_file(config_path)

    assert reader.content == {
        "~/code/": {
            "repo": {"repo": "git+https://example.com/repo.git"},
        },
    }
    assert reader.duplicate_sections == {}


def test_duplicate_aware_reader_preserves_top_level_item_order(
    tmp_path: pathlib.Path,
) -> None:
    """Loader should expose ordered top-level items so duplicates can be replayed."""
    yaml_content = textwrap.dedent(
        """\
        ~/study/python/:
          Flexget:
            repo: git+https://github.com/Flexget/Flexget.git
        ~/study/python/:
          bubbles:
            repo: git+https://github.com/Stiivi/bubbles.git
        ~/study/python/:
          cubes:
            repo: git+https://github.com/Stiivi/cubes.git
        """,
    )
    config_path = _write(tmp_path, "ordered.yaml", yaml_content)

    reader = DuplicateAwareConfigReader.from_file(config_path)

    items = reader.top_level_items
    assert [key for key, _ in items] == [
        "~/study/python/",
        "~/study/python/",
        "~/study/python/",
    ]
    assert items[0][1] == {
        "Flexget": {"repo": "git+https://github.com/Flexget/Flexget.git"},
    }
    assert items[1][1] == {
        "bubbles": {"repo": "git+https://github.com/Stiivi/bubbles.git"},
    }
    assert items[2][1] == {
        "cubes": {"repo": "git+https://github.com/Stiivi/cubes.git"},
    }


def test_duplicate_aware_reader_ignores_nested_list_mappings(
    tmp_path: pathlib.Path,
) -> None:
    """Mappings inside lists should not be counted as top-level duplicates.

    Regression test for bug where worktrees config like:

        worktrees:
          - dir: ../v1
            tag: v1.0
          - dir: ../v2
            tag: v2.0

    Would incorrectly flag 'dir' and 'tag' as duplicate top-level keys.

    The root cause is that PyYAML constructs sequence (list) items AFTER
    exiting parent mappings, causing list item mappings to appear at depth 1.
    """
    yaml_content = textwrap.dedent(
        """\
        ~/study/c/:
          tmux:
            repo: git+https://github.com/tmux/tmux.git
            worktrees:
              - dir: ../tmux-3.6a
                tag: "3.6a"
              - dir: ../tmux-3.6
                tag: "3.6"
              - dir: ../tmux-3.5
                tag: "3.5"
        """,
    )
    config_path = _write(tmp_path, "worktrees.yaml", yaml_content)

    reader = DuplicateAwareConfigReader.from_file(config_path)

    # The only top-level key should be the workspace root
    assert list(reader.content.keys()) == ["~/study/c/"]

    # 'dir' and 'tag' should NOT appear as duplicates - they're inside a list
    assert "dir" not in reader.duplicate_sections
    assert "tag" not in reader.duplicate_sections

    # No duplicates at all in this config
    assert reader.duplicate_sections == {}
