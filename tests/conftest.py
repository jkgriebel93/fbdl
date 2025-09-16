# Ensure the src-based package layout is importable in tests without installation
import os
import sys
from pathlib import Path

# Compute the project root as the parent of this tests directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = PROJECT_ROOT / "src"

# Prepend to sys.path so `import fbdl` works in tests
sys.path.insert(0, str(SRC_PATH))
