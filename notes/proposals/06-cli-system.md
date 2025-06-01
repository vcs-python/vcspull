# CLI System Proposal

> Restructuring the Command Line Interface to improve maintainability, extensibility, and user experience using argparse with Python 3.9+ strict typing and optional shtab integration.

## Current Issues

The audit identified several issues with the current CLI system:

1. **Monolithic Command Structure**: CLI commands are all defined in large monolithic files with complex nesting.

2. **Limited Command Discoverability**: Commands and options lack proper organization and documentation.

3. **Inconsistent Error Handling**: Error reporting is inconsistent across commands.

4. **Global State Dependencies**: Commands rely on global state, making testing difficult.

5. **Complex Option Parsing**: Manual option parsing instead of leveraging modern libraries.

6. **Lack of Progress Feedback**: Limited user feedback during long-running operations.

## Proposed Changes

### 1. Modular Command Structure

1. **Command Organization**:
   - Adopt a plugin-like architecture for commands
   - Create a clear command hierarchy
   - Separate command logic from CLI entry points

   ```python
   # src/vcspull/cli/commands/sync.py
   import typing as t
   from pathlib import Path
   import argparse
   
   from vcspull.cli.context import CliContext
   from vcspull.cli.registry import register_command
   from vcspull.config import load_and_validate_config
   from vcspull.types import Repository
   
   @register_command('sync')
   def add_sync_parser(subparsers: argparse._SubParsersAction) -> None:
       """Add sync command parser to the subparsers.
       
       Parameters
       ----
       subparsers : argparse._SubParsersAction
           Subparsers object to add command to
       """
       parser = subparsers.add_parser(
           'sync',
           help="Synchronize repositories from configuration",
           description="Clone or update repositories based on the configuration file"
       )
       
       # Add arguments
       parser.add_argument(
           "--config", "-c",
           type=Path,
           help="Path to configuration file"
       )
       parser.add_argument(
           "--repo", "-r",
           action="append",
           help="Repository names or patterns to sync (supports glob patterns)",
           dest="repos"
       )
       parser.add_argument(
           "--no-color",
           action="store_true",
           help="Disable colored output"
       )
       
       # Set handler function
       parser.set_defaults(func=sync_command)
       
       # Add shtab completion (optional)
       try:
           import shtab
           parser.add_argument(
               "--print-completion",
               action=shtab.SHELL_COMPLETION_ACTION,
               help="Print shell completion script"
           )
       except ImportError:
           pass
   
   def sync_command(args: argparse.Namespace, ctx: CliContext) -> int:
       """Synchronize repositories from configuration.
       
       Parameters
       ----
       args : argparse.Namespace
           Parsed command arguments
       ctx : CliContext
           CLI context
       
       Returns
       ----
       int
           Exit code
       """
       try:
           # Update context from args
           ctx.color = not args.no_color if hasattr(args, 'no_color') else ctx.color
           
           # Load configuration
           config_obj = load_and_validate_config(args.config)
           
           # Filter repositories if patterns specified
           repos_to_sync = filter_repositories(config_obj.repositories, args.repos)
           
           if not repos_to_sync:
               ctx.error("No matching repositories found.")
               return 1
           
           # Sync repositories
           ctx.info(f"Syncing {len(repos_to_sync)} repositories...")
           
           # Get progress manager
           from vcspull.cli.progress import ProgressManager
           progress = ProgressManager(quiet=ctx.quiet)
           
           # Show progress during sync
           with progress.progress_bar(len(repos_to_sync), "Syncing repositories") as bar:
               for repository in repos_to_sync:
                   ctx.info(f"Syncing {repository.name}...")
                   try:
                       # Sync repository
                       sync_repository(repository)
                       ctx.success(f"✓ {repository.name} synced successfully")
                   except Exception as e:
                       ctx.error(f"✗ Failed to sync {repository.name}: {e}")
                   
                   # Update progress bar
                   if bar:
                       bar.update(1)
           
           ctx.success("Sync completed successfully.")
           return 0
       except Exception as e:
           ctx.error(f"Sync failed: {e}")
           return 1
   
   def filter_repositories(
       repositories: list[Repository],
       patterns: t.Optional[list[str]]
   ) -> list[Repository]:
       """Filter repositories by name patterns.
       
       Parameters
       ----
       repositories : list[Repository]
           List of repositories to filter
       patterns : Optional[list[str]]
           List of patterns to match against repository names
           
       Returns
       ----
       list[Repository]
           Filtered repositories
       """
       if not patterns:
           return repositories
       
       import fnmatch
       result = []
       
       for repo in repositories:
           for pattern in patterns:
               if fnmatch.fnmatch(repo.name, pattern):
                   result.append(repo)
                   break
       
       return result
   ```

