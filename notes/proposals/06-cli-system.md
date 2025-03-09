# CLI System Proposal

> Restructuring the CLI system to improve maintainability, extensibility, and user experience.

## Current Issues

The audit identified several issues with the current CLI implementation:

1. **Argument Parsing**: Overloaded functions for parser creation add unnecessary complexity
2. **Sync Command Logic**: The sync command tries to handle multiple concerns simultaneously
3. **Lack of Command Pattern**: The CLI doesn't follow a command pattern that would make it more testable
4. **Error Handling**: Inconsistent error handling, with some errors raised as exceptions and others logged
5. **Duplicated Code**: Similar argument validation repeated across different command handlers

## Proposed Changes

### 1. Command Pattern Structure

1. **Command Interface**:
   ```python
   from abc import ABC, abstractmethod
   from argparse import ArgumentParser, Namespace
   from typing import List, Optional
   
   class Command(ABC):
       """Base class for CLI commands."""
       
       name: str  # Command name
       help: str  # Help text for command
       
       @abstractmethod
       def configure_parser(self, parser: ArgumentParser) -> None:
           """Configure the argument parser for this command."""
           pass
       
       @abstractmethod
       def execute(self, args: Namespace) -> int:
           """Execute the command with the parsed arguments."""
           pass
   ```

2. **Command Registry**:
   ```python
   class CommandRegistry:
       """Registry for CLI commands."""
       
       def __init__(self):
           self._commands = {}
       
       def register(self, command: Command) -> None:
           """Register a command."""
           self._commands[command.name] = command
       
       def get_command(self, name: str) -> Optional[Command]:
           """Get a command by name."""
           return self._commands.get(name)
       
       def get_all_commands(self) -> List[Command]:
           """Get all registered commands."""
           return list(self._commands.values())
   ```

3. **CLI Application**:
   ```python
   class CLI:
       """Main CLI application."""
       
       def __init__(self):
           self.registry = CommandRegistry()
           self._register_commands()
       
       def _register_commands(self) -> None:
           """Register all commands."""
           self.registry.register(SyncCommand())
           self.registry.register(DetectCommand())
           self.registry.register(LockCommand())
           self.registry.register(ApplyCommand())
       
       def create_parser(self) -> ArgumentParser:
           """Create the argument parser."""
           parser = ArgumentParser(
               description="VCSPull - synchronized multiple Git, SVN, and Mercurial repos"
           )
           
           # Add global arguments
           parser.add_argument(
               "--log-level", 
               choices=["debug", "info", "warning", "error", "critical"],
               default="info",
               help="Set log level"
           )
           
           # Add subparsers
           subparsers = parser.add_subparsers(dest="command", help="Command to execute")
           
           # Configure command parsers
           for command in self.registry.get_all_commands():
               command_parser = subparsers.add_parser(command.name, help=command.help)
               command.configure_parser(command_parser)
           
           return parser
       
       def run(self, args: List[str] = None) -> int:
           """Run the CLI application."""
           parser = self.create_parser()
           parsed_args = parser.parse_args(args)
           
           # Configure logging
           setup_logging(parsed_args.log_level)
           
           if not parsed_args.command:
               parser.print_help()
               return 1
           
           # Get and execute the command
           command = self.registry.get_command(parsed_args.command)
           if not command:
               logger.error(f"Unknown command: {parsed_args.command}")
               return 1
           
           try:
               return command.execute(parsed_args)
           except Exception as e:
               logger.error(f"Error executing command: {e}")
               if parsed_args.log_level.lower() == "debug":
                   logger.exception("Detailed error information:")
               return 1
   ```

### 2. Command Implementations

