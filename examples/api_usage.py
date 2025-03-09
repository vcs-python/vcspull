#!/usr/bin/env python
"""Example script demonstrating VCSPull API usage."""

from __future__ import annotations

import sys
from pathlib import Path

# Add the parent directory to the path so we can import vcspull
sys.path.insert(0, str(Path(__file__).parent.parent))

from vcspull import load_config
from vcspull.config import resolve_includes
from vcspull.vcs import get_vcs_handler


def main() -> int:
    """Run the main application."""
    # Load configuration
    config_path = Path(__file__).parent / "vcspull.yaml"

    if not config_path.exists():
        print(f"Configuration file not found: {config_path}")
        return 1

    print(f"Loading configuration from {config_path}")
    config = load_config(config_path)

    # Resolve includes
    config = resolve_includes(config, config_path.parent)

    # Print settings
    print("\nSettings:")
    print(f"  sync_remotes: {config.settings.sync_remotes}")
    print(f"  default_vcs: {config.settings.default_vcs}")
    print(f"  depth: {config.settings.depth}")

    # Print repositories
    print(f"\nRepositories ({len(config.repositories)}):")
    for repo in config.repositories:
        print(f"  {repo.name or 'unnamed'}:")
        print(f"    url: {repo.url}")
        print(f"    path: {repo.path}")
        print(f"    vcs: {repo.vcs}")
        if repo.rev:
            print(f"    rev: {repo.rev}")
        if repo.remotes:
            print(f"    remotes: {repo.remotes}")

    # Example of using VCS handlers
    print("\nVCS Handler Example:")
    if config.repositories:
        repo = config.repositories[0]
        handler = get_vcs_handler(repo, config.settings.default_vcs)

        print(f"  Handler type: {type(handler).__name__}")
        print(f"  Repository exists: {handler.exists()}")

        # Clone the repository if it doesn't exist
        if not handler.exists():
            print(f"  Cloning repository {repo.name}...")
            if handler.clone():
                print("  Clone successful")
            else:
                print("  Clone failed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