2. **Command Registry**:
   ```python
   # src/vcspull/cli/registry.py
   import typing as t
   import argparse
   import importlib
   import pkgutil
   from functools import wraps
   from pathlib import Path
   import inspect
   
   # Type for parser setup function
   ParserSetupFn = t.Callable[[argparse._SubParsersAction], None]
   
   # Registry to store command parser setup functions
   _COMMAND_REGISTRY: dict[str, ParserSetupFn] = {}
   
   def register_command(name: str) -> t.Callable[[ParserSetupFn], ParserSetupFn]:
       """Decorator to register a command parser setup function.
       
       Parameters
       ----
       name : str
           Name of the command
           
       Returns
       ----
       Callable
           Decorator function
       """
       def decorator(func: ParserSetupFn) -> ParserSetupFn:
           _COMMAND_REGISTRY[name] = func
           return func
       return decorator
   
   def setup_parsers(parser: argparse.ArgumentParser) -> None:
       """Set up all command parsers.
       
       Parameters
       ----
       parser : argparse.ArgumentParser
           Main parser to add subparsers to
       """
       # Create subparsers
       subparsers = parser.add_subparsers(
           title="commands",
           dest="command",
           help="Command to execute"
       )
       subparsers.required = True
       
       # Import all command modules to trigger registration
       import_commands()
       
       # Add all registered commands
       for _, setup_fn in sorted(_COMMAND_REGISTRY.items()):
           setup_fn(subparsers)
       
       # Add shtab completion (optional)
       try:
           import shtab
           parser.add_argument(
               "--print-completion",
               action=shtab.SHELL_COMPLETION_ACTION,
               help="Print shell completion script"
           )
       except ImportError:
           pass
   
   def import_commands() -> None:
       """Import all command modules to register commands."""
       from vcspull.cli import commands
       
       # Get the path to the commands package
       commands_pkg_path = Path(inspect.getfile(commands)).parent
       
       # Import all modules in the commands package
       prefix = f"{commands.__name__}."
       for _, name, is_pkg in pkgutil.iter_modules([str(commands_pkg_path)], prefix):
           if not is_pkg and name != f"{prefix}__init__":
               importlib.import_module(name)
   ```

3. **Benefits**:
   - Clear organization of commands using Python's type system
   - Commands can be tested in isolation
   - Automatic command discovery and registration
   - Shell tab completion via shtab (optional)
   - Strict typing for improved IDE support and error checking

### 2. Context Management

1. **CLI Context Object**:
   ```python
   # src/vcspull/cli/context.py
   import typing as t
   import sys
   from dataclasses import dataclass, field
   
   @dataclass
   class CliContext:
       """Context for CLI commands.
       
       Manages state and utilities for command execution.
       
       Parameters
       ----
       verbose : bool
           Whether to show verbose output
       quiet : bool
           Whether to suppress output
       color : bool
           Whether to use colored output
       """
       verbose: bool = False
       quiet: bool = False
       color: bool = True
       
       def info(self, message: str) -> None:
           """Display informational message.
           
           Parameters
           ----
           message : str
               Message to display
           """
           if not self.quiet:
               self._print_colored(message, "blue")
       
       def success(self, message: str) -> None:
           """Display success message.
           
           Parameters
           ----
           message : str
               Message to display
           """
           if not self.quiet:
               self._print_colored(message, "green")
       
       def warning(self, message: str) -> None:
           """Display warning message.
           
           Parameters
           ----
           message : str
               Message to display
           """
           if not self.quiet:
               self._print_colored(message, "yellow")
       
       def error(self, message: str) -> None:
           """Display error message.
           
           Parameters
           ----
           message : str
               Message to display
           """
           if not self.quiet:
               self._print_colored(message, "red", file=sys.stderr)
       
       def debug(self, message: str) -> None:
           """Display debug message when in verbose mode.
           
           Parameters
           ----
           message : str
               Message to display
           """
           if self.verbose and not self.quiet:
               self._print_colored(f"DEBUG: {message}", "cyan")
       
       def _print_colored(self, message: str, color: str, file: t.TextIO = sys.stdout) -> None:
           """Print colored message.
           
           Parameters
           ----
           message : str
               Message to print
           color : str
               Color name
           file : TextIO
               File to print to, defaults to stdout
           """
           if not self.color:
               print(message, file=file)
               return
           
           # Simple color codes for common terminals
           colors = {
               "red": "\033[31m",
               "green": "\033[32m",
               "yellow": "\033[33m",
               "blue": "\033[34m",
               "magenta": "\033[35m",
               "cyan": "\033[36m",
               "reset": "\033[0m",
           }
           
           print(f"{colors.get(color, '')}{message}{colors['reset']}", file=file)
   ```

