# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$
#
# Integration test to exercise the archive packaging
#

import os
import subprocess
import sys
import tarfile
import unittest
import autobuild.autobuild_tool_package as package
from autobuild import configfile


class TestPackaging(unittest.TestCase):
    def setUp(self):
        this_dir = os.path.abspath(os.path.dirname(__file__))
        data_dir = os.path.join(this_dir, "data")
        self.config_path = os.path.join(data_dir, "autobuild-package.xml")
        self.config = configfile.ConfigurationDescription(self.config_path)
        self.tar_name = os.path.join(this_dir, "archive-test.tar.bz2")

    def test_package(self):
        package.package(self.config, 'linux', self.tar_name)
        assert os.path.exists(self.tar_name)
        tarball = tarfile.open(self.tar_name)
        assert [os.path.basename(f) for f in tarball.getnames()].sort() == \
            ['file3', 'file1', 'test1.txt'].sort()
            
    def test_autobuild_package(self):
        result = subprocess.call('autobuild package --config-file=%s --archive-name=%s -p linux' % \
            (self.config_path, self.tar_name), shell=True)
        assert result == 0
        assert os.path.exists(self.tar_name)
        tarball = tarfile.open(self.tar_name)
        assert [os.path.basename(f) for f in tarball.getnames()].sort() == \
            ['file3', 'file1', 'test1.txt'].sort()
        os.remove(self.tar_name)
        result = subprocess.call('autobuild package --config-file=%s -p linux --dry-run' % \
            (self.config_path), shell=True)
        assert result == 0
    
    def tearDown(self):
        if os.path.exists(self.tar_name):
            os.remove(self.tar_name)

if __name__ == '__main__':
    unittest.main()