1. **Sync Command**:
   ```python
   class SyncCommand(Command):
       """Command to synchronize repositories."""
       
       name = "sync"
       help = "Synchronize repositories"
       
       def configure_parser(self, parser: ArgumentParser) -> None:
           """Configure the argument parser for sync command."""
           parser.add_argument(
               "-c", "--config", 
               dest="config_file",
               metavar="CONFIG_FILE",
               nargs="*",
               help="Specify config file(s)"
           )
           parser.add_argument(
               "repo_patterns",
               nargs="*",
               metavar="REPO_PATTERN",
               help="Repository patterns to filter (supports globbing)"
           )
           parser.add_argument(
               "-d", "--dry-run",
               action="store_true",
               help="Only show what would be done without making changes"
           )
       
       def execute(self, args: Namespace) -> int:
           """Execute the sync command."""
           try:
               # Load configuration
               config = load_config(*args.config_file if args.config_file else [])
               
               # Sync repositories
               results = sync_repositories(
                   config=config,
                   patterns=args.repo_patterns if args.repo_patterns else None,
                   dry_run=args.dry_run,
                   progress_callback=self._progress_callback
               )
               
               # Print results
               self._print_results(results)
               
               # Return success if all repos synced successfully
               return 0 if all(r["success"] for r in results.values()) else 1
           
           except ConfigurationError as e:
               logger.error(f"Configuration error: {e}")
               return 1
           except RepositoryError as e:
               logger.error(f"Repository error: {e}")
               return 1
       
       def _progress_callback(self, repo_name: str, current: int, total: int) -> None:
           """Progress callback for repository sync."""
           logger.info(f"[{current}/{total}] Processing {repo_name}")
       
       def _print_results(self, results: dict) -> None:
           """Print sync results."""
           for repo_name, result in results.items():
               status = "Success" if result["success"] else "Failed"
               logger.info(f"{repo_name}: {status} - {result['message']}")
   ```

2. **Detect Command**:
   ```python
   class DetectCommand(Command):
       """Command to detect repositories in a directory."""
       
       name = "detect"
       help = "Detect repositories in a directory"
       
       def configure_parser(self, parser: ArgumentParser) -> None:
           """Configure the argument parser for detect command."""
           parser.add_argument(
               "directory",
               help="Directory to scan for repositories"
           )
           parser.add_argument(
               "-r", "--recursive",
               action="store_true",
               default=True,
               help="Recursively scan subdirectories (default: true)"
           )
           parser.add_argument(
               "-s", "--include-submodules",
               action="store_true",
               help="Include Git submodules in detection"
           )
           parser.add_argument(
               "-o", "--output",
               help="Output file for detected repositories (YAML format)"
           )
           parser.add_argument(
               "-a", "--append",
               action="store_true",
               help="Append to existing config file instead of creating a new one"
           )
       
       def execute(self, args: Namespace) -> int:
           """Execute the detect command."""
           try:
               # Detect repositories
               repos = detect_repositories(
                   directory=args.directory,
                   recursive=args.recursive,
                   include_submodules=args.include_submodules
               )
               
               # Print discovered repositories
               logger.info(f"Detected {len(repos)} repositories:")
               for repo in repos:
                   logger.info(f"  {repo.name}: {repo.path} ({repo.vcs})")
               
               # Save to config file if specified
               if args.output:
                   self._save_to_config(repos, args.output, args.append)
               
               return 0
           
           except RepositoryError as e:
               logger.error(f"Repository detection error: {e}")
               return 1
       
       def _save_to_config(
           self, repos: List[Repository], output_file: str, append: bool
       ) -> None:
           """Save detected repositories to config file."""
           config = VCSPullConfig(repositories=repos)
           
           if append and os.path.exists(output_file):
               try:
                   existing_config = load_config(output_file)
                   # Merge repositories
                   for repo in config.repositories:
                       if not any(r.path == repo.path for r in existing_config.repositories):
                           existing_config.repositories.append(repo)
                   config = existing_config
               except ConfigurationError as e:
                   logger.warning(f"Could not load existing config, creating new one: {e}")
           
           save_config(config, output_file)
           logger.info(f"Saved configuration to {output_file}")
   ```

