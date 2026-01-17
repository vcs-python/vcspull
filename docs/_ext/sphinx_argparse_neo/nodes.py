"""Custom docutils node types for argparse documentation.

This module defines custom node types that represent the structure of
CLI documentation, along with HTML visitor functions for rendering.
"""

from __future__ import annotations

import typing as t

from docutils import nodes

if t.TYPE_CHECKING:
    from sphinx.writers.html5 import HTML5Translator


class argparse_program(nodes.General, nodes.Element):
    """Root node for an argparse program documentation block.

    Attributes
    ----------
    prog : str
        The program name.

    Examples
    --------
    >>> node = argparse_program()
    >>> node["prog"] = "myapp"
    >>> node["prog"]
    'myapp'
    """

    pass


class argparse_usage(nodes.General, nodes.Element):
    """Node for displaying program usage.

    Contains the usage string as a literal block.

    Examples
    --------
    >>> node = argparse_usage()
    >>> node["usage"] = "myapp [-h] [--verbose] command"
    >>> node["usage"]
    'myapp [-h] [--verbose] command'
    """

    pass


class argparse_group(nodes.General, nodes.Element):
    """Node for an argument group (positional, optional, or custom).

    Attributes
    ----------
    title : str
        The group title.
    description : str | None
        Optional group description.

    Examples
    --------
    >>> node = argparse_group()
    >>> node["title"] = "Output Options"
    >>> node["title"]
    'Output Options'
    """

    pass


class argparse_argument(nodes.Part, nodes.Element):
    """Node for a single CLI argument.

    Attributes
    ----------
    names : list[str]
        Argument names/flags.
    help : str | None
        Help text.
    default : str | None
        Default value string.
    choices : list[str] | None
        Available choices.
    required : bool
        Whether the argument is required.
    metavar : str | None
        Metavar for display.

    Examples
    --------
    >>> node = argparse_argument()
    >>> node["names"] = ["-v", "--verbose"]
    >>> node["names"]
    ['-v', '--verbose']
    """

    pass


class argparse_subcommands(nodes.General, nodes.Element):
    """Container node for subcommands section.

    Examples
    --------
    >>> node = argparse_subcommands()
    >>> node["title"] = "Commands"
    >>> node["title"]
    'Commands'
    """

    pass


class argparse_subcommand(nodes.General, nodes.Element):
    """Node for a single subcommand.

    Attributes
    ----------
    name : str
        Subcommand name.
    aliases : list[str]
        Subcommand aliases.
    help : str | None
        Subcommand help text.

    Examples
    --------
    >>> node = argparse_subcommand()
    >>> node["name"] = "sync"
    >>> node["aliases"] = ["s"]
    >>> node["name"]
    'sync'
    """

    pass


# HTML Visitor Functions


def visit_argparse_program_html(self: HTML5Translator, node: argparse_program) -> None:
    """Visit argparse_program node - start program container.

    Parameters
    ----------
    self : HTML5Translator
        The Sphinx HTML translator.
    node : argparse_program
        The program node being visited.
    """
    prog = node.get("prog", "")
    self.body.append(f'<div class="argparse-program" data-prog="{prog}">\n')


def depart_argparse_program_html(self: HTML5Translator, node: argparse_program) -> None:
    """Depart argparse_program node - close program container.

    Parameters
    ----------
    self : HTML5Translator
        The Sphinx HTML translator.
    node : argparse_program
        The program node being departed.
    """
    self.body.append("</div>\n")


def visit_argparse_usage_html(self: HTML5Translator, node: argparse_usage) -> None:
    """Visit argparse_usage node - render usage block.

    Parameters
    ----------
    self : HTML5Translator
        The Sphinx HTML translator.
    node : argparse_usage
        The usage node being visited.
    """
    usage = node.get("usage", "")
    self.body.append('<pre class="argparse-usage">')
    self.body.append(f"usage: {self.encode(usage)}")


def depart_argparse_usage_html(self: HTML5Translator, node: argparse_usage) -> None:
    """Depart argparse_usage node - close usage block.

    Parameters
    ----------
    self : HTML5Translator
        The Sphinx HTML translator.
    node : argparse_usage
        The usage node being departed.
    """
    self.body.append("</pre>\n")


def visit_argparse_group_html(self: HTML5Translator, node: argparse_group) -> None:
    """Visit argparse_group node - start argument group.

    Parameters
    ----------
    self : HTML5Translator
        The Sphinx HTML translator.
    node : argparse_group
        The group node being visited.
    """
    title = node.get("title", "")
    group_id = title.lower().replace(" ", "-")
    self.body.append(f'<div class="argparse-group" data-group="{group_id}">\n')
    if title:
        self.body.append(f'<p class="argparse-group-title">{self.encode(title)}</p>\n')
    description = node.get("description")
    if description:
        self.body.append(
            f'<p class="argparse-group-description">{self.encode(description)}</p>\n'
        )
    self.body.append('<dl class="argparse-arguments">\n')


