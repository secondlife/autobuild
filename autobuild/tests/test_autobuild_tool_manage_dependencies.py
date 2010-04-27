#!/usr/bin/env python

import os
import sys
import unittest
import autobuild.autobuild_tool_manage_dependencies

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
        this_dir = os.path.dirname(__file__)
        self.TESTFILENAME = os.path.join(this_dir, "data/dependencies_test_packages.xml")
        global captured_stdout
        captured_stdout = ''
        self.old_stdout = sys.stdout
        sys.stdout = CatchStdOut()
        self.old_stderr = sys.stderr
        sys.stderr = CatchStdOut()
        self.fixture = autobuild.autobuild_tool_manage_dependencies.autobuild_tool()
        def mock_exit(value=None, message=None):
            if(message):
                print message
            raise EarlyExitException()
        self.fixture.exit = mock_exit
        self.fixture.parser.exit = mock_exit
        pass

    def tearDown(self):
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr

        if(False):
            print '\nCaptured StdOut:\n****\n' + captured_stdout + '****\n'
        pass

    # first test via the standalone interface
    def test_empty_options(self):
        """test_empty_options: no options, should print usage and exit"""
        try:
            ret = self.fixture.main([])
            self.assertNotEquals(-1, captured_stdout.find('usage:'))
        except EarlyExitException:
            self.assertNotEquals(-1, captured_stdout.find('usage:'))
        pass

    def test_version(self):
        """test_version: make sure -v does the same (as we're here...) """
        try:
            ret = self.fixture.main(['-v'])
            self.assertNotEquals(-1, captured_stdout.find('dependencies tool module'))
        except EarlyExitException:
            self.assertNotEquals(-1, captured_stdout.find('dependencies tool module'))
        pass

    def test_tool_load(self):
        """test_tool_load: see if we can load a file and exit"""
        try:
            ret = self.fixture.main(['--package-name', self.TESTFILENAME])
            self.assertNotEquals(-1, captured_stdout.find("Package loaded"))
            self.assertNotEquals(-1, captured_stdout.find("Nothing to do..."))
        except EarlyExitException:
            self.fail()
        pass

    def test_tool_load_fails(self):
        """test_tool_load_fails: try a nonexistant file"""
        try:
            ret = self.fixture.main(['--package-name', 'packagefoobarfibblypoop.xml'])
            self.assertNotEquals(-1, captured_stdout.find("Package file not found"))
        except EarlyExitException:
            self.fail()
        pass

    def test_tool_add_a_package(self):
        """test_tool_add_a_package: see if we can add a package"""
        try:
            ret = self.fixture.main(['--package-name', self.TESTFILENAME,'--add','testpackage,,,,,,,','--dry-run'])
            self.assertNotEquals(-1, captured_stdout.find("Package loaded"))
            self.assertNotEquals(-1, captured_stdout.find("Adding testpackage"))
            # check file
        except EarlyExitException:
            self.fail()
        pass

    def test_tool_update_a_package(self):
        """test_tool_update_a_package: see if we can update a package"""
        try:
            ret = self.fixture.main(['--package-name', self.TESTFILENAME,'--add','llcommon,,,,,,,','--dry-run'])
            self.assertNotEquals(-1, captured_stdout.find("Package loaded"))
            self.assertNotEquals(-1, captured_stdout.find("Updating llcommon"))
            # check file
        except EarlyExitException:
            self.fail()
        pass

#    def test_tool_remove_a_package(self):
#        """test_tool_remove_a_package: see if we can remove a package"""
#        try:
#            ret = self.fixture.main(['--package-name', self.TESTFILENAME,'--remove','llcommon,,,,,,,','--dry-run'])
#            self.assertNotEquals(-1, captured_stdout.find("Package loaded"))
#            self.assertNotEquals(-1, captured_stdout.find("Removing llcommon"))
#            # check file
#        except EarlyExitException:
#            self.fail()
#        pass

if __name__ == '__main__':
    unittest.main()

