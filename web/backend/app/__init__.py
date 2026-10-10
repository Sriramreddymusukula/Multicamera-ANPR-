"""
Web API layer for the City-Wide AI Traffic Engine.

This package only ADDS a web interface on top of the existing
Python modules (config, database, analytics, detector, processing).
It never changes their behaviour; it imports and reuses them.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
