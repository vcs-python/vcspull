# CLI Tools Proposal

> Enhancing VCSPull's command-line tools with repository detection and version locking capabilities using argparse with Python 3.9+ typing and optional shtab support.

## Current Issues

The audit identified several limitations in the current CLI tools:

1. **Limited Repository Detection**: No built-in way to discover existing repositories
2. **No Version Locking**: Inability to "lock" repositories to specific versions
3. **Inconsistent Command Interface**: Commands have varying parameter styles and return types
4. **Limited Filtering Options**: Basic repository filtering with limited flexibility

## Proposed CLI Tools

### 1. Repository Detection Tool

1. **Detection Command**:
   ```
   vcspull detect [OPTIONS] [DIRECTORY]
   ```

2. **Features**:
   - Scan directories for existing Git, Mercurial, and SVN repositories
   - Automatic detection of repository type (Git/Hg/SVN)
   - Save discovered repositories to new or existing config file
   - Filter repositories by type, name pattern, or depth
   - Option to include Git submodules as separate repositories
   - Detect remotes and include them in configuration

3. **Command Implementation**:
   ```python
   # src/vcspull/cli/commands/detect.py
   import typing as t
   from pathlib import Path
   import argparse
   
   from vcspull.cli.context import CliContext
   from vcspull.cli.registry import register_command
   from vcspull.operations import detect_repositories
   
   @register_command('detect')
   def add_detect_parser(subparsers: argparse._SubParsersAction) -> None:
       """Add detect command parser to the subparsers.
       
       Parameters
       ----------
       subparsers : argparse._SubParsersAction
           Subparsers object to add command to
       """
       parser = subparsers.add_parser(
           'detect',
           help="Detect repositories in a directory",
           description="Scan directories for existing Git, Mercurial, and SVN repositories"
       )
       
       # Add arguments
       parser.add_argument(
           "directory",
           type=Path,
           nargs="?",
           default=Path.cwd(),
           help="Directory to scan (default: current directory)"
       )
       parser.add_argument(
           "-r", "--recursive",
           action="store_true",
           default=True,
           help="Recursively scan subdirectories (default: true)"
       )
       parser.add_argument(
           "--no-recursive",
           action="store_false",
           dest="recursive",
           help="Do not scan subdirectories"
       )
       parser.add_argument(
           "-d", "--max-depth",
           type=int,
           help="Maximum directory depth to scan"
       )
       parser.add_argument(
           "-t", "--type",
           choices=["git", "hg", "svn"],
           help="Only detect repositories of specified type"
       )
       parser.add_argument(
           "-p", "--pattern",
           help="Only include repositories matching pattern"
       )
       parser.add_argument(
           "--exclude-pattern",
           help="Exclude repositories matching pattern"
       )
       parser.add_argument(
           "-s", "--include-submodules",
           action="store_true",
           help="Include Git submodules as separate repositories"
       )
       parser.add_argument(
           "-o", "--output",
           type=Path,
           help="Save detected repositories to config file"
       )
       parser.add_argument(
           "-a", "--append",
           action="store_true",
           help="Append to existing config file"
       )
       parser.add_argument(
           "--include-empty",
           action="store_true",
           help="Include empty directories that have VCS artifacts"
       )
       parser.add_argument(
           "--remotes",
           action="store_true",
           default=True,
           help="Detect and include remote configurations"
       )
       parser.add_argument(
           "--no-color",
           action="store_true",
           help="Disable colored output"
       )
       parser.add_argument(
           "--json",
           action="store_const",
           const="json",
           dest="output_format",
           help="Output in JSON format"
       )
       parser.add_argument(
           "--yaml",
           action="store_const",
           const="yaml",
           dest="output_format",
           default="yaml",
           help="Output in YAML format (default)"
       )
       
       # Set handler function
       parser.set_defaults(func=detect_command)
       
       # Add shtab completion (optional)
       try:
           import shtab
           shtab.add_argument_to(parser, [Path])
       except ImportError:
           pass
   
   def detect_command(args: argparse.Namespace, ctx: CliContext) -> int:
       """Detect repositories in a directory.
       
       Parameters
       ----------
       args : argparse.Namespace
           Parsed command arguments
       ctx : CliContext
           CLI context
       
       Returns
       -------
       int
           Exit code
       """
       try:
           # Update context from args
           ctx.color = not args.no_color if hasattr(args, 'no_color') else ctx.color
           
           ctx.info(f"Scanning for repositories in {args.directory}...")
           
           # Call detection function
           repositories = detect_repositories(
               directory=args.directory,
               recursive=args.recursive,
               max_depth=args.max_depth,
               repo_type=args.type,
               include_pattern=args.pattern,
               exclude_pattern=args.exclude_pattern,
               include_submodules=args.include_submodules,
               include_empty=args.include_empty,
               detect_remotes=args.remotes
           )
           
           if not repositories:
               ctx.warning("No repositories found.")
               return 0
           
           ctx.success(f"Found {len(repositories)} repositories.")
           
           # Output repositories
           if args.output:
               from vcspull.config import save_config
               from vcspull.config.models import VCSPullConfig
               
               if args.append and args.output.exists():
                   from vcspull.config import load_config
                   config = load_config(args.output)
                   # Add new repositories
                   existing_paths = {r.path for r in config.repositories}
                   for repo in repositories:
                       if repo.path not in existing_paths:
                           config.repositories.append(repo)
               else:
                   config = VCSPullConfig(repositories=repositories)
               
               save_config(config, args.output)
               ctx.success(f"Saved {len(repositories)} repositories to {args.output}")
           else:
               # Print repositories
               import json
               import yaml
               
               if args.output_format == "json":
                   print(json.dumps([r.model_dump() for r in repositories], indent=2))
               else:
                   print(yaml.dump([r.model_dump() for r in repositories], default_flow_style=False))
           
           return 0
       except Exception as e:
           ctx.error(f"Detection failed: {e}")
           if ctx.verbose:
               import traceback
               traceback.print_exc()
           return 1

4. **Implementation Details**:
   ```python
   # src/vcspull/operations.py
   
   def detect_repositories(
       directory: Path,
       recursive: bool = True,
       max_depth: t.Optional[int] = None,
       repo_type: t.Optional[str] = None,
       include_pattern: t.Optional[str] = None,
       exclude_pattern: t.Optional[str] = None,
       include_submodules: bool = False,
       include_empty: bool = False,
       detect_remotes: bool = True
   ) -> list[Repository]:
       """Detect repositories in a directory.
       
       Parameters
       ----------
       directory : Path
           Directory to scan for repositories
       recursive : bool
           Whether to scan subdirectories
       max_depth : Optional[int]
           Maximum directory depth to scan
       repo_type : Optional[str]
           Only detect repositories of specified type (git, hg, svn)
       include_pattern : Optional[str]
           Only include repositories matching pattern
       exclude_pattern : Optional[str]
           Exclude repositories matching pattern
       include_submodules : bool
           Include Git submodules as separate repositories
       include_empty : bool
           Include empty directories that have VCS artifacts
       detect_remotes : bool
           Detect and include remote configurations
           
       Returns
       -------
       list[Repository]
           List of detected Repository objects
       """
       # Implementation
   ```

5. **Detection Algorithm**:
   - Use parallel processing for faster scanning of large directory structures
   - Detect .git, .hg, and .svn directories using glob patterns
   - Use VCS commands to extract metadata (remotes, current branch, etc.)
   - Filter results based on specified criteria
   - Normalize repository paths

### 2. Version Locking Tool

1. **Version Lock Command**:
   ```
   vcspull lock [OPTIONS]
   ```

2. **Features**:
   - Create a lock file with specific repository versions
   - Lock all repositories or specific ones by name/pattern
   - Ensure repositories are on specific commits/tags
   - Support for different lock file formats

3. **Command Implementation**:
   ```python
   # src/vcspull/cli/commands/lock.py
   import typing as t
   from pathlib import Path
   import argparse
   
   from vcspull.cli.context import CliContext
   from vcspull.cli.registry import register_command
   from vcspull.operations import lock_repositories
   
   @register_command('lock')
   def add_lock_parser(subparsers: argparse._SubParsersAction) -> None:
       """Add lock command parser to the subparsers.
       
       Parameters
       ----------
       subparsers : argparse._SubParsersAction
           Subparsers object to add command to
       """
       parser = subparsers.add_parser(
           'lock',
           help="Create a lock file with specific repository versions",
           description="Lock repositories to specific versions"
       )
       
       # Add arguments
       parser.add_argument(
           "--config", "-c",
           type=Path,
           help="Path to configuration file"
       )
       parser.add_argument(
           "--output", "-o",
           type=Path,
           help="Output lock file path",
           default=Path("vcspull.lock")
       )
       parser.add_argument(
           "--repo", "-r",
           action="append",
           dest="repos",
           help="Repository names or patterns to lock (supports glob patterns)"
       )
       parser.add_argument(
           "--no-color",
           action="store_true",
           help="Disable colored output"
       )
       
       # Set handler function
       parser.set_defaults(func=lock_command)
       
       # Add shtab completion (optional)
       try:
           import shtab
           shtab.add_argument_to(parser, [Path])
       except ImportError:
           pass
   
   def lock_command(args: argparse.Namespace, ctx: CliContext) -> int:
       """Create a lock file with specific repository versions.
       
       Parameters
       ----------
       args : argparse.Namespace
           Parsed command arguments
       ctx : CliContext
           CLI context
       
       Returns
       -------
       int
           Exit code
       """
       try:
           # Update context from args
           ctx.color = not args.no_color if hasattr(args, 'no_color') else ctx.color
           
           from vcspull.config import load_config
           
           # Load configuration
           config = load_config(args.config)
           
           ctx.info(f"Locking repositories from {args.config or 'default config'}")
           
           # Filter repositories if patterns specified
           from vcspull.cli.utils import filter_repositories
           repos_to_lock = filter_repositories(config.repositories, args.repos)
           
           if not repos_to_lock:
               ctx.error("No matching repositories found.")
               return 1
           
           ctx.info(f"Locking {len(repos_to_lock)} repositories...")
           
           # Lock repositories
           lock_file = lock_repositories(repos_to_lock)
           
           # Save lock file
           lock_file.save(args.output)
           
           ctx.success(f"✓ Locked {len(repos_to_lock)} repositories to {args.output}")
           return 0
       except Exception as e:
           ctx.error(f"Locking failed: {e}")
           if ctx.verbose:
               import traceback
               traceback.print_exc()
           return 1
   ```

4. **Lock File Model**:
   ```python
   # src/vcspull/config/models.py
   
   class LockedRepository(BaseModel):
       """Repository with locked version information.
       
       Parameters
       ----------
       name : str
           Name of the repository
       path : Path
           Path to the repository
       vcs : str
           Version control system (git, hg, svn)
       url : str
           Repository URL
       revision : str
           Specific revision (commit hash, tag, etc.)
       """
       name: str
       path: Path
       vcs: str
       url: str
       revision: str
       
       model_config = ConfigDict(
           frozen=True,
       )
   
   class LockFile(BaseModel):
       """Lock file for repository versions.
       
       Parameters
       ----------
       repositories : list[LockedRepository]
           List of locked repositories
       """
       repositories: list[LockedRepository] = Field(default_factory=list)
       
       model_config = ConfigDict(
           frozen=True,
       )
       
       def save(self, path: Path) -> None:
           """Save lock file to disk.
           
           Parameters
           ----------
           path : Path
               Path to save lock file
           """
           import yaml
           
           # Ensure parent directory exists
           path.parent.mkdir(parents=True, exist_ok=True)
           
           # Convert to dictionary
           data = self.model_dump()
           
           # Save as YAML
           with open(path, "w") as f:
               yaml.dump(data, f, default_flow_style=False)
       
       @classmethod
       def load(cls, path: Path) -> "LockFile":
           """Load lock file from disk.
           
           Parameters
           ----------
           path : Path
               Path to lock file
           
           Returns
           -------
           LockFile
               Loaded lock file
           
           Raises
           ------
           FileNotFoundError
               If lock file does not exist
           """
           import yaml
           
           if not path.exists():
               raise FileNotFoundError(f"Lock file not found: {path}")
           
           # Load YAML
           with open(path, "r") as f:
               data = yaml.safe_load(f)
           
           # Create lock file
           return cls.model_validate(data)
   ```

### 3. Apply Version Lock Tool

1. **Apply Lock Command**:
   ```
   vcspull apply-lock [OPTIONS]
   ```

2. **Features**:
   - Apply lock file to ensure repositories are at specific versions
   - Validate current repository state against lock file
   - Update repositories to locked versions if needed

3. **Command Implementation**:
   ```python
   # src/vcspull/cli/commands/apply_lock.py
   import typing as t
   from pathlib import Path
   import argparse
   
   from vcspull.cli.context import CliContext
   from vcspull.cli.registry import register_command
   from vcspull.operations import apply_lock
   
   @register_command('apply-lock')
   def add_apply_lock_parser(subparsers: argparse._SubParsersAction) -> None:
       """Add apply-lock command parser to the subparsers.
       
       Parameters
       ----------
       subparsers : argparse._SubParsersAction
           Subparsers object to add command to
       """
       parser = subparsers.add_parser(
           'apply-lock',
           help="Apply lock file to ensure repositories are at specific versions",
           description="Update repositories to locked versions"
       )
       
       # Add arguments
       parser.add_argument(
           "--lock-file", "-l",
           type=Path,
           default=Path("vcspull.lock"),
           help="Path to lock file (default: vcspull.lock)"
       )
       parser.add_argument(
           "--repo", "-r",
           action="append",
           dest="repos",
           help="Repository names or patterns to update (supports glob patterns)"
       )
       parser.add_argument(
           "--verify-only",
           action="store_true",
           help="Only verify repositories, don't update them"
       )
       parser.add_argument(
           "--no-color",
           action="store_true",
           help="Disable colored output"
       )
       
       # Set handler function
       parser.set_defaults(func=apply_lock_command)
       
       # Add shtab completion (optional)
       try:
           import shtab
           shtab.add_argument_to(parser, [Path])
       except ImportError:
           pass
   
   def apply_lock_command(args: argparse.Namespace, ctx: CliContext) -> int:
       """Apply lock file to ensure repositories are at specific versions.
       
       Parameters
       ----------
       args : argparse.Namespace
           Parsed command arguments
       ctx : CliContext
           CLI context
       
       Returns
       -------
       int
           Exit code
       """
       try:
           # Update context from args
           ctx.color = not args.no_color if hasattr(args, 'no_color') else ctx.color
           
           from vcspull.config.models import LockFile
           
           # Load lock file
           lock_file = LockFile.load(args.lock_file)
           
           ctx.info(f"Applying lock file: {args.lock_file}")
           
           # Filter repositories if patterns specified
           from vcspull.cli.utils import filter_repositories
           repos_to_update = filter_repositories(lock_file.repositories, args.repos)
           
           if not repos_to_update:
               ctx.error("No matching repositories found in lock file.")
               return 1
           
           # Apply lock
           update_result = apply_lock(
               repos_to_update,
               verify_only=args.verify_only
           )
           
           # Display results
           for repo_name, (status, message) in update_result.items():
               if status == "success":
                   ctx.success(f"✓ {repo_name}: {message}")
               elif status == "mismatch":
                   ctx.warning(f"⚠ {repo_name}: {message}")
               elif status == "error":
                   ctx.error(f"✗ {repo_name}: {message}")
           
           # Check if any repositories had mismatches or errors
           has_mismatch = any(status == "mismatch" for status, _ in update_result.values())
           has_error = any(status == "error" for status, _ in update_result.values())
           
           if has_error:
               ctx.error("Some repositories had errors during update.")
               return 1
           if has_mismatch and args.verify_only:
               ctx.warning("Some repositories do not match the lock file.")
               return 1
           
           ctx.success("Lock file applied successfully.")
           return 0
       except Exception as e:
           ctx.error(f"Lock application failed: {e}")
           if ctx.verbose:
               import traceback
               traceback.print_exc()
           return 1
   ```

### 4. Command Line Entry Point

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
    ----------
    argv : Optional[list[str]]
        Command line arguments, defaults to sys.argv[1:] if not provided
    
    Returns
    -------
    int
        Exit code
    """
    # Create argument parser
    parser = argparse.ArgumentParser(
        description="VCSPull - Version Control System Repository Manager",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
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
    
    # Create default context
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

if __name__ == "__main__":
    sys.exit(main())
```

