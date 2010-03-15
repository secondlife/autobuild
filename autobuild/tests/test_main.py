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

    #def test_commands(self):
    #    for command in ['install', 'configure', 'build', 'package', 'upload']:
    #        autobuild_main.main([command, '--dry-run'])

if __name__ == '__main__':
    unittest.main()

