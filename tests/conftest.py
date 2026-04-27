import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.logger import run_tracker


def pytest_runtest_teardown():
    run_tracker.CURRENT_RUN_TRACKER = None