2. **Shared Command Options**:
   ```python
   # src/vcspull/cli/options.py
   import typing as t
   import argparse
   from pathlib import Path
   import functools
   
   def common_options(parser: argparse.ArgumentParser) -> None:
       """Add common options to parser.
       
       Parameters
       ----
       parser : argparse.ArgumentParser
           Parser to add options to
       """
       parser.add_argument(
           "--no-color",
           action="store_true",
           help="Disable colored output"
       )
   
   def config_option(parser: argparse.ArgumentParser) -> None:
       """Add configuration file option to parser.
       
       Parameters
       ----
       parser : argparse.ArgumentParser
           Parser to add option to
       """
       parser.add_argument(
           "--config", "-c",
           type=Path,
           help="Path to configuration file"
       )
   ```

3. **Benefits**:
   - Consistent interface for all commands
   - Common utilities for user interaction
   - State management across command execution
   - Type safety through models

### 3. Improved Error Handling

1. **Structured Error Reporting**:
   ```python
   # src/vcspull/cli/errors.py
   import typing as t
   import sys
   import traceback
   
   from vcspull.cli.context import CliContext
   from vcspull.exceptions import VCSPullError, ConfigError, VCSError
   
   def handle_exception(e: Exception, ctx: CliContext) -> int:
       """Handle exception and return appropriate exit code.
       
       Parameters
       ----
       e : Exception
           Exception to handle
       ctx : CliContext
           CLI context
           
       Returns
       ----
       int
           Exit code
       """
       if isinstance(e, ConfigError):
           ctx.error(f"Configuration error: {e}")
       elif isinstance(e, VCSError):
           ctx.error(f"VCS operation error: {e}")
       elif isinstance(e, VCSPullError):
           ctx.error(f"Error: {e}")
       else:
           ctx.error(f"Unexpected error: {e}")
       
       if ctx.verbose:
           ctx.debug(traceback.format_exc())
       
       return 1
   ```

2. **Command Wrapper Function**:
   ```python
   # src/vcspull/cli/commands/common.py
   import typing as t
   import functools
   
   from vcspull.cli.context import CliContext
   from vcspull.cli.errors import handle_exception
   
   CommandFunc = t.Callable[[argparse.Namespace, CliContext], int]
   
   def command_wrapper(func: CommandFunc) -> CommandFunc:
       """Wrap command function with error handling.
       
       Parameters
       ----
       func : CommandFunc
           Command function to wrap
           
       Returns
       ----
       CommandFunc
           Wrapped function
       """
       @functools.wraps(func)
       def wrapper(args: argparse.Namespace, ctx: CliContext) -> int:
           try:
               return func(args, ctx)
           except Exception as e:
               return handle_exception(e, ctx)
       
       return wrapper
   ```

3. **Benefits**:
   - Consistent error handling across commands
   - Detailed error reporting in verbose mode
   - Clean error messages for users
   - Proper exit codes for scripts

### 4. Progress Reporting

