#!/usr/bin/env python

import unittest
from autobuild import autobuild_main

class TestOptions(unittest.TestCase):
    def setUp(self):
        self.parser = autobuild_main.OptionParser()

    def test_empty_options(self):
        options, args = self.parser.parse_args([])
        assert options
        self.assertEquals(options.package_info, 'autobuild.xml')
        self.assertEquals(args, [])

if __name__ == '__main__':
    unittest.main()

