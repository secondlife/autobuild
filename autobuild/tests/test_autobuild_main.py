# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# $/LicenseInfo$

import sys
import unittest
import autobuild.autobuild_main
from basetest import BaseTest

captured_stdout = ''

class EarlyExitException(Exception):
    pass

class CatchStdOut:
    def write(self, text):
        global captured_stdout
        captured_stdout += text
        pass

class TestOptions(BaseTest):
    def setUp(self):
        BaseTest.setUp(self)
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
        pass

    def tearDown(self):
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr
        sys.exit = self.old_exit

        if(False):
            print '\nCaptured StdOut:\n****\n' + captured_stdout + '****\n'
        pass
        BaseTest.tearDown(self)

    def test_empty_options(self):
        """test_empty_options: no options, should print usage and exit"""
        try:
            ret = self.autobuild_fixture.main([])
            self.fail()
        except EarlyExitException:
            self.assertNotEquals(-1, captured_stdout.find('usage:'))
        pass

    def test_typo_subtool(self):
        """test_typo_subtool: 'foobardribble' should print usage and exit"""
        try:
            ret = self.autobuild_fixture.main(['foobardribble'])
            self.fail()
        except EarlyExitException:
            self.assertNotEquals(-1, captured_stdout.find('usage:'))
        pass

    def test_version(self):
        """test_version: make sure -v does the same (as we're here...) """
        try:
            ret = self.autobuild_fixture.main(['-v'])
            self.fail()
        except EarlyExitException:
            self.assertNotEquals(-1, captured_stdout.find('autobuild'))
        pass

    def test_tool_register(self):
        """test_tool_register: check autobuild test finds & registers autobuild_tool_test.py"""
        try:
            ret = self.autobuild_fixture.main(['build', '-h'])
            self.fail()
        except EarlyExitException:
            self.assertNotEquals(-1, captured_stdout.find("an option to pass to the build command"))
        pass
        
    def test_tool_search_for_tools(self):
        """test_tool_search_for_tools: check that autobuild --help shows test tools help"""
        try:
            ret = self.autobuild_fixture.main(['--help'])
            self.fail()
        except EarlyExitException:
            self.assertNotEquals(-1, captured_stdout.find("Builds platform targets."))
        pass


if __name__ == '__main__':
    unittest.main()

