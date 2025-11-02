"""Tests for config reader utilities."""

from __future__ import annotations

import pathlib

from vcspull._internal.config_reader import DuplicateAwareConfigReader


def _write(tmp_path: pathlib.Path, name: str, content: str) -> pathlib.Path:
    file_path = tmp_path / name
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_duplicate_aware_reader_records_yaml_duplicates(tmp_path: pathlib.Path) -> None:
    """YAML duplicate workspace roots are captured without data loss."""
    yaml_content = (
        "~/study/python/:\n"
        "  repo1:\n"
        "    repo: git+https://example.com/repo1.git\n"
        "~/study/python/:\n"
        "  repo2:\n"
        "    repo: git+https://example.com/repo2.git\n"
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
    yaml_content = "~/code/:\n  repo:\n    repo: git+https://example.com/repo.git\n"
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
    json_content = (
        "{\n"
        '  "~/code/": {\n'
        '    "repo": {"repo": "git+https://example.com/repo.git"}\n'
        "  }\n"
        "}\n"
    )
    config_path = _write(tmp_path, "config.json", json_content)

    reader = DuplicateAwareConfigReader.from_file(config_path)

    assert reader.content == {
        "~/code/": {
            "repo": {"repo": "git+https://example.com/repo.git"},
        },
    }
    assert reader.duplicate_sections == {}
