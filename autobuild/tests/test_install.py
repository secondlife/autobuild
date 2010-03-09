#!/usr/bin/env python

import unittest
from autobuild import install

class TestOptions(unittest.TestCase):
    def setUp(self):
        self.installer = install.Installer("autobuild.xml",
                                           "autobuild-installed.xml",
                                           False)

    def test_0(self):
        pass

if __name__ == '__main__':
    unittest.main()

