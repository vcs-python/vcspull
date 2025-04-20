"""URL handling for vcspull."""

from __future__ import annotations

from libvcs.url.git import DEFAULT_RULES

# Find the core-git-scp rule and modify it to be explicit
for rule in DEFAULT_RULES:
    if rule.label == "core-git-scp":
        # Make the rule explicit so it can be detected with is_explicit=True
        rule.is_explicit = True
        # Increase the weight to ensure it takes precedence
        rule.weight = 100