1. **Progress Bar Integration**:
   ```python
   # src/vcspull/cli/progress.py
   import typing as t
   import threading
   import itertools
   import sys
   import time
   
   class ProgressManager:
       """Manager for CLI progress reporting."""
       
       def __init__(self, quiet: bool = False):
           """Initialize progress manager.
           
           Parameters
           ----
           quiet : bool, optional
               Whether to suppress output, by default False
           """
           self.quiet = quiet
       
       def progress_bar(self, total: int, label: str = "Progress"):
           """Create a progress bar context manager.
           
           Parameters
           ----
           total : int
               Total number of items
           label : str
               Label for the progress bar
               
           Returns
           ----
           ProgressBar
               Progress bar context manager
           """
           if self.quiet:
               return DummyProgressBar()
           return ProgressBar(total, label)
       
       def spinner(self, text: str = "Working..."):
           """Create a spinner for indeterminate progress.
           
           Parameters
           ----
           text : str
               Text to display
               
           Returns
           ----
           Spinner
               Spinner context manager
           """
           if self.quiet:
               return DummySpinner()
           return Spinner(text)
   
   
   class ProgressBar:
       """Progress bar for CLI applications."""
       
       def __init__(self, total: int, label: str = "Progress"):
           """Initialize progress bar.
           
           Parameters
           ----
           total : int
               Total number of items
           label : str
               Label for the progress bar
           """
           self.total = total
           self.label = label
           self.current = 0
           self.width = 40
           self.start_time = 0
       
       def __enter__(self):
           """Enter context manager."""
           self.start_time = time.time()
           self._draw()
           return self
       
       def __exit__(self, exc_type, exc_val, exc_tb):
           """Exit context manager."""
           self._draw()
           sys.stdout.write("\n")
           sys.stdout.flush()
       
       def update(self, n: int = 1):
           """Update progress bar.
           
           Parameters
           ----
           n : int
               Number of items to increment
           """
           self.current += n
           self._draw()
       
       def _draw(self):
           """Draw progress bar."""
           if self.total == 0:
               percent = 100
           else:
               percent = int(self.current * 100 / self.total)
           
           filled_width = int(self.width * self.current / self.total)
           bar = '=' * filled_width + ' ' * (self.width - filled_width)
           
           elapsed = time.time() - self.start_time
           if elapsed == 0:
               rate = 0
           else:
               rate = self.current / elapsed
           
           sys.stdout.write(f"\r{self.label}: [{bar}] {percent}% {self.current}/{self.total} ({rate:.1f}/s)")
           sys.stdout.flush()
   
   
   class Spinner:
       """Spinner for indeterminate progress."""
       
       def __init__(self, text: str = "Working..."):
           """Initialize spinner.
           
           Parameters
           ----
           text : str
               Text to display
           """
           self.text = text
           self.spinner_chars = itertools.cycle(["-", "/", "|", "\\"])
           self.running = False
           self.spinner_thread = None
       
       def __enter__(self):
           """Enter context manager."""
           self.running = True
           self.spinner_thread = threading.Thread(target=self._spin)
           self.spinner_thread.daemon = True
           self.spinner_thread.start()
           return self
       
       def __exit__(self, exc_type, exc_val, exc_tb):
           """Exit context manager."""
           self.running = False
           if self.spinner_thread:
               self.spinner_thread.join()
           sys.stdout.write("\r" + " " * (len(self.text) + 4) + "\r")
           sys.stdout.flush()
       
       def _spin(self):
           """Spin the spinner."""
           while self.running:
               char = next(self.spinner_chars)
               sys.stdout.write(f"\r{char} {self.text}")
               sys.stdout.flush()
               time.sleep(0.1)
   
   
   class DummyProgressBar:
       """Dummy progress bar that does nothing."""
       
       def __enter__(self):
           """Enter context manager."""
           return self
       
       def __exit__(self, exc_type, exc_val, exc_tb):
           """Exit context manager."""
           pass
       
       def update(self, n: int = 1):
           """Update progress bar.
           
           Parameters
           ----
           n : int
               Number of items to increment
           """
           pass
   
   
   class DummySpinner:
       """Dummy spinner that does nothing."""
       
       def __enter__(self):
           """Enter context manager."""
           return self
       
       def __exit__(self, exc_type, exc_val, exc_tb):
           """Exit context manager."""
           pass
   ```

