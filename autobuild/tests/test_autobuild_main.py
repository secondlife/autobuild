#!/usr/bin/env python

import sys
import unittest
import autobuild.autobuild_main

captured_stdout = ''

class EarlyExitException(Exception):
    pass

class CatchStdOut:
    def write(self, text):
        global captured_stdout
        captured_stdout += text
        pass

class TestOptions(unittest.TestCase):
    def setUp(self):
        global captured_stdout
        captured_stdout = ''
        self.old_stdout = sys.stdout
        sys.stdout = CatchStdOut()
        self.old_stderr = sys.stderr
        sys.stderr = CatchStdOut()
        self.autobuild_fixture = autobuild.autobuild_main.Autobuild()
        def mock_exit(value=None, message=None):
            if(message):
                print message
            raise EarlyExitException()
        self.autobuild_fixture.exit = mock_exit
        self.autobuild_fixture.parser.exit = mock_exit
        self.old_exit = sys.exit
        sys.exit = mock_exit
        def mock_listdir(dir):
            return ['autobuild_tool_test.py']
        self.autobuild_fixture.listdir = mock_listdir
        pass

    def tearDown(self):
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr
        sys.exit = self.old_exit

        if(False):
            print '\nCaptured StdOut:\n****\n' + captured_stdout + '****\n'
        pass

    def test_empty_options(self):
        """test_empty_options: no options, should print usage and exit"""
        try:
            ret = self.autobuild_fixture.main([])
        except EarlyExitException:
            self.assertNotEquals(-1, captured_stdout.find('usage:'))
        pass

    def test_version(self):
        """test_version: make sure -v does the same (as we're here...) """
        try:
            ret = self.autobuild_fixture.main(['-v'])
            self.fail()
        except EarlyExitException:
            self.assertNotEquals(-1, captured_stdout.find('Autobuild'))
        pass

    def test_tool_register(self):
        """test_tool_register: check autobuild test finds & registers autobuild_tool_test.py"""
        try:
            ret = self.autobuild_fixture.main(['test', '-h'])
            self.fail()
        except EarlyExitException:
            self.assertNotEquals(-1, captured_stdout.find("Test Tool Internal Help"))
        pass
        
    def test_tool_search_for_tools(self):
        """test_tool_search_for_tools: check that autobuild --help shows test tools help"""
        try:
            ret = self.autobuild_fixture.main(['--help'])
            self.fail()
        except EarlyExitException:
            self.assertNotEquals(-1, captured_stdout.find("Test Tool for Autobuild"))
        pass
        
    def test_tool_version(self):
        """test_tool_version: check test tool has independent version"""
        try:
            ret = self.autobuild_fixture.main(['test', '-v'])
            self.fail()
        except EarlyExitException:
            self.assertNotEquals(-1, captured_stdout.find("test tool module 1.0"))
        pass
        
    def test_tool_run(self):
        """test_tool_run: ensure imported test tool runs when invoked with correct options"""
        try:
            ret = self.autobuild_fixture.main(['test', '--Test','x','y','z','-o','--option', '3'])
            self.assertNotEquals(-1, captured_stdout.find("the answer is:'3'xyz"))
        except EarlyExitException:
            self.assertNotEquals(-1, captured_stdout.find("test tool module 1.0"))
        pass


if __name__ == '__main__':
    unittest.main()

