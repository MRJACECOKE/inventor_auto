#!/usr/bin/env python3
"""Run all non-Inventor tests. No pip dependencies.

  python tests/run_tests.py            # all
  python tests/run_tests.py -v         # verbose
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    verbosity = 2 if "-v" in sys.argv else 1
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=HERE, pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