### 5. Shell Completion Support

1. **Shell Completion Integration**
   ```python
   # src/vcspull/cli/completion.py
   import typing as t
   import argparse
   
   def register_shtab_completion(parser: argparse.ArgumentParser) -> None:
       """Register shell completion for the parser.
       
       Parameters
       ----------
       parser : argparse.ArgumentParser
           Argument parser to register completion for
       """
       try:
           import shtab
           
           # Add shell completion arguments
           parser.add_argument(
               "--print-completion",
               action=shtab.SHELL_COMPLETION_ACTION,
               help="Print shell completion script"
           )
           
           # Register custom completions
           shtab.add_argument_to(
               parser,
               shell="bash",
               complete_help={
                   "vcspull detect": "Scan directories for existing repositories",
                   "vcspull sync": "Clone or update repositories from configuration",
                   "vcspull lock": "Create a lock file with specific repository versions",
                   "vcspull apply-lock": "Update repositories to locked versions",
               }
           )
       except ImportError:
           # shtab is not installed, skip registration
           pass
   ```

2. **Installation Instructions**
   ```
   # Install with completion support
   pip install vcspull[completion]
   
   # Generate and install bash completion
   vcspull --print-completion=bash > ~/.bash_completion.d/vcspull
   
   # Generate and install zsh completion
   vcspull --print-completion=zsh > ~/.zsh/completions/_vcspull
   ```

