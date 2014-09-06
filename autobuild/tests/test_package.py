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
import logging
import shutil
import tarfile
import tempfile
import unittest
from zipfile import ZipFile

import autobuild.autobuild_tool_package as package
from autobuild import configfile
from basetest import BaseTest, ExpectError, CaptureStdout, clean_dir
        

# ****************************************************************************
#   TODO
# - Test for specific --build-dir (new select_directories() mechanism)
# - Test packaging from configuration-specific build directory
# - Test packaging from --all configurations
# - Test packaging from build directory(ies) for specified --configuration(s)
# ****************************************************************************

logger=logging.getLogger("autobuild.test_package")


class TestPackaging(BaseTest):
    def setUp(self):
        BaseTest.setUp(self)
        self.temp_dir = tempfile.mkdtemp()
        # Copy our data_dir to temp_dir because loading a config file may
        # cause it to be updated and resaved.
        orig_data_dir = os.path.join(self.this_dir, "data")
        self.data_dir = os.path.join(self.temp_dir, "data")
        shutil.copytree(orig_data_dir, self.data_dir)
        self.config_path = os.path.join(self.data_dir, "autobuild-package-config.xml")
        self.config = configfile.ConfigurationDescription(self.config_path)
        self.platform = 'common'
        self.tar_basename = os.path.join(self.data_dir, "test1-1.0-common-123456")
        self.tar_name = self.tar_basename + ".tar.bz2"
        self.zip_name = self.tar_basename + ".zip"
        self.expected_files=['include/file1','LICENSES/test1.txt','autobuild-package.xml']
        self.expected_files.sort()

    def tearDown(self):
        clean_dir(self.temp_dir)
        BaseTest.tearDown(self)

    def tar_has_expected(self,tar):
        tarball = tarfile.open(tar, 'r:bz2')
        packaged_files=tarball.getnames()
        packaged_files.sort()
        self.assertEquals(packaged_files, self.expected_files)
        tarball.close()

    def zip_has_expected(self,zip):
        zip_file = ZipFile(zip,'r')
        packaged_files=zip_file.namelist()
        packaged_files.sort()
        self.assertEquals(packaged_files, self.expected_files)
        zip_file.close()

    def test_package(self):
        logger.setLevel(logging.DEBUG)
        package.package(self.config, self.config.get_build_directory(None, 'common'), 'common', archive_format='tbz2')
        assert os.path.exists(self.tar_name), "%s does not exist" % self.tar_name
        self.tar_has_expected(self.tar_name)

    def test_autobuild_package(self):
        with CaptureStdout() as stream:
            self.autobuild("package",
                           "--config-file=" + self.config_path,
                           "-p", "common")
        assert os.path.exists(self.tar_name), "%s does not exist" % self.tar_name
        self.tar_has_expected(self.tar_name)
        self.remove(self.tar_name)
        self.autobuild("package",
                       "--config-file=" + self.config_path,
                       "--archive-format=zip",
                       "-p", "common")
        assert os.path.exists(self.zip_name), "%s does not exist" % self.zip_name
        self.zip_has_expected(self.zip_name)
        self.remove(self.zip_name)

        self.autobuild("package",
                       "--config-file=" + self.config_path,
                       "-p", "common",
                       "--dry-run")
        assert not os.path.exists(self.zip_name), "%s created by dry run" % self.zip_name
        assert not os.path.exists(self.tar_name), "%s created by dry run" % self.tar_name

if __name__ == '__main__':
    unittest.main()
