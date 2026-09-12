import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent

for path in (str(SERVICE_ROOT), str(TESTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)