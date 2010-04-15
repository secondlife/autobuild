#!/usr/bin/env python

import unittest
from autobuild import autobuild_main

class EarlyExitException(Exception):
    pass

class TestOptions(unittest.TestCase):
    def setUp(self):
        self.parser = autobuild_main.OptionParser()
        def mock_exit():
            raise EarlyExitException()
        self.parser.exit = mock_exit

    def test_empty_options(self):
        options, args = self.parser.parse_args([])
        assert options
        self.assertEquals(options.package_info, 'autobuild.xml')
        self.assertEquals(args, [])

    def test_help(self):
        try:
            options, args = self.parser.parse_args(['--help'])
            self.fail("hmm, that was supposed to exit")
        except EarlyExitException:
            pass

if __name__ == '__main__':
    unittest.main()

