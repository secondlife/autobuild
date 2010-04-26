#!/usr/bin/env python
#
# Integration test to exercise the archive packaging
#

import os
import sys
import unittest
from autobuild import autobuild_tool_package

class FakeOptions:
    """
    Creates a fake argparse options structure to simulate
    passing in a number of command line options.
    """
    def __init__(self, config_file, build_dir, tar_name):
        self.autobuild_filename = config_file
        self.build_dir = build_dir
        self.archive_filename = tar_name
        self.platform = "linux"
        self.dry_run = False

class TestPackaging(unittest.TestCase):
    def setUp(self):
        """
        Create our fake cmd line options to point to our test files.
        """
        this_dir = os.path.dirname(__file__)
        data_dir = os.path.join(this_dir, "data")
        config_file = os.path.join(data_dir, "autobuild-package.xml")
        build_dir = os.path.join(data_dir, "package-test")
        tar_name = os.path.join(this_dir, "archive-test.tar.bz2")
        self.options = FakeOptions(config_file, build_dir, tar_name)

    def test_0(self):
        """
        Try to package the files in data/package-test/, as specified
        in the autobuild-package.xml config file. Creates a .tar.bz2
        archive if all went well.
        """
        autobuild_tool_package.create_archive(self.options)

    def tearDown(self):
        """
        Remove any archive file that we generated.
        """
        tar_name = self.options.archive_filename
        if os.path.exists(tar_name):
            os.remove(tar_name)

if __name__ == '__main__':
    unittest.main()

