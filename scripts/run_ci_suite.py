"""Run every extractor unittest and fail if any optional gate was skipped."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(ROOT / "tests"), top_level_dir=str(ROOT / "tests")
    )
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.testsRun:
        print("CI failure: no tests were discovered", file=sys.stderr)
        return 1
    if result.skipped:
        print(f"CI failure: {len(result.skipped)} tests were skipped", file=sys.stderr)
        for test, reason in result.skipped:
            print(f"  {test}: {reason}", file=sys.stderr)
        return 1
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