2. **Benefits**:
   - Visual feedback for long-running operations
   - Improved user experience
   - Optional (can be disabled with --quiet)
   - Consistent progress reporting across commands

### 5. Command Discovery and Help

1. **Main CLI Entry Point**:
   ```python
   # src/vcspull/cli/main.py
   import typing as t
   import argparse
   import sys
   
   from vcspull.cli.context import CliContext
   from vcspull.cli.registry import setup_parsers
   
   def main(argv: t.Optional[list[str]] = None) -> int:
       """CLI entry point.
       
       Parameters
       ----
       argv : Optional[list[str]]
           Command line arguments, defaults to sys.argv[1:] if not provided
       
       Returns
       ----
       int
           Exit code
       """
       # Create argument parser
       parser = argparse.ArgumentParser(
           description="VCSPull - Version Control System Repository Manager",
           formatter_class=argparse.ArgumentDefaultsHelpFormatter,
           epilog="""
           Examples:
             vcspull sync               # Sync all repositories
             vcspull sync -r project1   # Sync specific repository
             vcspull detect ~/code      # Detect repositories in directory
           """
       )
       
       # Add global options
       parser.add_argument(
           "--verbose", "-v",
           action="store_true",
           help="Enable verbose output"
       )
       parser.add_argument(
           "--quiet", "-q",
           action="store_true",
           help="Suppress output"
       )
       parser.add_argument(
           "--version",
           action="store_true",
           help="Show version information and exit"
       )
       
       # Set up command parsers
       setup_parsers(parser)
       
       # Create context
       ctx = CliContext(verbose=False, quiet=False, color=True)
       
       # Parse arguments
       if argv is None:
           argv = sys.argv[1:]
       
       args = parser.parse_args(argv)
       
       # Show version if requested
       if args.version:
           from vcspull.__about__ import __version__
           print(f"VCSPull v{__version__}")
           return 0
       
       # Update context from args
       ctx.verbose = args.verbose
       ctx.quiet = args.quiet
       
       # Call command handler
       if hasattr(args, 'func'):
           return args.func(args, ctx)
       else:
           parser.print_help()
           return 1
   ```

2. **Benefits**:
   - Improved command discoverability
   - Better help text formatting
   - Examples and usage guidance
   - Consistent command documentation

### 6. Configuration Integration

1. **Configuration Helper Functions**:
   ```python
   # src/vcspull/cli/config_helpers.py
   import typing as t
   from pathlib import Path
   
   from vcspull.config import load_config, find_configs
   from vcspull.config.models import VCSPullConfig
   from vcspull.cli.context import CliContext
   
   def get_config(
       config_path: t.Optional[Path],
       ctx: CliContext
   ) -> t.Optional[VCSPullConfig]:
       """Get configuration from file or default locations.
       
       Parameters
       ----
       config_path : Optional[Path]
           Path to configuration file, or None to use default
       ctx : CliContext
           CLI context
       
       Returns
       ----
       Optional[VCSPullConfig]
           Loaded configuration, or None if not found or invalid
       """
       try:
           # Use specified config file if provided
           if config_path:
               ctx.debug(f"Loading configuration from {config_path}")
               return load_config(config_path)
           
           # Find configuration files
           config_files = find_configs()
           
           if not config_files:
               ctx.error("No configuration files found.")
               return None
           
           # Use first config file
           ctx.debug(f"Loading configuration from {config_files[0]}")
           return load_config(config_files[0])
       except Exception as e:
           ctx.error(f"Failed to load configuration: {e}")
           return None
   ```

2. **Benefits**:
   - Simplified configuration handling in commands
   - User-friendly error messages
   - Consistent configuration loading
   - Debug output for troubleshooting

### 7. Rich Output Formatting

