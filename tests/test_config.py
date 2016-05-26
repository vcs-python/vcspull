# -*- coding: utf-8 -*-
"""Tests for vcspull config loading."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals, with_statement)

import os

import kaptan
import pytest

from vcspull import config, exc
from vcspull.config import expand_config

from .fixtures import example as fixtures
from .fixtures._util import loadfixture
from .helpers import EnvironmentVarGuard


@pytest.fixture
def config_dir(tmpdir):
    _config_dir = tmpdir.join('.vcspull')
    _config_dir.ensure(dir=True)
    return _config_dir


@pytest.fixture
def sample_yaml_config(config_dir):
    config_file1 = config_dir.join('repos1.yaml')
    config_file1.write('')
    return config_file1


@pytest.fixture
def sample_json_config(config_dir):
    config_file2 = config_dir.join('repos2.json')
    config_file2.write('')
    return config_file2


def test_dict_equals_yaml():
    # Verify that example YAML is returning expected dict format.
    config = kaptan.Kaptan(handler='yaml').import_config(
        loadfixture('example1.yaml'))

    assert fixtures.config_dict == config.export('dict')


def test_export_json(tmpdir):
    json_config = tmpdir.join('.vcspull.json')
    json_config_file = str(json_config)

    config = kaptan.Kaptan()
    config.import_config(fixtures.config_dict)

    json_config_data = config.export('json', indent=2)

    json_config.write(json_config_data)

    new_config = kaptan.Kaptan().import_config(json_config_file).get()
    assert fixtures.config_dict == new_config


def test_export_yaml(tmpdir):
    yaml_config = tmpdir.join('.vcspull.yaml')
    yaml_config_file = str(yaml_config)

    config = kaptan.Kaptan()
    config.import_config(fixtures.config_dict)

    yaml_config_data = config.export('yaml', indent=2)

    yaml_config.write(yaml_config_data)

    new_config = kaptan.Kaptan().import_config(yaml_config_file).get()
    assert fixtures.config_dict == new_config


def test_scan_config(tmpdir):
    configs = []

    exists = os.path.exists
    garbage_file = tmpdir.join('.vcspull.psd')
    garbage_file.write('wat')

    for r, d, f in os.walk(str(tmpdir)):
        for filela in (x for x in f if x.endswith(('.json', 'yaml')) and
                       x.startswith('.vcspull')):
            configs.append(str(tmpdir.join(filela)))

    files = 0
    if exists(str(tmpdir.join('.vcspull.json'))):
        files += 1
        assert str(tmpdir.join('.vcspull.json')) in configs

    if exists(str(tmpdir.join('.vcspull.yaml'))):
        files += 1
        assert str(tmpdir.join('.vcspull.json')) in configs

    assert len(configs) == files


def test_expand_shell_command_after():
    # Expand shell commands from string to list.
    config = expand_config(fixtures.config_dict)

    assert config, fixtures.config_dict_expanded


def test_expandenv_and_homevars():
    # Assure ~ tildes and environment template vars expand.

    expanduser = os.path.expanduser
    expandvars = os.path.expandvars

    config_yaml = loadfixture('expand.yaml')
    config_json = loadfixture("expand.json")

    config1 = kaptan.Kaptan(handler='yaml') \
        .import_config(config_yaml).export('dict')

    config2 = kaptan.Kaptan(handler='json') \
        .import_config(config_json).export('dict')

    config1_expanded = expand_config(config1)
    config2_expanded = expand_config(config2)

    paths = [r['parent_dir'] for r in config1_expanded]
    assert expanduser(expandvars('${HOME}/github_projects/')) in paths
    assert expanduser('~/study/') in paths
    assert expanduser('~') in paths

    paths = [r['parent_dir'] for r in config2_expanded]
    assert expandvars('${HOME}/github_projects/') in paths
    assert expanduser('~/study/') in paths


def test_find_config_files(tmpdir):
    # Test find_config_files in home directory.

    tmpdir.join('.vcspull.yaml').write('')
    with EnvironmentVarGuard() as env:
        env.set("HOME", str(tmpdir))
        os.environ.get("HOME") == str(tmpdir)
        expectedIn = str(tmpdir.join('.vcspull.yaml'))
        results = config.find_home_config_files()

        assert expectedIn in results


def test_multiple_configs_raises_exception(tmpdir):

    tmpdir.join('.vcspull.json').write('')
    tmpdir.join('.vcspull.yaml').write('')
    with EnvironmentVarGuard() as env:
        with pytest.raises(exc.MultipleRootConfigs):
            env.set("HOME", str(tmpdir))
            os.environ.get("HOME") == str(tmpdir)

            config.find_home_config_files()


def test_in_dir(
    config_dir,
    sample_yaml_config,
    sample_json_config
):
    expected = [
        sample_yaml_config.purebasename,
        sample_json_config.purebasename,
    ]
    result = config.in_dir(str(config_dir))

    assert len(expected) == len(result)


def test_find_config_path_string(
    config_dir,
    sample_yaml_config,
    sample_json_config
):
    configs = config.find_config_files(path=str(config_dir))

    assert str(sample_yaml_config) in configs
    assert str(sample_json_config) in configs


def test_find_config_path_list(
    config_dir,
    sample_yaml_config,
    sample_json_config
):
    configs = config.find_config_files(path=[str(config_dir)])

    assert str(sample_yaml_config) in configs
    assert str(sample_json_config) in configs


def test_find_config_match_string(
    config_dir,
    sample_yaml_config,
    sample_json_config
):
    configs = config.find_config_files(
        path=str(config_dir),
        match=sample_yaml_config.purebasename
    )

    assert str(sample_yaml_config) in configs
    assert str(sample_json_config) not in configs

    configs = config.find_config_files(
        path=[str(config_dir)],
        match=sample_json_config.purebasename
    )

    assert str(sample_yaml_config) not in configs
    assert str(sample_json_config) in configs

    configs = config.find_config_files(
        path=[str(config_dir)],
        match='randomstring'
    )

    assert str(sample_yaml_config) not in configs
    assert str(sample_json_config) not in configs

    configs = config.find_config_files(
        path=[str(config_dir)],
        match='*'
    )

    assert str(sample_yaml_config) in configs
    assert str(sample_json_config) in configs

    configs = config.find_config_files(
        path=[str(config_dir)],
        match='repos*'
    )

    assert str(sample_yaml_config) in configs
    assert str(sample_json_config) in configs

    configs = config.find_config_files(
        path=[str(config_dir)],
        match='repos[1-9]*'
    )

    assert len([c for c in configs if str(sample_yaml_config) in c]) == 1

    assert str(sample_yaml_config) in configs
    assert str(sample_json_config) in configs


def test_find_config_match_list(
    config_dir,
    sample_yaml_config,
    sample_json_config
):
    configs = config.find_config_files(
        path=[str(config_dir)],
        match=[
            sample_yaml_config.purebasename,
            sample_json_config.purebasename
        ]
    )

    assert str(sample_yaml_config) in configs
    assert str(sample_json_config) in configs

    configs = config.find_config_files(
        path=[str(config_dir)],
        match=[sample_yaml_config.purebasename]
    )

    assert str(sample_yaml_config) in configs
    assert len([c for c in configs if str(sample_yaml_config) in c]) == 1
    assert str(sample_json_config) not in configs
    assert len([c for c in configs if str(sample_json_config) in c]) == 0


def test_find_config_filetype_string(
    config_dir,
    sample_yaml_config,
    sample_json_config
):
    configs = config.find_config_files(
        path=[str(config_dir)],
        match=sample_yaml_config.purebasename,
        filetype='yaml',
    )

    assert str(sample_yaml_config) in configs
    assert str(sample_json_config) not in configs

    configs = config.find_config_files(
        path=[str(config_dir)],
        match=sample_yaml_config.purebasename,
        filetype='json',
    )

    assert str(sample_yaml_config) not in configs
    assert str(sample_json_config) not in configs

    configs = config.find_config_files(
        path=[str(config_dir)],
        match='repos*',
        filetype='json',
    )

    assert str(sample_yaml_config) not in configs
    assert str(sample_json_config) in configs

    configs = config.find_config_files(
        path=[str(config_dir)],
        match='repos*',
        filetype='*',
    )

    assert str(sample_yaml_config) in configs
    assert str(sample_json_config) in configs


def test_find_config_filetype_list(
    config_dir,
    sample_yaml_config,
    sample_json_config
):
    configs = config.find_config_files(
        path=[str(config_dir)],
        match=['repos*'],
        filetype=['*'],
    )

    assert str(sample_yaml_config) in configs
    assert str(sample_json_config) in configs

    configs = config.find_config_files(
        path=[str(config_dir)],
        match=['repos*'],
        filetype=['json', 'yaml'],
    )

    assert str(sample_yaml_config) in configs
    assert str(sample_json_config) in configs

    configs = config.find_config_files(
        path=[str(config_dir)],
        filetype=['json', 'yaml'],
    )

    assert str(sample_yaml_config) in configs
    assert str(sample_json_config) in configs


def test_find_config_include_home_configs(
    tmpdir,
    config_dir,
    sample_yaml_config,
    sample_json_config
):
    with EnvironmentVarGuard() as env:
        env.set("HOME", str(tmpdir))
        configs = config.find_config_files(
            path=[str(config_dir)],
            match='*',
            include_home=True
        )

        assert str(sample_yaml_config) in configs
        assert str(sample_json_config) in configs

        config_file3 = tmpdir.join('.vcspull.json')
        config_file3.write('')

        results = config.find_config_files(
            path=[str(config_dir)],
            match='*',
            include_home=True
        )
        expectedIn = str(config_file3)

        assert expectedIn in results
        assert str(sample_yaml_config) in results
        assert str(sample_json_config) in results


def test_merge_nested_dict(tmpdir, config_dir):
    config1 = config_dir.join('repoduplicate1.yaml')
    config1.write(loadfixture(r'repoduplicate1.yaml'))

    conf = kaptan.Kaptan(handler='yaml').import_config(str(config1))
    config1_dict = conf.export('dict')

    config2 = config_dir.join('repoduplicate2.yaml')
    config2.write(loadfixture('repoduplicate2.yaml'))

    conf = kaptan.Kaptan(handler='yaml').import_config(str(config2))
    config2_dict = conf.export('dict')

    # validate export of multiple configs + nested dirs
    assert 'vcsOn1' in config1_dict['/path/to/test/']
    assert 'vcsOn2' not in config1_dict['/path/to/test/']
    assert 'vcsOn2' in config2_dict['/path/to/test/']

    # Duplicate path + name with different repo URL / remotes raises.
    configs = config.find_config_files(
        path=str(config_dir),
        match="repoduplicate[1-2]"
    )

    assert str(config1) in configs
    assert str(config2) in configs
    with pytest.raises(Exception):
        config.load_configs(configs)
