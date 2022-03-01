"""CLI utilities for vcspull.

vcspull.cli
~~~~~~~~~~~

"""
import logging

import click

from ..__about__ import __version__
from ..cli_defaultgroup import DefaultGroup
from ..log import setup_logger
from .sync import sync

log = logging.getLogger(__name__)


@click.group(cls=DefaultGroup)
@click.option(
    "--log-level",
    default="INFO",
    help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
)
@click.version_option(version=__version__, message="%(prog)s %(version)s")
def cli(log_level):
    setup_logger(log=log, level=log_level.upper())


# Register sub-commands here
cli.add_command(sync)
