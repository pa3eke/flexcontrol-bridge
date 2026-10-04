"""Entry point for source checkout and frozen desktop app."""
import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pa3eke_flexcontrol_bridge.gui import main

if __name__ == "__main__":
    main()