3. **Lock Command**:
   ```python
   class LockCommand(Command):
       """Command to lock repositories to their current revisions."""
       
       name = "lock"
       help = "Lock repositories to their current revisions"
       
       def configure_parser(self, parser: ArgumentParser) -> None:
           """Configure the argument parser for lock command."""
           parser.add_argument(
               "-c", "--config", 
               dest="config_file",
               metavar="CONFIG_FILE",
               nargs="*",
               help="Specify config file(s)"
           )
           parser.add_argument(
               "repo_patterns",
               nargs="*",
               metavar="REPO_PATTERN",
               help="Repository patterns to filter (supports globbing)"
           )
           parser.add_argument(
               "-o", "--output",
               default="vcspull.lock.json",
               help="Output lock file (default: vcspull.lock.json)"
           )
       
       def execute(self, args: Namespace) -> int:
           """Execute the lock command."""
           try:
               # Load configuration
               config = load_config(*args.config_file if args.config_file else [])
               
               # Lock repositories
               lock_info = lock_repositories(
                   config=config,
                   patterns=args.repo_patterns if args.repo_patterns else None,
                   lock_file=args.output
               )
               
               # Print results
               logger.info(f"Locked {len(lock_info)} repositories to {args.output}")
               return 0
           
           except ConfigurationError as e:
               logger.error(f"Configuration error: {e}")
               return 1
           except RepositoryError as e:
               logger.error(f"Repository error: {e}")
               return 1
   ```

4. **Apply Command**:
   ```python
   class ApplyCommand(Command):
       """Command to apply locked revisions to repositories."""
       
       name = "apply"
       help = "Apply locked revisions to repositories"
       
       def configure_parser(self, parser: ArgumentParser) -> None:
           """Configure the argument parser for apply command."""
           parser.add_argument(
               "-c", "--config", 
               dest="config_file",
               metavar="CONFIG_FILE",
               nargs="*",
               help="Specify config file(s)"
           )
           parser.add_argument(
               "-l", "--lock-file",
               default="vcspull.lock.json",
               help="Lock file to apply (default: vcspull.lock.json)"
           )
           parser.add_argument(
               "repo_patterns",
               nargs="*",
               metavar="REPO_PATTERN",
               help="Repository patterns to filter (supports globbing)"
           )
           parser.add_argument(
               "-d", "--dry-run",
               action="store_true",
               help="Only show what would be done without making changes"
           )
       
       def execute(self, args: Namespace) -> int:
           """Execute the apply command."""
           try:
               # Load configuration
               config = load_config(*args.config_file if args.config_file else [])
               
               # Apply locks
               results = apply_locks(
                   config=config,
                   lock_file=args.lock_file,
                   patterns=args.repo_patterns if args.repo_patterns else None,
                   dry_run=args.dry_run
               )
               
               # Print results
               for repo_name, result in results.items():
                   status = "Success" if result["success"] else "Failed"
                   logger.info(f"{repo_name}: {status} - {result['message']}")
               
               return 0 if all(r["success"] for r in results.values()) else 1
           
           except ConfigurationError as e:
               logger.error(f"Configuration error: {e}")
               return 1
           except RepositoryError as e:
               logger.error(f"Repository error: {e}")
               return 1
   ```

### 3. Rich Output and Terminal UI

1. **Rich Progress Bars**:
   ```python
   from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn
   
   def sync_with_progress(config, patterns=None, dry_run=False):
       """Synchronize repositories with rich progress display."""
       repos = filter_repositories(config, patterns)
       
       with Progress(
           TextColumn("[bold blue]{task.description}"),
           BarColumn(),
           TaskProgressColumn(),
           expand=True
       ) as progress:
           task = progress.add_task("Syncing repositories", total=len(repos))
           
           results = {}
           for i, repo in enumerate(repos, 1):
               progress.update(task, description=f"Syncing {repo.name}")
               
               try:
                   result = sync_repository(repo, dry_run=dry_run)
                   results[repo.name] = result
               except Exception as e:
                   results[repo.name] = {
                       "success": False,
                       "message": str(e),
                       "details": {"error": repr(e)}
                   }
               
               progress.update(task, advance=1)
           
           return results
   ```

