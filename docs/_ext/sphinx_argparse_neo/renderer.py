"""Renderer - convert ParserInfo to docutils nodes.

This module provides the ArgparseRenderer class that transforms
structured parser information into docutils nodes for documentation.
"""

from __future__ import annotations

import typing as t

from docutils import nodes
from docutils.statemachine import StringList
from sphinx_argparse_neo.nodes import (
    argparse_argument,
    argparse_group,
    argparse_program,
    argparse_subcommand,
    argparse_subcommands,
    argparse_usage,
)
from sphinx_argparse_neo.parser import (
    ArgumentGroup,
    ArgumentInfo,
    MutuallyExclusiveGroup,
    ParserInfo,
    SubcommandInfo,
)

if t.TYPE_CHECKING:
    from docutils.parsers.rst.states import RSTStateMachine
    from sphinx.config import Config


@t.dataclass_transform()
class RenderConfig:
    """Configuration for the renderer.

    Examples
    --------
    >>> config = RenderConfig()
    >>> config.heading_level
    2
    >>> config.use_rubric
    False
    """

    heading_level: int = 2
    use_rubric: bool = False
    group_title_prefix: str = ""
    include_in_toc: bool = True
    toc_depth: int = 2
    flatten_subcommands: bool = False
    subcommand_style: str = "nested"
    show_defaults: bool = True
    show_choices: bool = True
    show_types: bool = True
    help_format: str = "rst"
    usage_style: str = "literal"

    def __init__(
        self,
        heading_level: int = 2,
        use_rubric: bool = False,
        group_title_prefix: str = "",
        include_in_toc: bool = True,
        toc_depth: int = 2,
        flatten_subcommands: bool = False,
        subcommand_style: str = "nested",
        show_defaults: bool = True,
        show_choices: bool = True,
        show_types: bool = True,
        help_format: str = "rst",
        usage_style: str = "literal",
    ) -> None:
        """Initialize render configuration."""
        self.heading_level = heading_level
        self.use_rubric = use_rubric
        self.group_title_prefix = group_title_prefix
        self.include_in_toc = include_in_toc
        self.toc_depth = toc_depth
        self.flatten_subcommands = flatten_subcommands
        self.subcommand_style = subcommand_style
        self.show_defaults = show_defaults
        self.show_choices = show_choices
        self.show_types = show_types
        self.help_format = help_format
        self.usage_style = usage_style

    @classmethod
    def from_sphinx_config(cls, config: Config) -> RenderConfig:
        """Create RenderConfig from Sphinx configuration.

        Parameters
        ----------
        config : Config
            Sphinx configuration object.

        Returns
        -------
        RenderConfig
            Render configuration based on Sphinx config values.
        """
        return cls(
            heading_level=getattr(config, "argparse_heading_level", 2),
            use_rubric=getattr(config, "argparse_use_rubric", False),
            group_title_prefix=getattr(config, "argparse_group_title_prefix", ""),
            include_in_toc=getattr(config, "argparse_include_in_toc", True),
            toc_depth=getattr(config, "argparse_toc_depth", 2),
            flatten_subcommands=getattr(config, "argparse_flatten_subcommands", False),
            subcommand_style=getattr(config, "argparse_subcommand_style", "nested"),
            show_defaults=getattr(config, "argparse_show_defaults", True),
            show_choices=getattr(config, "argparse_show_choices", True),
            show_types=getattr(config, "argparse_show_types", True),
            help_format=getattr(config, "argparse_help_format", "rst"),
            usage_style=getattr(config, "argparse_usage_style", "literal"),
        )


