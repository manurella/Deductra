"""Packaging smoke tests for the Deductra foundation."""

from importlib.metadata import version

import deductra


def test_public_version_matches_installed_metadata() -> None:
    """The package exposes the version from its installed metadata."""
    assert deductra.__version__ == version("deductra")
