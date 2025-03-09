# CLI Tools Proposal

> Enhancing VCSPull's command-line tools with repository detection and version locking capabilities.

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

3. **Command Options**:
   ```
   Usage: vcspull detect [OPTIONS] [DIRECTORY]
   
   Options:
     -r, --recursive                 Recursively scan subdirectories (default: true)
     -d, --max-depth INTEGER         Maximum directory depth to scan
     --no-recursive                  Do not scan subdirectories
     -t, --type [git|hg|svn]         Only detect repositories of specified type
     -p, --pattern TEXT              Only include repositories matching pattern
     -s, --include-submodules        Include Git submodules as separate repositories
     -o, --output FILE               Save detected repositories to config file
     -a, --append                    Append to existing config file
     --json                          Output in JSON format
     --yaml                          Output in YAML format (default)
     --include-empty                 Include empty directories that have VCS artifacts
     --remotes                       Detect and include remote configurations
     --exclude-pattern TEXT          Exclude repositories matching pattern
     --help                          Show this message and exit
   ```

4. **Implementation Details**:
   ```python
   def detect_repositories(
       directory: Path,
       recursive: bool = True,
       max_depth: Optional[int] = None,
       repo_type: Optional[str] = None,
       include_pattern: Optional[str] = None,
       exclude_pattern: Optional[str] = None,
       include_submodules: bool = False,
       include_empty: bool = False,
       detect_remotes: bool = True
   ) -> List[Repository]:
       """Detect repositories in a directory.
       
       Args:
           directory: Directory to scan for repositories
           recursive: Whether to scan subdirectories
           max_depth: Maximum directory depth to scan
           repo_type: Only detect repositories of specified type (git, hg, svn)
           include_pattern: Only include repositories matching pattern
           exclude_pattern: Exclude repositories matching pattern
           include_submodules: Include Git submodules as separate repositories
           include_empty: Include empty directories that have VCS artifacts
           detect_remotes: Detect and include remote configurations
           
       Returns:
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

6. **Detection Results**:
   ```python
   # Example output format
   [
       {
           "name": "myrepo",
           "url": "git+https://github.com/user/myrepo.git",
           "path": "/home/user/projects/myrepo",
           "vcs": "git",
           "remotes": {
               "origin": "https://github.com/user/myrepo.git",
               "upstream": "https://github.com/upstream/myrepo.git"
           },
           "current_branch": "main"
       },
       # More repositories...
   ]
   ```

### 2. Repository Locking Tool

1. **Lock Command**:
   ```
   vcspull lock [OPTIONS] [REPO_PATTERNS]...
   ```

2. **Features**:
   - Lock repositories to specific revisions or branches
   - Save lock information to a lock file (JSON/YAML)
   - Lock all repositories or filter by name patterns
   - Different lock strategies (commit hash, tag, branch)
   - Include metadata about locked repositories
   - Option to verify repository state before locking

3. **Command Options**:
   ```
   Usage: vcspull lock [OPTIONS] [REPO_PATTERNS]...
   
   Options:
     -c, --config FILE              Config file(s) to use
     -o, --output FILE              Output lock file (default: vcspull.lock.json)
     -s, --strategy [commit|tag|branch]
                                   Locking strategy (default: commit)
     --verify                       Verify clean working tree before locking
     --include-metadata             Include additional repository metadata
     --json                         Output in JSON format (default)
     --yaml                         Output in YAML format
     --help                         Show this message and exit
   ```

4. **Implementation Details**:
   ```python
   def lock_repositories(
       config: VCSPullConfig,
       patterns: Optional[List[str]] = None,
       strategy: str = "commit",
       verify: bool = False,
       include_metadata: bool = False,
       lock_file: Optional[str] = None
   ) -> Dict[str, Dict[str, Any]]:
       """Lock repositories to their current revisions.
       
       Args:
           config: Configuration object
           patterns: Repository patterns to filter
           strategy: Locking strategy (commit, tag, branch)
           verify: Verify clean working tree before locking
           include_metadata: Include additional repository metadata
           lock_file: Path to save lock file (if specified)
           
       Returns:
           Dictionary of locked repository information
       """
       # Implementation
   ```

5. **Lock File Format**:
   ```json
   {
     "created_at": "2023-03-15T12:34:56Z",
     "vcspull_version": "1.0.0",
     "lock_strategy": "commit",
     "repositories": {
       "myrepo": {
         "url": "git+https://github.com/user/myrepo.git",
         "path": "/home/user/projects/myrepo",
         "vcs": "git",
         "locked_rev": "a1b2c3d4e5f6g7h8i9j0",
         "locked_branch": "main",
         "locked_tag": null,
         "locked_at": "2023-03-15T12:34:56Z",
         "metadata": {
           "author": "John Doe <john@example.com>",
           "date": "2023-03-10T15:30:45Z",
           "message": "Latest commit message"
         }
       },
       // More repositories...
     }
   }
   ```

6. **Lock Strategies**:
   - **Commit**: Lock to exact commit hash
   - **Tag**: Lock to the most recent tag
   - **Branch**: Lock to the branch name only (less precise)

### 3. Lock Application Tool

1. **Apply Command**:
   ```
   vcspull apply [OPTIONS] [REPO_PATTERNS]...
   ```

2. **Features**:
   - Apply locked revisions to repositories
   - Apply all locks or filter by name patterns
   - Dry-run mode to preview changes
   - Option to handle conflicts or uncommitted changes
   - Verification of applied versions

3. **Command Options**:
   ```
   Usage: vcspull apply [OPTIONS] [REPO_PATTERNS]...
   
   Options:
     -c, --config FILE               Config file(s) to use
     -l, --lock-file FILE            Lock file to use (default: vcspull.lock.json)
     -d, --dry-run                   Show what would be done without making changes
     --force                         Force checkout even with uncommitted changes
     --verify                        Verify applied versions match lock file
     --help                          Show this message and exit
   ```

4. **Implementation Details**:
   ```python
   def apply_locks(
       config: VCSPullConfig,
       lock_file: str,
       patterns: Optional[List[str]] = None,
       dry_run: bool = False,
       force: bool = False,
       verify: bool = True
   ) -> Dict[str, Dict[str, Any]]:
       """Apply locked revisions to repositories.
       
       Args:
           config: Configuration object
           lock_file: Path to lock file
           patterns: Repository patterns to filter
           dry_run: Only show what would be done without making changes
           force: Force checkout even with uncommitted changes
           verify: Verify applied versions match lock file
           
       Returns:
           Dictionary of results for each repository
       """
       # Implementation
   ```

5. **Application Process**:
   - Load lock file and validate
   - Match repositories in config with locked info
   - For each repository, check current state
   - Apply locked revision using appropriate VCS command
   - Verify the result and report success/failure

6. **Status Reporting**:
   ```
   Applying locked revisions from vcspull.lock.json:
   
   myrepo:
     Current: a1b2c3d (main)
     Locked:  a1b2c3d (already at locked revision)
     Status:  ✓ No change needed
   
   another-repo:
     Current: b2c3d4e (develop)
     Locked:  f6e5d4c (main)
     Status:  → Updating to locked revision
   
   third-repo:
     Current: <not found>
     Locked:  c3d4e5f (main)
     Status:  + Cloning at locked revision
   
   Summary: 3 repositories processed (1 updated, 1 cloned, 1 already current)
   ```

### 4. Enhanced Repository Information Tool

1. **Info Command**:
   ```
   vcspull info [OPTIONS] [REPO_PATTERNS]...
   ```

2. **Features**:
   - Display detailed information about repositories
   - Compare current state with locked versions
   - Show commit history, branches, and tags
   - Check for uncommitted changes
   - Display remote information and tracking branches

3. **Command Options**:
   ```
   Usage: vcspull info [OPTIONS] [REPO_PATTERNS]...
   
   Options:
     -c, --config FILE               Config file(s) to use
     -l, --lock-file FILE            Compare with lock file
     --show-commits INTEGER          Show recent commits (default: 5)
     --show-remotes                  Show remote information
     --show-branches                 Show branch information
     --show-status                   Show working tree status
     --json                          Output in JSON format
     --yaml                          Output in YAML format
     --help                          Show this message and exit
   ```

4. **Implementation Details**:
   ```python
   def get_repository_info(
       config: VCSPullConfig,
       patterns: Optional[List[str]] = None,
       lock_file: Optional[str] = None,
       show_commits: int = 5,
       show_remotes: bool = False,
       show_branches: bool = False,
       show_status: bool = False
   ) -> Dict[str, Dict[str, Any]]:
       """Get detailed information about repositories.
       
       Args:
           config: Configuration object
           patterns: Repository patterns to filter
           lock_file: Path to lock file for comparison
           show_commits: Number of recent commits to show
           show_remotes: Show remote information
           show_branches: Show branch information
           show_status: Show working tree status
           
       Returns:
           Dictionary of repository information
       """
       # Implementation
   ```

5. **Information Output**:
   ```
   Repository: myrepo
   Path: /home/user/projects/myrepo
   VCS: Git
   
   Current Revision: a1b2c3d4e5f6
   Current Branch: main
   
   Lock Status: Locked at a1b2c3d4e5f6 (current)
   
   Recent Commits:
     a1b2c3d - Fix bug in login component (John Doe, 2 days ago)
     b2c3d4e - Update documentation (Jane Smith, 4 days ago)
     c3d4e5f - Add new feature (John Doe, 1 week ago)
     
   Remotes:
     origin: https://github.com/user/myrepo.git (fetch)
     origin: https://github.com/user/myrepo.git (push)
     upstream: https://github.com/upstream/myrepo.git (fetch)
     upstream: https://github.com/upstream/myrepo.git (push)
     
   Branches:
     * main       a1b2c3d [origin/main] Latest commit message
       develop    d4e5f6g Feature in progress
       feature-x  e5f6g7h Experimental feature
   
   Status:
     M src/component.js
     ?? new-file.txt
   ```

### 5. Repository Synchronization Improvements

1. **Enhanced Sync Command**:
   ```
   vcspull sync [OPTIONS] [REPO_PATTERNS]...
   ```

2. **New Features**:
   - Progress bars for synchronization operations
   - Parallel processing for faster synchronization
   - Conflict resolution options
   - Support for branch switching during sync
   - Detailed logging and reporting
   - Interactive mode for manual approvals

3. **Command Options**:
   ```
   Usage: vcspull sync [OPTIONS] [REPO_PATTERNS]...
   
   Options:
     -c, --config FILE               Config file(s) to use
     -d, --dry-run                   Show what would be done without making changes
     -i, --interactive               Interactive mode with manual approvals
     -j, --jobs INTEGER              Number of parallel jobs (default: CPU count)
     --force                         Force operations even with conflicts
     --no-progress                   Disable progress bars
     --switch-branch                 Switch to the configured branch if different
     --depth INTEGER                 Git clone depth
     --help                          Show this message and exit
   ```

4. **Implementation Details**:
   ```python
   def sync_repositories(
       config: VCSPullConfig,
       patterns: Optional[List[str]] = None,
       dry_run: bool = False,
       interactive: bool = False,
       jobs: Optional[int] = None,
       force: bool = False,
       show_progress: bool = True,
       switch_branch: bool = False,
       clone_depth: Optional[int] = None,
       progress_callback: Optional[Callable] = None
   ) -> Dict[str, Dict[str, Any]]:
       """Synchronize repositories with enhanced features.
       
       Args:
           config: Configuration object
           patterns: Repository patterns to filter
           dry_run: Only show what would be done without making changes
           interactive: Interactive mode with manual approvals
           jobs: Number of parallel jobs
           force: Force operations even with conflicts
           show_progress: Show progress bars
           switch_branch: Switch to configured branch if different
           clone_depth: Git clone depth
           progress_callback: Custom progress callback
           
       Returns:
           Dictionary of sync results
       """
       # Implementation
   ```

5. **Parallel Processing**:
   ```python
   def sync_repositories_parallel(
       repos: List[Repository],
       jobs: int,
       dry_run: bool = False,
       **kwargs
   ) -> Dict[str, Dict[str, Any]]:
       """Synchronize repositories in parallel.
       
       Args:
           repos: List of repositories to sync
           jobs: Number of parallel jobs
           dry_run: Only show what would be done without making changes
           **kwargs: Additional arguments for repository sync
           
       Returns:
           Dictionary of sync results
       """
       with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
           futures = {
               executor.submit(
                   sync_repository, repo, dry_run=dry_run, **kwargs
               ): repo.name for repo in repos
           }
           
           results = {}
           for future in concurrent.futures.as_completed(futures):
               repo_name = futures[future]
               try:
                   results[repo_name] = future.result()
               except Exception as e:
                   results[repo_name] = {
                       "success": False,
                       "message": str(e),
                       "details": {"error": repr(e)}
                   }
           
           return results
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