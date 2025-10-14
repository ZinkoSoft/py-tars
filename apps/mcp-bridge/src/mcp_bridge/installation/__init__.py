"""MCP server installation module.

Handles pip installation of discovered MCP servers:
- Editable installs for local packages and extensions
- PyPI installs for external packages
- Installation status tracking
- Rollback on failure
"""

from .pip_installer import PipInstaller
from .service import InstallationResult, InstallationService, InstallationStatus

__all__ = [
    "PipInstaller",
    "InstallationService",
    "InstallationResult",
    "InstallationStatus",
]
