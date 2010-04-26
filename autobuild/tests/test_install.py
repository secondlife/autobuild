#!/usr/bin/env python
#
# Integration test to exercise archive installation
#

import os
import sys
import shutil
import unittest
from autobuild import autobuild_tool_install

class FakeOptions:
    """
    Creates a fake argparse options structure to simulate
    passing in a number of command line options.
    """
    def __init__(self, config_file, manifest, install_dir):
        self.install_filename = config_file
        self.installed_filename = manifest
        self.install_dir = install_dir
        self.platform = "darwin"
        self.dry_run = False
        self.list_archives = False
        self.list_installed = False
        self.check_license = True
        self.list_licenses = False
        self.export_manifest = False

class TestInstall(unittest.TestCase):
    def setUp(self):
        """
        Create our fake cmd line options to point to our test files.
        """
        this_dir = os.path.dirname(__file__)
        data_dir = os.path.join(this_dir, "data")
        config_file = os.path.join(data_dir, "packages-install.xml")
        manifest_file = os.path.join(this_dir, "packages-installed.xml")
        install_dir = os.path.join(this_dir, "packages")
        self.options = FakeOptions(config_file, manifest_file, install_dir)

    def test_0(self):
        """
        Try to download and install the packages to tests/packages
        """
        autobuild_tool_install.install_packages(self.options, None)

        # do an extra check to make sure the install worked
        lic_dir = os.path.join(self.options.install_dir, "LICENSES")
        if not os.path.exists(lic_dir):
            self.fail("Installation did not install a LICENSES dir")

    def tearDown(self):
        """
        Remove any files that we downloaded/generated.
        """
        # remove the installed manifest file
        if os.path.exists(self.options.installed_filename):
            os.remove(self.options.installed_filename)

        # remove all the files extracted to our tmp packages dir
        shutil.rmtree(self.options.install_dir, True)

if __name__ == '__main__':
    unittest.main()