## Implementation Plan

### Phase 1: Repository Detection

1. **Core Detection Logic**:
   - Implement repository type detection
   - Add directory traversal with filtering
   - Implement metadata extraction

2. **Detection Command**:
   - Create command implementation
   - Add output formatting (JSON/YAML)
   - Implement config file generation

3. **Testing**:
   - Unit tests for detection logic
   - Integration tests with test repositories
   - Performance tests for large directory structures

### Phase 2: Repository Locking

1. **Lock File Format**:
   - Design and implement lock file schema
   - Create serialization/deserialization utilities
   - Implement versioning for lock files

2. **Lock Command**:
   - Implement locking logic for each VCS type
   - Add lock file generation
   - Support different lock strategies

3. **Apply Command**:
   - Implement application logic for each VCS type
   - Add verification of applied locks
   - Implement conflict resolution

### Phase 3: Enhanced Information and Sync

1. **Info Command**:
   - Implement repository information gathering
   - Add comparison with lock files
   - Create formatted output (terminal, JSON, YAML)

2. **Enhanced Sync**:
   - Add progress reporting
   - Implement parallel processing
   - Add interactive mode
   - Enhance conflict handling

### Phase 4: Integration and Documentation

1. **CLI Integration**:
   - Integrate all commands into CLI system
   - Ensure consistent interface and error handling
   - Add command help and examples

