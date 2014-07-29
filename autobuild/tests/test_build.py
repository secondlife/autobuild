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
import logging
import pprint
from baseline_compare import AutobuildBaselineCompare
from autobuild import autobuild_tool_build as build
import autobuild.configfile as configfile
from autobuild.executable import Executable
import autobuild.common as common
import basetest
import tempfile
import os

# ****************************************************************************
#   TODO
# - Test for specific --build-dir (new select_directories() mechanism)
# - Test building to configuration-specific build directory
# - Test building to build trees for --all configurations
# - Test building to build directory(ies) for specified --configuration(s)
# ****************************************************************************
logger = logging.getLogger("autobuild.test_build")

class TestBuild(basetest.BaseTest, AutobuildBaselineCompare):
    def setUp(self):
        basetest.BaseTest.setUp(self)
        os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.abspath(os.path.dirname(__file__))])
        self.tmp_file = self.get_tmp_file(0)
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        package = configfile.PackageDescription('test')
        package.license="LGPL"
        package.version="0"
        platform = configfile.PlatformDescription()
        self.tmp_build_dir=tempfile.mkdtemp(prefix=os.path.dirname(self.tmp_file)+"/build-")
        platform.build_directory = self.tmp_build_dir
        build_configuration = configfile.BuildConfigurationDescription()
        build_configuration.build = Executable(command="noop.py")
        build_configuration.default = True
        build_configuration.name = 'Release'
        platform.configurations['Release'] = build_configuration
        package.platforms[common.get_current_platform()] = platform
        self.config.package_description = package
        logger.debug("config: %s" % pprint.pprint(self.config))
        self.config.save()

    def test_autobuild_build_default(self):
        self.autobuild('build', '--no-configure', '--config-file=' + self.tmp_file, '--id=123456')
        self.autobuild('build', '--config-file=' + self.tmp_file, '--id=123456', '--', '--foo', '-b')

    def test_autobuild_build_all(self):
        self.autobuild('build', '--config-file=' + self.tmp_file, '--id=123456', '-a')

    def test_autobuild_build_release(self):
        self.autobuild('build', '--config-file=' + self.tmp_file, '-c', 'Release', '--id=123456')

    def tearDown(self):
        self.cleanup_tmp_file()
        if self.tmp_build_dir:
            basetest.clean_dir(self.tmp_build_dir)
        basetest.BaseTest.tearDown(self)

class TestEnvironment(basetest.BaseTest, AutobuildBaselineCompare):
    def setUp(self):
        basetest.BaseTest.setUp(self)
        os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.abspath(os.path.dirname(__file__))])
        self.tmp_file = self.get_tmp_file(0)
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        package = configfile.PackageDescription('test')
        platform = configfile.PlatformDescription()
        self.tmp_build_dir=tempfile.mkdtemp(prefix=os.path.dirname(self.tmp_file)+"/build-")
        platform.build_directory = self.tmp_build_dir
        build_configuration = configfile.BuildConfigurationDescription()
        build_configuration.build = Executable(command="envtest.py")
        build_configuration.default = True
        build_configuration.name = 'Release'
        platform.configurations['Release'] = build_configuration
        package.platforms[common.get_current_platform()] = platform
        self.config.package_description = package
        self.config.save()

    def test_env(self):
        # verify that the AUTOBUILD env var is set to point to something executable
        self.autobuild('build', '--no-configure', '--config-file=' + self.tmp_file, '--id=123456')

    def tearDown(self):
        self.cleanup_tmp_file()
        if self.tmp_build_dir:
            basetest.clean_dir(self.tmp_build_dir)
        basetest.BaseTest.tearDown(self)

if __name__ == '__main__':
    unittest.main()