class ArgparseRenderer:
    """Render ParserInfo to docutils nodes.

    This class can be subclassed to customize rendering behavior.
    Override individual methods to change how specific elements are rendered.

    Parameters
    ----------
    config : RenderConfig
        Rendering configuration.
    state : RSTStateMachine | None
        RST state machine for parsing nested RST content.

    Examples
    --------
    >>> from sphinx_argparse_neo.parser import ParserInfo
    >>> config = RenderConfig()
    >>> renderer = ArgparseRenderer(config)
    >>> info = ParserInfo(
    ...     prog="myapp",
    ...     usage=None,
    ...     bare_usage="myapp [-h]",
    ...     description="My app",
    ...     epilog=None,
    ...     argument_groups=[],
    ...     subcommands=None,
    ...     subcommand_dest=None,
    ... )
    >>> result = renderer.render(info)
    >>> isinstance(result, list)
    True
    """

    def __init__(
        self,
        config: RenderConfig | None = None,
        state: RSTStateMachine | None = None,
    ) -> None:
        """Initialize the renderer."""
        self.config = config or RenderConfig()
        self.state = state

    def render(self, parser_info: ParserInfo) -> list[nodes.Node]:
        """Render a complete parser to docutils nodes.

        Parameters
        ----------
        parser_info : ParserInfo
            The parsed parser information.

        Returns
        -------
        list[nodes.Node]
            List of docutils nodes representing the documentation.
        """
        result: list[nodes.Node] = []

        # Create program container
        program_node = argparse_program()
        program_node["prog"] = parser_info.prog

        # Add description
        if parser_info.description:
            desc_nodes = self._parse_text(parser_info.description)
            program_node.extend(desc_nodes)

        # Add usage
        usage_node = self.render_usage(parser_info)
        program_node.append(usage_node)

        # Add argument groups
        for group in parser_info.argument_groups:
            group_node = self.render_group(group)
            program_node.append(group_node)

        # Add subcommands
        if parser_info.subcommands:
            subcommands_node = self.render_subcommands(parser_info.subcommands)
            program_node.append(subcommands_node)

        # Add epilog
        if parser_info.epilog:
            epilog_nodes = self._parse_text(parser_info.epilog)
            program_node.extend(epilog_nodes)

        result.append(program_node)
        return self.post_process(result)

    def render_usage(self, parser_info: ParserInfo) -> argparse_usage:
        """Render the usage block.

        Parameters
        ----------
        parser_info : ParserInfo
            The parser information.

        Returns
        -------
        argparse_usage
            Usage node.
        """
        usage_node = argparse_usage()
        usage_node["usage"] = parser_info.bare_usage
        return usage_node

    def render_group(self, group: ArgumentGroup) -> argparse_group:
        """Render an argument group.

        Parameters
        ----------
        group : ArgumentGroup
            The argument group to render.

        Returns
        -------
        argparse_group
            Group node containing argument nodes.
        """
        group_node = argparse_group()
        title = group.title
        if self.config.group_title_prefix:
            title = f"{self.config.group_title_prefix}{title}"
        group_node["title"] = title
        group_node["description"] = group.description

        # Add individual arguments
        for arg in group.arguments:
            arg_node = self.render_argument(arg)
            group_node.append(arg_node)

        # Add mutually exclusive groups
        for mutex in group.mutually_exclusive:
            mutex_nodes = self.render_mutex_group(mutex)
            group_node.extend(mutex_nodes)

        return group_node

    def render_argument(self, arg: ArgumentInfo) -> argparse_argument:
        """Render a single argument.

        Parameters
        ----------
        arg : ArgumentInfo
            The argument to render.

        Returns
        -------
        argparse_argument
            Argument node.
        """
        arg_node = argparse_argument()
        arg_node["names"] = arg.names
        arg_node["help"] = arg.help
        arg_node["metavar"] = arg.metavar
        arg_node["required"] = arg.required

        if self.config.show_defaults:
            arg_node["default_string"] = arg.default_string

        if self.config.show_choices:
            arg_node["choices"] = arg.choices

        if self.config.show_types:
            arg_node["type_name"] = arg.type_name

        return arg_node

    def render_mutex_group(
        self, mutex: MutuallyExclusiveGroup
    ) -> list[argparse_argument]:
        """Render a mutually exclusive group.

        Parameters
        ----------
        mutex : MutuallyExclusiveGroup
            The mutually exclusive group.

        Returns
        -------
        list[argparse_argument]
            List of argument nodes with mutex indicator.
        """
        result: list[argparse_argument] = []
        for arg in mutex.arguments:
            arg_node = self.render_argument(arg)
            # Mark as part of mutex group
            arg_node["mutex"] = True
            arg_node["mutex_required"] = mutex.required
            result.append(arg_node)
        return result

    def render_subcommands(
        self, subcommands: list[SubcommandInfo]
    ) -> argparse_subcommands:
        """Render subcommands section.

        Parameters
        ----------
        subcommands : list[SubcommandInfo]
            List of subcommand information.

        Returns
        -------
        argparse_subcommands
            Subcommands container node.
        """
        container = argparse_subcommands()
        container["title"] = "Sub-commands"

        for subcmd in subcommands:
            subcmd_node = self.render_subcommand(subcmd)
            container.append(subcmd_node)

        return container

    def render_subcommand(self, subcmd: SubcommandInfo) -> argparse_subcommand:
        """Render a single subcommand.

        Parameters
        ----------
        subcmd : SubcommandInfo
            The subcommand information.

        Returns
        -------
        argparse_subcommand
            Subcommand node, potentially containing nested parser content.
        """
        subcmd_node = argparse_subcommand()
        subcmd_node["name"] = subcmd.name
        subcmd_node["aliases"] = subcmd.aliases
        subcmd_node["help"] = subcmd.help

        # Recursively render the subcommand's parser
        if subcmd.parser:
            nested_nodes = self.render(subcmd.parser)
            subcmd_node.extend(nested_nodes)

        return subcmd_node

    def post_process(self, result_nodes: list[nodes.Node]) -> list[nodes.Node]:
        """Post-process the rendered nodes.

        Override this method to apply transformations after rendering.

        Parameters
        ----------
        result_nodes : list[nodes.Node]
            The rendered nodes.

        Returns
        -------
        list[nodes.Node]
            Post-processed nodes.
        """
        return result_nodes

    def _parse_text(self, text: str) -> list[nodes.Node]:
        """Parse text as RST or MyST content.

        Parameters
        ----------
        text : str
            Text to parse.

        Returns
        -------
        list[nodes.Node]
            Parsed docutils nodes.
        """
        if not text:
            return []

        if self.state is None:
            # No state machine available, return as paragraph
            para = nodes.paragraph(text=text)
            return [para]

        # Use the state machine to parse RST
        container = nodes.container()
        self.state.nested_parse(
            StringList(text.split("\n")),
            0,
            container,
        )
        return list(container.children)


def create_renderer(
    config: RenderConfig | None = None,
    state: RSTStateMachine | None = None,
    renderer_class: type[ArgparseRenderer] | None = None,
) -> ArgparseRenderer:
    """Create a renderer instance.

    Parameters
    ----------
    config : RenderConfig | None
        Rendering configuration.
    state : RSTStateMachine | None
        RST state machine for parsing.
    renderer_class : type[ArgparseRenderer] | None
        Custom renderer class to use.

    Returns
    -------
    ArgparseRenderer
        Configured renderer instance.
    """
    cls = renderer_class or ArgparseRenderer
    return cls(config=config, state=state)
