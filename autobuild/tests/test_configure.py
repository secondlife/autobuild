from __future__ import absolute_import
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
from .baseline_compare import AutobuildBaselineCompare
from autobuild import autobuild_tool_configure as configure
import autobuild.configfile as configfile
from autobuild.executable import Executable
import autobuild.common as common
import os, sys
from .basetest import BaseTest


class TestConfigure(BaseTest, AutobuildBaselineCompare):
    def setUp(self):
        BaseTest.setUp(self)
        os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.abspath(os.path.dirname(__file__))])
        self.tmp_file = self.get_tmp_file(0)
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        package = configfile.PackageDescription('test')
        package.license="LGPL"
        package.copyright="copy left"
        package.license_file="LICENSES/file"
        platform = configfile.PlatformDescription()
        build_configuration = configfile.BuildConfigurationDescription()
        # Formally you might consider that noop.py is an "argument" rather
        # than an "option" -- but the way Executable is structured, if we pass
        # it as an "argument" then the "build" subcommand gets inserted before
        # it, which thoroughly confuses the Python interpreter.
        build_configuration.configure = \
            Executable(command=sys.executable,
                       options=[os.path.join(os.path.dirname(__file__), "noop.py")])
        build_configuration.default = True
        build_configuration.name = 'Release'
        platform.configurations['Release'] = build_configuration
        package.platforms[common.get_current_platform()] = platform
        self.config.package_description = package
        self.config.save()

    def test_configure(self):
        # tests underlying API
        build_configuration = self.config.get_build_configuration('Release')
        result = configure._configure_a_configuration(self.config, build_configuration, [])
        assert result == 0
    
    def test_autobuild_configure(self):
        self.autobuild('configure', '--config-file=' + self.tmp_file, '--id=123456')
        self.autobuild('configure', '--config-file=' + self.tmp_file, '--id=123456', '--', '--foo', '-b')

    def test_substitutions(self):
        self.config.package_description.platforms[common.get_current_platform()] \
            .configurations['Release'].configure = \
            Executable("echo", arguments=["foo$AUTOBUILD_ADDRSIZE"])
        self.config.save()
        assert "foo32" in self.autobuild('configure', '--config-file=' + self.tmp_file,
                                        '-A', '32')
        assert "foo64" in self.autobuild('configure', '--config-file=' + self.tmp_file,
                                        '-A', '64')
    def test_id(self):
        self.config.package_description.platforms[common.get_current_platform()] \
            .configurations['Release'].configure = \
            Executable("echo", arguments=["foo$AUTOBUILD_BUILD_ID"])
        self.config.save()
        assert "foo666" in self.autobuild('configure', '--config-file=' + self.tmp_file,
                                        '-i', '666')

    def tearDown(self):
        self.cleanup_tmp_file()
        BaseTest.tearDown(self)

if __name__ == '__main__':
    unittest.main()

