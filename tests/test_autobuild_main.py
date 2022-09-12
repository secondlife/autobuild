import sys

import autobuild.autobuild_main
from tests.basetest import BaseTest

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
                print(message)
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
            print('\nCaptured StdOut:\n****\n' + captured_stdout + '****\n')
        pass
        BaseTest.tearDown(self)

    def test_empty_options(self):
        """test_empty_options: no options, should print usage and exit"""
        try:
            ret = self.autobuild_fixture.main([])
            self.fail()
        except EarlyExitException:
            self.assertNotEqual(-1, captured_stdout.find('usage:'))
        pass

    def test_typo_subtool(self):
        """test_typo_subtool: 'foobardribble' should print usage and exit"""
        try:
            ret = self.autobuild_fixture.main(['foobardribble'])
            self.fail()
        except EarlyExitException:
            self.assertNotEqual(-1, captured_stdout.find('usage:'))
        pass

    def test_version(self):
        """test_version: make sure -v does the same (as we're here...) """
        try:
            ret = self.autobuild_fixture.main(['-v'])
            self.fail()
        except EarlyExitException:
            self.assertNotEqual(-1, captured_stdout.find('autobuild'))
        pass

    def test_tool_register(self):
        """test_tool_register: check autobuild test finds & registers autobuild_tool_test.py"""
        try:
            ret = self.autobuild_fixture.main(['build', '-h'])
            self.fail()
        except EarlyExitException:
            self.assertNotEqual(-1, captured_stdout.find("an option to pass to the build command"))
        pass

    def test_tool_search_for_tools(self):
        """test_tool_search_for_tools: check that autobuild --help shows test tools help"""
        try:
            ret = self.autobuild_fixture.main(['--help'])
            self.fail()
        except EarlyExitException:
            self.assertNotEqual(-1, captured_stdout.find("Builds platform targets."))
        pass