def depart_argparse_group_html(self: HTML5Translator, node: argparse_group) -> None:
    """Depart argparse_group node - close argument group.

    Parameters
    ----------
    self : HTML5Translator
        The Sphinx HTML translator.
    node : argparse_group
        The group node being departed.
    """
    self.body.append("</dl>\n")
    self.body.append("</div>\n")


def visit_argparse_argument_html(
    self: HTML5Translator, node: argparse_argument
) -> None:
    """Visit argparse_argument node - render argument entry.

    Parameters
    ----------
    self : HTML5Translator
        The Sphinx HTML translator.
    node : argparse_argument
        The argument node being visited.
    """
    names = node.get("names", [])
    names_str = ", ".join(names)
    metavar = node.get("metavar")

    # Build the argument signature
    signature = names_str
    if metavar:
        signature = f"{names_str} {metavar}"

    self.body.append(
        f'<dt class="argparse-argument-name">{self.encode(signature)}</dt>\n'
    )
    self.body.append('<dd class="argparse-argument-help">')

    # Add help text
    help_text = node.get("help")
    if help_text:
        self.body.append(f"<p>{self.encode(help_text)}</p>")


def depart_argparse_argument_html(
    self: HTML5Translator, node: argparse_argument
) -> None:
    """Depart argparse_argument node - close argument entry.

    Adds default, choices, and type information if present.

    Parameters
    ----------
    self : HTML5Translator
        The Sphinx HTML translator.
    node : argparse_argument
        The argument node being departed.
    """
    # Add metadata (default, choices, type)
    metadata: list[str] = []

    default = node.get("default_string")
    if default is not None:
        metadata.append(f"Default: {self.encode(default)}")

    choices = node.get("choices")
    if choices:
        choices_str = ", ".join(str(c) for c in choices)
        metadata.append(f"Choices: {self.encode(choices_str)}")

    type_name = node.get("type_name")
    if type_name:
        metadata.append(f"Type: {self.encode(type_name)}")

    required = node.get("required", False)
    if required:
        metadata.append("Required")

    if metadata:
        meta_str = " | ".join(metadata)
        self.body.append(f'<p class="argparse-argument-meta">{meta_str}</p>')

    self.body.append("</dd>\n")


def visit_argparse_subcommands_html(
    self: HTML5Translator, node: argparse_subcommands
) -> None:
    """Visit argparse_subcommands node - start subcommands section.

    Parameters
    ----------
    self : HTML5Translator
        The Sphinx HTML translator.
    node : argparse_subcommands
        The subcommands node being visited.
    """
    title = node.get("title", "Sub-commands")
    self.body.append('<div class="argparse-subcommands">\n')
    self.body.append(
        f'<p class="argparse-subcommands-title">{self.encode(title)}</p>\n'
    )


def depart_argparse_subcommands_html(
    self: HTML5Translator, node: argparse_subcommands
) -> None:
    """Depart argparse_subcommands node - close subcommands section.

    Parameters
    ----------
    self : HTML5Translator
        The Sphinx HTML translator.
    node : argparse_subcommands
        The subcommands node being departed.
    """
    self.body.append("</div>\n")


def visit_argparse_subcommand_html(
    self: HTML5Translator, node: argparse_subcommand
) -> None:
    """Visit argparse_subcommand node - start subcommand entry.

    Parameters
    ----------
    self : HTML5Translator
        The Sphinx HTML translator.
    node : argparse_subcommand
        The subcommand node being visited.
    """
    name = node.get("name", "")
    aliases = node.get("aliases", [])

    self.body.append(f'<div class="argparse-subcommand" data-name="{name}">\n')

    # Subcommand header
    header = name
    if aliases:
        alias_str = ", ".join(aliases)
        header = f"{name} ({alias_str})"
    self.body.append(
        f'<h4 class="argparse-subcommand-name">{self.encode(header)}</h4>\n'
    )

    # Help text
    help_text = node.get("help")
    if help_text:
        self.body.append(
            f'<p class="argparse-subcommand-help">{self.encode(help_text)}</p>\n'
        )


def depart_argparse_subcommand_html(
    self: HTML5Translator, node: argparse_subcommand
) -> None:
    """Depart argparse_subcommand node - close subcommand entry.

    Parameters
    ----------
    self : HTML5Translator
        The Sphinx HTML translator.
    node : argparse_subcommand
        The subcommand node being departed.
    """
    self.body.append("</div>\n")
