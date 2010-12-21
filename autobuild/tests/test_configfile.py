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
# Integration test to exercise the config file reading/writing
#

import unittest
import os
import sys
from baseline_compare import AutobuildBaselineCompare
from autobuild import configfile
from autobuild.executable import Executable


class TestConfigFile(unittest.TestCase, AutobuildBaselineCompare):

    def setUp(self):
        pass

    def test_configuration_simple(self):
        tmp_file = self.get_tmp_file(4)
        config = configfile.ConfigurationDescription(tmp_file)
        package = configfile.PackageDescription('test')
        config.package_description = package
        platform = configfile.PlatformDescription()
        platform.build_directory = '.'
        build_cmd = Executable(command="gcc", options=['-wall'])
        build_configuration = configfile.BuildConfigurationDescription()
        build_configuration.build = build_cmd
        platform.configurations['common'] = build_configuration
        config.package_description.platforms['common'] = platform
        config.save()
        
        reloaded = configfile.ConfigurationDescription(tmp_file)
        assert reloaded.package_description.platforms['common'].build_directory == '.'
        assert reloaded.package_description.platforms['common'].configurations['common'].build.get_command() == 'gcc'

    def tearDown(self):
        self.cleanup_tmp_file()


if __name__ == '__main__':
    unittest.main()

