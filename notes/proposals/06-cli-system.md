# CLI System Proposal

> Restructuring the Command Line Interface to improve maintainability, extensibility, and user experience.

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
   import click
   from pathlib import Path
   
   from vcspull.cli.context import CliContext
   from vcspull.cli.options import common_options, config_option
   from vcspull.config import load_and_validate_config
   from vcspull.types import Repository
   
   @click.command()
   @common_options
   @config_option
   @click.option(
       "--repo", "-r", multiple=True,
       help="Repository names or patterns to sync (supports glob patterns)."
   )
   @click.pass_obj
   def sync(
       ctx: CliContext,
       config: t.Optional[Path] = None,
       repo: t.Optional[t.List[str]] = None
   ) -> int:
       """Synchronize repositories from configuration.
       
       This command clones or updates repositories based on the configuration.
       """
       try:
           # Load configuration
           config_obj = load_and_validate_config(config)
           
           # Filter repositories if patterns specified
           repositories = filter_repositories(config_obj.repositories, repo)
           
           if not repositories:
               ctx.error("No matching repositories found.")
               return 1
           
           # Sync repositories
           ctx.info(f"Syncing {len(repositories)} repositories...")
           
           for repository in repositories:
               try:
                   ctx.info(f"Syncing {repository.name}...")
                   # Sync repository logic
               except Exception as e:
                   ctx.error(f"Failed to sync {repository.name}: {e}")
           
           ctx.success("Sync completed successfully.")
           return 0
       except Exception as e:
           ctx.error(f"Sync failed: {e}")
           return 1
   
   def filter_repositories(
       repositories: t.List[Repository],
       patterns: t.Optional[t.List[str]]
   ) -> t.List[Repository]:
       """Filter repositories by name patterns.
       
       Parameters
       ----
       repositories : List[Repository]
           List of repositories to filter
       patterns : Optional[List[str]]
           List of patterns to match against repository names
           
       Returns
       ----
       List[Repository]
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
   # src/vcspull/cli/main.py
   import click
   
   from vcspull.cli.context import CliContext
   from vcspull.cli.commands.sync import sync
   from vcspull.cli.commands.info import info
   from vcspull.cli.commands.detect import detect
   
   @click.group()
   @click.option("--verbose", "-v", is_flag=True, help="Enable verbose output.")
   @click.option("--quiet", "-q", is_flag=True, help="Suppress output.")
   @click.version_option()
   @click.pass_context
   def cli(click_ctx, verbose: bool = False, quiet: bool = False):
       """VCSPull - Version Control System Repository Manager.
       
       This tool helps manage multiple version control repositories.
       """
       # Initialize our custom context
       ctx = CliContext(verbose=verbose, quiet=quiet)
       click_ctx.obj = ctx
   
   # Register commands
   cli.add_command(sync)
   cli.add_command(info)
   cli.add_command(detect)
   
   if __name__ == "__main__":
       cli()
   ```

3. **Benefits**:
   - Clear organization of commands
   - Commands can be tested in isolation
   - Easier to add new commands
   - Improved code readability

### 2. Context Management

1. **CLI Context Object**:
   ```python
   # src/vcspull/cli/context.py
   import typing as t
   import sys
   from pydantic import BaseModel, Field
   import click
   
   class CliContext(BaseModel):
       """Context for CLI commands.
       
       Manages state and utilities for command execution.
       """
       verbose: bool = False
       quiet: bool = False
       color: bool = True
       
       model_config = {
           "arbitrary_types_allowed": True
       }
       
       def info(self, message: str) -> None:
           """Display informational message.
           
           Parameters
           ----
           message : str
               Message to display
           """
           if not self.quiet:
               click.secho(message, fg="blue" if self.color else None)
       
       def success(self, message: str) -> None:
           """Display success message.
           
           Parameters
           ----
           message : str
               Message to display
           """
           if not self.quiet:
               click.secho(message, fg="green" if self.color else None)
       
       def warning(self, message: str) -> None:
           """Display warning message.
           
           Parameters
           ----
           message : str
               Message to display
           """
           if not self.quiet:
               click.secho(message, fg="yellow" if self.color else None)
       
       def error(self, message: str) -> None:
           """Display error message.
           
           Parameters
           ----
           message : str
               Message to display
           """
           click.secho(message, fg="red" if self.color else None, err=True)
       
       def debug(self, message: str) -> None:
           """Display debug message.
           
           Parameters
           ----
           message : str
               Message to display
           """
           if self.verbose and not self.quiet:
               click.secho(f"DEBUG: {message}", fg="cyan" if self.color else None)
   ```

2. **Dependency Management**:
   ```python
   # src/vcspull/cli/options.py
   import typing as t
   import click
   from pathlib import Path
   import functools
   
   def common_options(func):
       """Common options for all commands.
       
       Parameters
       ----
       func : Callable
           Command function to decorate
           
       Returns
       ----
       Callable
           Decorated function
       """
       @click.option(
           "--no-color", is_flag=True, help="Disable colored output."
       )
       @functools.wraps(func)
       def wrapper(*args, no_color: bool = False, **kwargs):
           # Get CLI context from Click
           ctx = click.get_current_context().obj
           # Update context
           ctx.color = not no_color
           # Call original function
           return func(*args, **kwargs)
       return wrapper
   
   def config_option(func):
       """Option for specifying configuration file.
       
       Parameters
       ----
       func : Callable
           Command function to decorate
           
       Returns
       ----
       Callable
           Decorated function
       """
       @click.option(
           "--config", "-c", type=click.Path(exists=True, dir_okay=False, path_type=Path),
           help="Path to configuration file."
       )
       @functools.wraps(func)
       def wrapper(*args, **kwargs):
           return func(*args, **kwargs)
       return wrapper
   ```

3. **Benefits**:
   - Centralized context management
   - Consistent output formatting
   - Easier to extend with new functionality
   - Improved testability

### 3. Improved Error Handling

1. **Structured Error Reporting**:
   ```python
   # src/vcspull/cli/errors.py
   import typing as t
   import sys
   import click
   from vcspull.exceptions import VCSPullError, ConfigError, VCSError
   
   def handle_exceptions(func):
       """Handle exceptions in CLI commands.
       
       Parameters
       ----
       func : Callable
           Command function to decorate
           
       Returns
       ----
       Callable
           Decorated function
       """
       from functools import wraps
       
       @wraps(func)
       def wrapper(*args, **kwargs):
           try:
               return func(*args, **kwargs)
           except ConfigError as e:
               ctx = click.get_current_context().obj
               ctx.error(f"Configuration error: {e}")
               if ctx.verbose:
                   import traceback
                   ctx.debug(traceback.format_exc())
               return 1
           except VCSError as e:
               ctx = click.get_current_context().obj
               ctx.error(f"VCS operation error: {e}")
               if ctx.verbose:
                   import traceback
                   ctx.debug(traceback.format_exc())
               return 1
           except VCSPullError as e:
               ctx = click.get_current_context().obj
               ctx.error(f"Error: {e}")
               if ctx.verbose:
                   import traceback
                   ctx.debug(traceback.format_exc())
               return 1
           except Exception as e:
               ctx = click.get_current_context().obj
               ctx.error(f"Unexpected error: {e}")
               if ctx.verbose:
                   import traceback
                   ctx.debug(traceback.format_exc())
               return 1
       
       return wrapper
   ```

2. **Usage in Commands**:
   ```python
   # src/vcspull/cli/commands/info.py
   import typing as t
   import click
   from pathlib import Path
   
   from vcspull.cli.context import CliContext
   from vcspull.cli.options import common_options, config_option
   from vcspull.cli.errors import handle_exceptions
   from vcspull.config import load_and_validate_config
   
   @click.command()
   @common_options
   @config_option
   @click.option(
       "--format", "-f", type=click.Choice(["text", "json"]), default="text",
       help="Output format."
   )
   @click.pass_obj
   @handle_exceptions
   def info(
       ctx: CliContext,
       config: t.Optional[Path] = None,
       format: str = "text"
   ) -> int:
       """Display information about repositories.
       
       Shows details about configured repositories.
       """
       # Load configuration
       config_obj = load_and_validate_config(config)
       
       if format == "json":
           # JSON output
           result = []
           for repo in config_obj.repositories:
               result.append({
                   "name": repo.name,
                   "url": repo.url,
                   "path": repo.path,
                   "vcs": repo.vcs
               })
           click.echo(json.dumps(result, indent=2))
       else:
           # Text output
           ctx.info(f"Found {len(config_obj.repositories)} repository configuration(s):")
           for repo in config_obj.repositories:
               ctx.info(f"- {repo.name} ({repo.vcs})")
               ctx.info(f"  URL: {repo.url}")
               ctx.info(f"  Path: {repo.path}")
       
       return 0
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
   from pydantic import BaseModel
   import click
   
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
       
       def progress_bar(self, length: int, label: str = "Progress") -> t.Optional[click.progressbar]:
           """Create a progress bar.
           
           Parameters
           ----
           length : int
               Total length of the progress bar
           label : str, optional
               Label for the progress bar, by default "Progress"
               
           Returns
           ----
           Optional[click.progressbar]
               Progress bar object or None if quiet
           """
           if self.quiet:
               return None
           
           return click.progressbar(
               length=length,
               label=label,
               show_eta=True,
               show_percent=True,
               fill_char="="
           )
       
       def spinner(self, text: str = "Working...") -> t.Optional[click.progressbar]:
           """Create a spinner for indeterminate progress.
           
           Parameters
           ----
           text : str, optional
               Text to display, by default "Working..."
               
           Returns
           ----
           Optional[click.progressbar]
               Spinner object or None if quiet
           """
           if self.quiet:
               return None
           
           import itertools
           import time
           import threading
           import sys
           
           spinner_symbols = itertools.cycle(["-", "/", "|", "\\"])
           
           class Spinner:
               def __init__(self, text):
                   self.text = text
                   self.running = False
                   self.spinner_thread = None
               
               def __enter__(self):
                   self.running = True
                   self.spinner_thread = threading.Thread(target=self._spin)
                   self.spinner_thread.start()
                   return self
               
               def __exit__(self, exc_type, exc_val, exc_tb):
                   self.running = False
                   if self.spinner_thread:
                       self.spinner_thread.join()
                   sys.stdout.write("\r")
                   sys.stdout.write(" " * (len(self.text) + 4))
                   sys.stdout.write("\r")
                   sys.stdout.flush()
               
               def _spin(self):
                   while self.running:
                       symbol = next(spinner_symbols)
                       sys.stdout.write(f"\r{symbol} {self.text}")
                       sys.stdout.flush()
                       time.sleep(0.1)
           
           return Spinner(text)
   ```

2. **Usage in Commands**:
   ```python
   # src/vcspull/cli/commands/sync.py 
   # In the sync command function
   
   # Get progress manager
   progress = ProgressManager(quiet=ctx.quiet)
   
   # Show progress during sync
   repos_to_sync = filter_repositories(config_obj.repositories, repo)
   
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
   ```

3. **Benefits**:
   - Visual feedback for long-running operations
   - Improved user experience
   - Optional (can be disabled with --quiet)
   - Consistent progress reporting across commands

### 5. Command Discovery and Help

1. **Enhanced Help System**:
   ```python
   # src/vcspull/cli/main.py
   import click
   
   # Define custom help formatter
   class VCSPullHelpFormatter(click.HelpFormatter):
       """Custom help formatter for VCSPull CLI."""
       
       def write_usage(self, prog, args='', prefix='Usage: '):
           """Write usage line with custom formatting."""
           super().write_usage(prog, args, prefix)
           # Add extra newline for readability
           self.write("\n")
       
       def write_heading(self, heading):
           """Write section heading with custom formatting."""
           self.write(f"\n{click.style(heading, fg='green', bold=True)}:\n")
   
   # Use custom formatter for CLI group
   @click.group(cls=click.Group, context_settings={
       "help_option_names": ["--help", "-h"],
       "max_content_width": 100
   })
   @click.version_option()
   @click.pass_context
   def cli(ctx):
       """VCSPull - Version Control System Repository Manager.
       
       This tool helps you manage multiple version control repositories.
       
       Basic Commands:
         sync      Clone or update repositories
         info      Show information about repositories
         detect    Auto-detect repositories in a directory
       
       Configuration:
         VCSPull looks for configuration in:
         - ./.vcspull.yaml
         - ~/.vcspull.yaml
         - ~/.config/vcspull/config.yaml
       
       Examples:
         vcspull sync               # Sync all repositories
         vcspull sync -r project1   # Sync specific repository
         vcspull info --format json # Show repository info in JSON format
       """
       # Custom formatter for help text
       ctx.ensure_object(dict)
       ctx.obj["formatter"] = VCSPullHelpFormatter()
   ```

2. **Command Documentation**:
   ```python
   # src/vcspull/cli/commands/detect.py
   import typing as t
   import click
   from pathlib import Path
   
   from vcspull.cli.context import CliContext
   from vcspull.cli.options import common_options
   from vcspull.cli.errors import handle_exceptions
   
   @click.command()
   @common_options
   @click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path), default=".")
   @click.option(
       "--recursive", "-r", is_flag=True,
       help="Recursively search for repositories."
   )
   @click.option(
       "--max-depth", type=int, default=3,
       help="Maximum recursion depth (with --recursive)."
   )
   @click.pass_obj
   @handle_exceptions
   def detect(
       ctx: CliContext,
       directory: Path,
       recursive: bool = False,
       max_depth: int = 3
   ) -> int:
       """Detect version control repositories in a directory.
       
       This command scans the specified DIRECTORY for version control
       repositories and displays information about them.
       
       Examples:
       
         vcspull detect                   # Scan current directory
         vcspull detect ~/code            # Scan specific directory
         vcspull detect ~/code --recursive # Scan recursively
       """
       # Implementation
       ctx.info(f"Scanning {directory}{' recursively' if recursive else ''}...")
       # ...
       return 0
   ```

3. **Benefits**:
   - Improved command discoverability
   - Better help text formatting
   - Examples and usage guidance
   - Consistent command documentation

### 6. Configuration Integration

1. **Automated Configuration Discovery**:
   ```python
   # src/vcspull/cli/config.py
   import typing as t
   from pathlib import Path
   import os
   import click
   
   from vcspull.config import find_configs, load_and_validate_config
   from vcspull.schemas import VCSPullConfig
   
   def get_config(path: t.Optional[Path] = None) -> VCSPullConfig:
       """Get configuration from file or standard locations.
       
       Parameters
       ----
       path : Optional[Path], optional
           Explicit configuration path, by default None
           
       Returns
       ----
       VCSPullConfig
           Loaded and validated configuration
           
       Raises
       ----
       click.ClickException
           If no configuration is found or configuration is invalid
       """
       try:
           if path:
               # Explicit path provided
               return load_and_validate_config(path)
           
           # Find configuration in standard locations
           config_paths = find_configs()
           
           if not config_paths:
               # No configuration found
               raise click.ClickException(
                   "No configuration file found. Please create one or specify with --config."
               )
           
           # Load first found configuration
           return load_and_validate_config(config_paths[0])
       except Exception as e:
           # Wrap exceptions in ClickException for nice error reporting
           raise click.ClickException(f"Configuration error: {e}")
   ```

2. **Configuration Output**:
   ```python
   # src/vcspull/cli/commands/config.py
   import typing as t
   import click
   import json
   import yaml
   from pathlib import Path
   
   from vcspull.cli.context import CliContext
   from vcspull.cli.options import common_options
   from vcspull.cli.errors import handle_exceptions
   from vcspull.config import find_configs, load_and_validate_config
   from vcspull.schemas import VCSPullConfig
   
   @click.group(name="config")
   def config_group():
       """Configuration management commands."""
       pass
   
   @config_group.command(name="list")
   @common_options
   @click.pass_obj
   @handle_exceptions
   def list_configs(ctx: CliContext) -> int:
       """List available configuration files."""
       configs = find_configs()
       
       if not configs:
           ctx.warning("No configuration files found.")
           return 0
       
       ctx.info("Found configuration files:")
       for config_path in configs:
           ctx.info(f"- {config_path}")
       
       return 0
   
   @config_group.command(name="validate")
   @common_options
   @click.argument("config_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
   @click.pass_obj
   @handle_exceptions
   def validate_config(ctx: CliContext, config_file: Path) -> int:
       """Validate a configuration file."""
       try:
           config = load_and_validate_config(config_file)
           ctx.success(f"Configuration is valid: {config_file}")
           ctx.info(f"Found {len(config.repositories)} repositories")
           return 0
       except Exception as e:
           ctx.error(f"Invalid configuration: {e}")
           return 1
   
   @config_group.command(name="show-schema")
   @common_options
   @click.option(
       "--format", "-f", type=click.Choice(["json", "yaml"]), default="json",
       help="Output format for schema."
   )
   @click.pass_obj
   @handle_exceptions
   def show_schema(ctx: CliContext, format: str = "json") -> int:
       """Show JSON schema for configuration."""
       schema = VCSPullConfig.model_json_schema()
       
       if format == "yaml":
           click.echo(yaml.dump(schema, sort_keys=False))
       else:
           click.echo(json.dumps(schema, indent=2))
       
       return 0
   ```

3. **Benefits**:
   - Simplified configuration handling in commands
   - User-friendly configuration management
   - Schema documentation for users
   - Configuration validation tools

### 7. Rich Output Formatting

1. **Output Format System**:
   ```python
   # src/vcspull/cli/output.py
   import typing as t
   import json
   import yaml
   import click
   from pydantic import BaseModel
   
   class OutputFormatter:
       """Format command output in different formats."""
       
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
           if isinstance(data, BaseModel):
               data = data.model_dump()
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
           if isinstance(data, BaseModel):
               data = data.model_dump()
           return yaml.dump(data, sort_keys=False)
       
       @staticmethod
       def format_table(data: t.List[t.Dict[str, t.Any]], columns: t.List[str] = None) -> str:
           """Format data as an ASCII table.
           
           Parameters
           ----
           data : List[Dict[str, Any]]
               List of dictionaries to format as a table
           columns : List[str], optional
               Column names to include, by default all columns
               
           Returns
           ----
           str
               Formatted table string
           """
           if not data:
               return "No data"
           
           # Convert BaseModel instances to dictionaries
           formatted_data = []
           for item in data:
               if isinstance(item, BaseModel):
                   formatted_data.append(item.model_dump())
               else:
                   formatted_data.append(item)
           
           # Get all columns if not specified
           if not columns:
               columns = set()
               for item in formatted_data:
                   columns.update(item.keys())
               columns = sorted(columns)
           
           # Calculate column widths
           widths = {col: len(col) for col in columns}
           for item in formatted_data:
               for col in columns:
                   if col in item:
                       widths[col] = max(widths[col], len(str(item[col])))
           
           # Create table
           header = " | ".join(col.ljust(widths[col]) for col in columns)
           separator = "-+-".join("-" * widths[col] for col in columns)
           
           rows = []
           for item in formatted_data:
               row = " | ".join(
                   str(item.get(col, "")).ljust(widths[col]) for col in columns
               )
               rows.append(row)
           
           return "\n".join([header, separator] + rows)
   ```

2. **Usage in Commands**:
   ```python
   # src/vcspull/cli/commands/info.py
   # In the info command function
   
   from vcspull.cli.output import OutputFormatter
   
   # Get repositories info
   repos_info = []
   for repo in config_obj.repositories:
       repos_info.append({
           "name": repo.name,
           "url": repo.url,
           "path": repo.path,
           "vcs": repo.vcs or "unknown"
       })
   
   # Format output based on user selection
   if format == "json":
       click.echo(OutputFormatter.format_json(repos_info))
   elif format == "yaml":
       click.echo(OutputFormatter.format_yaml(repos_info))
   elif format == "table":
       click.echo(OutputFormatter.format_table(repos_info, columns=["name", "vcs", "path"]))
   else:
       # Text output
       for repo in repos_info:
           ctx.info(f"- {repo['name']} ({repo['vcs']})")
           ctx.info(f"  URL: {repo['url']}")
           ctx.info(f"  Path: {repo['path']}")
   ```

3. **Benefits**:
   - Consistent output formatting across commands
   - Multiple output formats for different use cases
   - Machine-readable outputs (JSON/YAML)
   - Pretty-printed human-readable output

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

These changes will make VCSPull easier to use for both new and existing users, while also simplifying future development by providing a clear, modular structure for CLI commands. 