2. **Interactive Mode**:
   ```python
   from rich.prompt import Confirm
   
   class InteractiveSyncCommand(SyncCommand):
       """Interactive version of sync command."""
       
       name = "isync"
       help = "Interactive repository synchronization"
       
       def configure_parser(self, parser: ArgumentParser) -> None:
           """Configure the argument parser for interactive sync command."""
           super().configure_parser(parser)
           parser.add_argument(
               "-i", "--interactive",
               action="store_true",
               default=True,  # Always true for this command
               help=argparse.SUPPRESS
           )
       
       def execute(self, args: Namespace) -> int:
           """Execute the interactive sync command."""
           try:
               # Load configuration
               config = load_config(*args.config_file if args.config_file else [])
               
               # Filter repositories
               repos = filter_repositories(
                   config,
                   patterns=args.repo_patterns if args.repo_patterns else None
               )
               
               # Interactive sync
               return self._interactive_sync(repos, args.dry_run)
           
           except ConfigurationError as e:
               logger.error(f"Configuration error: {e}")
               return 1
           except RepositoryError as e:
               logger.error(f"Repository error: {e}")
               return 1
       
       def _interactive_sync(self, repos: List[Repository], dry_run: bool) -> int:
           """Interactive repository synchronization."""
           if not repos:
               logger.info("No repositories found.")
               return 0
           
           results = {}
           for repo in repos:
               logger.info(f"Repository: {repo.name} ({repo.path})")
               
               if Confirm.ask("Synchronize this repository?"):
                   try:
                       result = sync_repository(repo, dry_run=dry_run)
                       results[repo.name] = result
                       logger.info(f"Result: {'Success' if result['success'] else 'Failed'} - {result['message']}")
                   except Exception as e:
                       results[repo.name] = {
                           "success": False,
                           "message": str(e),
                           "details": {"error": repr(e)}
                       }
                       logger.error(f"Error: {e}")
               else:
                   logger.info("Skipped.")
           
           return 0 if all(r["success"] for r in results.values()) else 1
   ```

### 4. Consistent Error Handling

1. **Error Levels and User Messages**:
   ```python
   def handle_error(e: Exception, args: Namespace) -> int:
       """Handle exceptions with appropriate error messages."""
       if isinstance(e, ConfigurationError):
           logger.error(f"Configuration error: {e}")
           return 1
       elif isinstance(e, RepositoryError):
           logger.error(f"Repository error: {e}")
           return 1
       elif isinstance(e, VCSError):
           logger.error(f"VCS error ({e.vcs_type}): {e}")
           if args.log_level.lower() == "debug" and e.command:
               logger.debug(f"Command: {e.command}")
               logger.debug(f"Output: {e.output}")
           return 1
       else:
           logger.error(f"Unexpected error: {e}")
           if args.log_level.lower() == "debug":
               logger.exception("Detailed error information:")
           return 1
   ```

2. **Common Error Handling Implementation**:
   ```python
   class BaseCommand(Command):
       """Base class with common functionality for commands."""
       
       @abstractmethod
       def configure_parser(self, parser: ArgumentParser) -> None:
           """Configure the argument parser for this command."""
           pass
       
       @abstractmethod
       def run_command(self, args: Namespace) -> int:
           """Run the command implementation."""
           pass
       
       def execute(self, args: Namespace) -> int:
           """Execute the command with error handling."""
           try:
               return self.run_command(args)
           except Exception as e:
               return handle_error(e, args)
   ```

### 5. Command-Line Help and Documentation

