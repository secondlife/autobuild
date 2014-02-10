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
#
# Integration test to exercise the archive packaging
#

import os
import sys
import tarfile
import unittest
import autobuild.autobuild_tool_package as package
from autobuild import configfile
from basetest import BaseTest
from zipfile import ZipFile

# ****************************************************************************
#   TODO
# - Test for specific --build-dir (new select_directories() mechanism)
# - Test packaging from configuration-specific build directory
# - Test packaging from --all configurations
# - Test packaging from build directory(ies) for specified --configuration(s)
# ****************************************************************************


class TestPackaging(BaseTest):
    def setUp(self):
        BaseTest.setUp(self)
        data_dir = os.path.join(self.this_dir, "data")
        self.config_path = os.path.join(data_dir, "autobuild-package.xml")
        self.config = configfile.ConfigurationDescription(self.config_path)
        self.platform = 'linux'
        #self.configuration = config.get_default_build_configurations()
        self.tar_basename = os.path.join(self.this_dir, "archive-test-123456")
        self.tar_name = self.tar_basename + ".tar.bz2"
        self.zip_name = self.tar_basename + ".zip"

    def test_package(self):
        package.package(self.config, self.config.get_build_directory(None, 'linux'), 'linux', '123456', self.tar_basename)
        assert os.path.exists(self.tar_name), "%s does not exist" % self.tar_name
        tarball = tarfile.open(self.tar_name)
        self.assertEquals([os.path.basename(f) for f in tarball.getnames()].sort(),
                          ['file3', 'file1', 'test1.txt'].sort())
        tarball.close()
            
    def test_autobuild_package(self):
        self.autobuild("package",
                       "--config-file=" + self.config_path,
                       "--archive-name=" + self.tar_basename,
                       "--id=123456",
                       "-p", "linux")
        assert os.path.exists(self.tar_name), "%s does not exist" % self.tar_name
        tarball = tarfile.open(self.tar_name)
        self.assertEquals([os.path.basename(f) for f in tarball.getnames()].sort(),
                          ['file3', 'file1', 'test1.txt'].sort())
        tarball.close()
        self.remove(self.tar_name)
        self.autobuild("package",
                       "--config-file=" + self.config_path,
                       "--archive-name=" + self.tar_basename,
                       "--archive-format=zip",
                       "--id=123456",
                       "-p", "linux")
        assert os.path.exists(self.zip_name), "%s does not exist" % self.zip_name
        zip_file = ZipFile(self.zip_name, 'r')
        self.assertEquals([os.path.basename(f) for f in zip_file.namelist()].sort(),
                          ['file3', 'file1', 'test1.txt'].sort())
        zip_file.close()
        self.autobuild("package",
                       "--config-file=" + self.config_path,
                       "-p", "linux", '--id=123456',
                       "--dry-run")
    
    def tearDown(self):
        if os.path.exists(self.tar_name):
            self.remove(self.tar_name)
        if os.path.exists(self.zip_name):
            self.remove(self.zip_name)
        BaseTest.tearDown(self)

if __name__ == '__main__':
    unittest.main()

