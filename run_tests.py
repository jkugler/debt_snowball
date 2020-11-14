#!/usr/bin/python3

import os
#import shutil
import sys
import unittest

# Set up the test environment
opd = os.path.dirname
sys.path.insert(0, opd(os.path.abspath(__file__)))

import debt_snowball

from debt_snowball_tests import (unit, integration)

test_mods = [unit]

if __name__ == '__main__':
    if '--both' in sys.argv:
        test_mods.append(integration)
    elif '--integration' in sys.argv:
        test_mods = [integration]

    if '--quiet' in sys.argv:
        verbosity = 0
    else:
        verbosity = 2

    for tests in test_mods:
        suite = unittest.TestLoader().loadTestsFromModule(tests)
        unittest.TextTestRunner(verbosity=verbosity).run(suite)