1. **Output Formatter**:
   ```python
   # src/vcspull/cli/output.py
   import typing as t
   import json
   import yaml
   
   from pydantic import BaseModel
   
   class OutputFormatter:
       """Format output in different formats."""
       
       @staticmethod
       def format_json(data: t.Any) -> str:
           """Format data as JSON.
           
           Parameters
           ----
           data : Any
               Data to format
           
           Returns
           ----
           str
               Formatted JSON string
           """
           # Convert pydantic models to dict
           if isinstance(data, BaseModel):
               data = data.model_dump()
           elif isinstance(data, list) and data and isinstance(data[0], BaseModel):
               data = [item.model_dump() for item in data]
           
           return json.dumps(data, indent=2)
       
       @staticmethod
       def format_yaml(data: t.Any) -> str:
           """Format data as YAML.
           
           Parameters
           ----
           data : Any
               Data to format
           
           Returns
           ----
           str
               Formatted YAML string
           """
           # Convert pydantic models to dict
           if isinstance(data, BaseModel):
               data = data.model_dump()
           elif isinstance(data, list) and data and isinstance(data[0], BaseModel):
               data = [item.model_dump() for item in data]
           
           return yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
       
       @staticmethod
       def format_table(data: t.List[t.Dict[str, t.Any]], columns: t.Optional[list[str]] = None) -> str:
           """Format data as ASCII table.
           
           Parameters
           ----
           data : List[Dict[str, Any]]
               Data to format
           columns : Optional[list[str]]
               Columns to include, or None for all
           
           Returns
           ----
           str
               Formatted table string
           """
           if not data:
               return "No data"
           
           # Convert pydantic models to dict
           processed_data = []
           for item in data:
               if isinstance(item, BaseModel):
                   processed_data.append(item.model_dump())
               else:
                   processed_data.append(item)
           
           # Determine columns if not specified
           if columns is None:
               all_keys = set()
               for item in processed_data:
                   all_keys.update(item.keys())
               columns = sorted(all_keys)
           
           # Calculate column widths
           widths = {col: len(col) for col in columns}
           for item in processed_data:
               for col in columns:
                   if col in item:
                       widths[col] = max(widths[col], len(str(item.get(col, ""))))
           
           # Build table
           header_row = " | ".join(col.ljust(widths[col]) for col in columns)
           separator = "-+-".join("-" * widths[col] for col in columns)
           
           result = [header_row, separator]
           
           for item in processed_data:
               row = " | ".join(
                   str(item.get(col, "")).ljust(widths[col]) for col in columns
               )
               result.append(row)
           
           return "\n".join(result)
   ```

2. **Benefits**:
   - Consistent output formatting across commands
   - Multiple output formats for different use cases
   - Clean, readable output for users
   - Machine-readable formats (JSON, YAML) for scripts

## Implementation Plan

1. **Phase 1: Basic CLI Structure**
   - Create modular command structure
   - Implement CLI context
   - Set up basic error handling
   - Define shared command options

2. **Phase 2: Command Implementation**
   - Migrate existing commands to new structure
   - Add proper documentation to all commands
   - Implement missing command functionality
   - Add comprehensive tests

3. **Phase 3: Output Formatting**
   - Implement progress feedback
   - Add rich output formatting
   - Create table and structured output formats
   - Implement color and styling

4. **Phase 4: Configuration Integration**
   - Implement configuration discovery
   - Add configuration validation command
   - Create schema documentation command
   - Improve error messages for configuration issues

5. **Phase 5: User Experience Enhancement**
   - Improve help text and documentation
   - Add examples for all commands
   - Implement command completion
   - Create user guides

## Benefits

1. **Improved Maintainability**: Modular, testable command structure
2. **Better User Experience**: Rich output, progress feedback, and better error messages
3. **Enhanced Discoverability**: Improved help text and documentation
4. **Extensibility**: Easier to add new commands and features
5. **Testability**: Commands can be tested in isolation
6. **Consistency**: Uniform error handling and output formatting

## Drawbacks and Mitigation

1. **Migration Effort**:
   - Implement changes incrementally
   - Preserve backward compatibility for common commands
   - Document changes for users

2. **Learning Curve**:
   - Improved help text and examples
   - Comprehensive documentation
   - Intuitive command structure

## Conclusion

The proposed CLI system will significantly improve the maintainability, extensibility, and user experience of VCSPull. By restructuring the command system, enhancing error handling, and improving output formatting, we can create a more professional and user-friendly command-line interface.

These changes will make VCSPull easier to use for both new and existing users, while also simplifying future development by providing a clear, modular structure for CLI commands. 