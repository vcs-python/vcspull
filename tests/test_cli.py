# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import pytest

from click.testing import CliRunner

from vcspull.cli import cli


@pytest.mark.skip(reason="todo")
def test_command_line(self):
    runner = CliRunner()
    result = runner.invoke(cli, ['up', 'hi'])
    assert result.exit_code == 0
    assert 'Debug mode is on' in result.output
    assert 'Syncing' in result.output
