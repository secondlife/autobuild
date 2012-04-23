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
import subprocess
import sys
import tarfile
import unittest
import autobuild.autobuild_tool_package as package
from autobuild import configfile
from zipfile import ZipFile


class TestPackaging(unittest.TestCase):
    def setUp(self):
        this_dir = os.path.abspath(os.path.dirname(__file__))
        data_dir = os.path.join(this_dir, "data")
        self.config_path = os.path.join(data_dir, "autobuild-package.xml")
        self.config = configfile.ConfigurationDescription(self.config_path)
        self.platform = 'linux'
        #self.configuration = config.get_default_build_configurations()
        self.tar_basename = os.path.join(this_dir, "archive-test")
        self.tar_name = self.tar_basename + ".tar.bz2"
        self.zip_name = self.tar_basename + ".zip"
        self.autobuild_bin = os.path.abspath(os.path.join("..", "bin", "autobuild"))

    def test_package(self):
        package.package(self.config, self.config.get_build_directory(None, 'linux'), 'linux', self.tar_basename)
        assert os.path.exists(self.tar_name)
        tarball = tarfile.open(self.tar_name)
        assert [os.path.basename(f) for f in tarball.getnames()].sort() == \
            ['file3', 'file1', 'test1.txt'].sort()
            
    def test_autobuild_package(self):
        result = subprocess.call('%s package --config-file=%s --archive-name=%s -p linux' % \
            (self.autobuild_bin, self.config_path, self.tar_basename), shell=True)
        print '%s package --config-file=%s --archive-name=%s -p linux' % \
            (self.autobuild_bin, self.config_path, self.tar_basename)
        assert result == 0
        assert os.path.exists(self.tar_name)
        tarball = tarfile.open(self.tar_name)
        assert [os.path.basename(f) for f in tarball.getnames()].sort() == \
            ['file3', 'file1', 'test1.txt'].sort()
        os.remove(self.tar_name)
        result = subprocess.call('../bin/autobuild package --config-file=%s --archive-name=%s --archive-format=zip -p linux' % \
            (self.config_path, self.tar_basename), shell=True)
        assert result == 0
        assert os.path.exists(self.zip_name)
        zip_file = ZipFile(self.zip_name, 'r')
        assert [os.path.basename(f) for f in zip_file.namelist()].sort() == \
            ['file3', 'file1', 'test1.txt'].sort()
        result = subprocess.call('../bin/autobuild package --config-file=%s -p linux --dry-run' % \
            (self.config_path), shell=True)
        assert result == 0
    
    def tearDown(self):
        if os.path.exists(self.tar_name):
            os.remove(self.tar_name)
        if os.path.exists(self.zip_name):
            os.remove(self.zip_name)

if __name__ == '__main__':
    unittest.main()