1. **Improved Help Text**:
   ```python
   def create_main_parser() -> ArgumentParser:
       """Create the main argument parser with improved help."""
       parser = ArgumentParser(
           description="VCSPull - synchronized multiple Git, SVN, and Mercurial repos",
           epilog="""
Examples:
  vcspull sync                   # Sync all repositories in default config
  vcspull sync project*          # Sync repositories matching 'project*'
  vcspull sync -c custom.yaml    # Sync repositories from custom config file
  vcspull detect ~/projects      # Detect repositories in directory
  vcspull lock                   # Lock repositories to current revisions
  vcspull apply                  # Apply locked revisions to repositories
           """,
           formatter_class=argparse.RawDescriptionHelpFormatter
       )
       # ... other parser configuration
       return parser
   ```

2. **Command-Specific Help**:
   ```python
   def configure_sync_parser(parser: ArgumentParser) -> None:
       """Configure the sync command parser with detailed help."""
       parser.description = """
Synchronize repositories according to configuration.

This command will:
1. Clone repositories that don't exist locally
2. Update existing repositories to the latest version
3. Configure remotes as specified in the configuration

If repository patterns are provided, only repositories matching those patterns
will be synchronized. Patterns support Unix shell-style wildcards.
       """
       # ... argument configuration
   ```

### 6. YAML Output Format

1. **YAML Output Helper**:
   ```python
   def print_yaml_output(data, output_file=None):
       """Print data as YAML to stdout or file."""
       yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False)
       
       if output_file:
           with open(output_file, 'w') as f:
               f.write(yaml_str)
       else:
           print(yaml_str)
   ```

2. **JSON/YAML Output Arguments**:
   ```python
   def add_output_format_args(parser: ArgumentParser) -> None:
       """Add arguments for output format control."""
       group = parser.add_argument_group("output format")
       group.add_argument(
           "--json",
           action="store_true",
           help="Output in JSON format"
       )
       group.add_argument(
           "--yaml",
           action="store_true",
           help="Output in YAML format (default)"
       )
       group.add_argument(
           "--output-file",
           help="Write output to file instead of stdout"
       )
   ```

## Implementation Plan

1. **Phase 1: Command Pattern Structure**
   - Implement the Command base class
   - Create CommandRegistry
   - Implement CLI application class

2. **Phase 2: Core Commands**
   - Implement Sync command
   - Implement Detect command
   - Implement Lock and Apply commands

3. **Phase 3: Error Handling**
   - Implement consistent error handling
   - Update commands to use common error handling
   - Add debug logging

4. **Phase 4: Rich UI**
   - Add progress bar support
   - Implement interactive mode
   - Improve terminal output formatting

5. **Phase 5: Documentation**
   - Improve command help text
   - Add examples to help documentation
   - Create man pages

## Benefits

1. **Improved Maintainability**: Command pattern makes the code more maintainable
2. **Better Testability**: Commands can be tested in isolation
3. **Consistent User Experience**: Error handling and output formatting is consistent
4. **Extensibility**: New commands can be easily added
5. **Better Error Reporting**: Users get more actionable error messages
6. **Enhanced User Interface**: Progress bars and interactive mode improve usability

## Drawbacks and Mitigation

1. **Learning Curve for Contributors**:
   - Comprehensive documentation for command implementation
   - Examples of adding new commands
   - Clear guidelines for error handling

2. **Increased Complexity**:
   - Keep the command pattern implementation simple
   - Focus on practical use cases
   - Provide base classes for common functionality

3. **Breaking Changes**:
   - Ensure backward compatibility where possible
   - Deprecation warnings before removing features
   - Clear migration documentation

## Conclusion

The proposed CLI system will significantly improve the maintainability, testability, and user experience of VCSPull. By adopting the command pattern, we can create a more extensible CLI that is easier to maintain and test. The improved error handling and rich UI features will enhance the user experience, while the consistent design will make it easier for users to learn and use the tool effectively. 