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

import unittest
from baseline_compare import AutobuildBaselineCompare
from autobuild import autobuild_tool_configure as configure
import autobuild.configfile as configfile
from autobuild.executable import Executable
import autobuild.common as common
import subprocess
import os


class TestConfigure(unittest.TestCase, AutobuildBaselineCompare):
    def setUp(self):
        os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.abspath(os.path.dirname(__file__))])
        self.tmp_file = self.get_tmp_file(0)
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        package = configfile.PackageDescription('test')
        platform = configfile.PlatformDescription()
        build_configuration = configfile.BuildConfigurationDescription()
        build_configuration.configure = Executable(command="noop.py")
        build_configuration.default = True
        build_configuration.name = 'Release'
        platform.configurations['Release'] = build_configuration
        package.platforms[common.get_current_platform()] = platform
        self.config.package_description = package
        self.config.save()

    def test_configure(self):
        result = configure.configure(self.config, 'Release')
        assert result == 0
    
    def test_autobuild_configure(self):
        result = subprocess.call('autobuild configure --config-file=%s' % \
            self.tmp_file, shell=True)
        assert result == 0
        result = subprocess.call('autobuild configure --config-file=%s -- --foo -b' % \
            self.tmp_file, shell=True)
        assert result == 0

    def tearDown(self):
        self.cleanup_tmp_file()

if __name__ == '__main__':
    unittest.main()

