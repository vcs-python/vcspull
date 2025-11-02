from __future__ import annotations

import json
import pathlib
import typing as t

import yaml

if t.TYPE_CHECKING:
    from typing import Literal, TypeAlias

    FormatLiteral = Literal["json", "yaml"]

    RawConfigData: TypeAlias = dict[t.Any, t.Any]


class ConfigReader:
    r"""Parse string data (YAML and JSON) into a dictionary.

    >>> cfg = ConfigReader({ "session_name": "my session" })
    >>> cfg.dump("yaml")
    'session_name: my session\n'
    >>> cfg.dump("json")
    '{\n  "session_name": "my session"\n}'
    """

    def __init__(self, content: RawConfigData) -> None:
        self.content = content

    @staticmethod
    def _load(fmt: FormatLiteral, content: str) -> dict[str, t.Any]:
        """Load raw config data and directly return it.

        >>> ConfigReader._load("json", '{ "session_name": "my session" }')
        {'session_name': 'my session'}

        >>> ConfigReader._load("yaml", 'session_name: my session')
        {'session_name': 'my session'}
        """
        if fmt == "yaml":
            return t.cast(
                "dict[str, t.Any]",
                yaml.load(
                    content,
                    Loader=yaml.SafeLoader,
                ),
            )
        if fmt == "json":
            return t.cast("dict[str, t.Any]", json.loads(content))
        msg = f"{fmt} not supported in configuration"
        raise NotImplementedError(msg)

    @classmethod
    def load(cls, fmt: FormatLiteral, content: str) -> ConfigReader:
        """Load raw config data into a ConfigReader instance (to dump later).

        >>> cfg = ConfigReader.load("json", '{ "session_name": "my session" }')
        >>> cfg
        <tmuxp.config_reader.ConfigReader object at ...>
        >>> cfg.content
        {'session_name': 'my session'}

        >>> cfg = ConfigReader.load("yaml", 'session_name: my session')
        >>> cfg
        <tmuxp.config_reader.ConfigReader object at ...>
        >>> cfg.content
        {'session_name': 'my session'}
        """
        return cls(
            content=cls._load(
                fmt=fmt,
                content=content,
            ),
        )

    @classmethod
    def _from_file(cls, path: pathlib.Path) -> dict[str, t.Any]:
        r"""Load data from file path directly to dictionary.

        **YAML file**

        *For demonstration only,* create a YAML file:

        >>> yaml_file = tmp_path / 'my_config.yaml'
        >>> yaml_file.write_text('session_name: my session', encoding='utf-8')
        24

        *Read YAML file*:

        >>> ConfigReader._from_file(yaml_file)
        {'session_name': 'my session'}

        **JSON file**

        *For demonstration only,* create a JSON file:

        >>> json_file = tmp_path / 'my_config.json'
        >>> json_file.write_text('{"session_name": "my session"}', encoding='utf-8')
        30

        *Read JSON file*:

        >>> ConfigReader._from_file(json_file)
        {'session_name': 'my session'}
        """
        assert isinstance(path, pathlib.Path)
        content = path.open(encoding="utf-8").read()

        # TODO(#?): Align this loader with the duplicate-aware YAML handling that
        # ``vcspull fmt`` introduced in November 2025. The formatter now uses a
        # custom SafeLoader subclass to retain and merge duplicate workspace root
        # sections so repos are never overwritten. ConfigReader currently drops
        # later duplicates because PyYAML keeps only the last key. Options:
        # 1) Extract the formatter's loader/merge helpers into a shared utility
        #    that ConfigReader can reuse here;
        # 2) Replace ConfigReader entirely when reading vcspull configs and call
        #    the formatter helpers directly;
        # 3) Keep this basic loader but add an opt-in path for duplicate-aware
        #    parsing so commands like ``vcspull add`` can avoid data loss.
        # Revisit once the new ``vcspull add`` flow lands so both commands share
        # the same duplication safeguards.

        if path.suffix in {".yaml", ".yml"}:
            fmt: FormatLiteral = "yaml"
        elif path.suffix == ".json":
            fmt = "json"
        else:
            msg = f"{path.suffix} not supported in {path}"
            raise NotImplementedError(msg)

        return cls._load(
            fmt=fmt,
            content=content,
        )

    @classmethod
    def from_file(cls, path: pathlib.Path) -> ConfigReader:
        r"""Load data from file path.

        **YAML file**

        *For demonstration only,* create a YAML file:

        >>> yaml_file = tmp_path / 'my_config.yaml'
        >>> yaml_file.write_text('session_name: my session', encoding='utf-8')
        24

        *Read YAML file*:

        >>> cfg = ConfigReader.from_file(yaml_file)
        >>> cfg
        <tmuxp.config_reader.ConfigReader object at ...>

        >>> cfg.content
        {'session_name': 'my session'}

        **JSON file**

        *For demonstration only,* create a JSON file:

        >>> json_file = tmp_path / 'my_config.json'
        >>> json_file.write_text('{"session_name": "my session"}', encoding='utf-8')
        30

        *Read JSON file*:

        >>> cfg = ConfigReader.from_file(json_file)
        >>> cfg
        <tmuxp.config_reader.ConfigReader object at ...>

        >>> cfg.content
        {'session_name': 'my session'}
        """
        return cls(content=cls._from_file(path=path))

    @staticmethod
    def _dump(
        fmt: FormatLiteral,
        content: RawConfigData,
        indent: int = 2,
        **kwargs: t.Any,
    ) -> str:
        r"""Dump directly.

        >>> ConfigReader._dump("yaml", { "session_name": "my session" })
        'session_name: my session\n'

        >>> ConfigReader._dump("json", { "session_name": "my session" })
        '{\n  "session_name": "my session"\n}'
        """
        if fmt == "yaml":
            return yaml.dump(
                content,
                indent=2,
                default_flow_style=False,
                Dumper=yaml.SafeDumper,
            )
        if fmt == "json":
            return json.dumps(
                content,
                indent=2,
            )
        msg = f"{fmt} not supported in config"
        raise NotImplementedError(msg)

    def dump(self, fmt: FormatLiteral, indent: int = 2, **kwargs: t.Any) -> str:
        r"""Dump via ConfigReader instance.

        >>> cfg = ConfigReader({ "session_name": "my session" })
        >>> cfg.dump("yaml")
        'session_name: my session\n'
        >>> cfg.dump("json")
        '{\n  "session_name": "my session"\n}'
        """
        return self._dump(
            fmt=fmt,
            content=self.content,
            indent=indent,
            **kwargs,
        )