2. **Documentation**:
   - Create user documentation for new commands
   - Add examples and use cases
   - Update README and man pages

## Benefits

1. **Improved Repository Management**:
   - Easier discovery of existing repositories
   - Better control over repository versions
   - More detailed information about repositories

2. **Reproducible Environments**:
   - Lock file ensures consistent versions across environments
   - Easier collaboration with locked dependencies
   - Version tracking for project requirements

3. **Enhanced User Experience**:
   - Progress reporting for long-running operations
   - Parallel processing for faster synchronization
   - Interactive mode for fine-grained control

4. **Better Conflict Handling**:
   - Clear reporting of conflicts
   - Options for conflict resolution
   - Verification of successful operations

## Drawbacks and Mitigation

1. **Complexity**:
   - **Issue**: More features could lead to complex command interfaces
   - **Mitigation**: Group related options, provide sensible defaults, and use command groups

2. **Performance**:
   - **Issue**: Detection of repositories in large directory structures could be slow
   - **Mitigation**: Implement parallel processing, caching, and incremental scanning

3. **Backward Compatibility**:
   - **Issue**: New lock file format may not be compatible with existing workflows
   - **Mitigation**: Provide migration tools and backward compatibility options

## Conclusion

The proposed CLI tools will significantly enhance VCSPull's capabilities for repository management. The addition of repository detection, version locking, and improved synchronization will make it easier to manage multiple repositories consistently across environments. These tools will enable more reproducible development environments and smoother collaboration across teams. 