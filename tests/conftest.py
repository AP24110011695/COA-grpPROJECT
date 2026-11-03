"""Pytest bootstrap: put the project root on sys.path so test modules can
import `bots.*` and share fixtures from `test_smoke` regardless of whether
pytest is invoked as `python -m pytest` or plain `pytest`."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
