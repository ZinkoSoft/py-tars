"""Router service package for py-tars."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if _SRC_DIR.exists():
	src_path = str(_SRC_DIR)
	if src_path not in sys.path:
		sys.path.insert(0, src_path)

__all__ = ["_SRC_DIR"]
