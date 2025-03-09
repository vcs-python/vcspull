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
        return 1

    config = load_config(config_path)

    # Resolve includes
    config = resolve_includes(config, config_path.parent)

    # Print settings

    # Print repositories
    for repo in config.repositories:
        if repo.rev:
            pass
        if repo.remotes:
            pass

    # Example of using VCS handlers
    if config.repositories:
        repo = config.repositories[0]
        handler = get_vcs_handler(repo, config.settings.default_vcs)

        # Clone the repository if it doesn't exist
        if not handler.exists() and handler.clone():
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
