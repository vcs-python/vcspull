"""CLI utilities for vcspull.

vcspull.cli
~~~~~~~~~~~

"""
import logging

import click

from libvcs.__about__ import __version__ as libvcs_version

from ..__about__ import __version__
from ..log import setup_logger
from .sync import sync

log = logging.getLogger(__name__)


@click.group()
@click.option(
    "--log-level",
    default="INFO",
    help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
)
@click.version_option(
    __version__,
    "-V",
    "--version",
    message=f"%(prog)s %(version)s, libvcs {libvcs_version}",
)
def cli(log_level):
    setup_logger(log=log, level=log_level.upper())


# Register sub-commands here
cli.add_command(sync)
