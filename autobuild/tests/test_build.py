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

class LocalBase(basetest.BaseTest, AutobuildBaselineCompare):
    def setUp(self):
        basetest.BaseTest.setUp(self)
        # We intend to ask our child autobuild command to run a script located
        # in this directory. Make sure this directory is on child autobuild's
        # PATH so we find it.
        os.environ["PATH"] = os.pathsep.join([os.path.abspath(os.path.dirname(__file__)),
                                              os.environ["PATH"]])
        # Create and return a config file appropriate for this test class.
        self.tmp_file = self.get_tmp_file(0)
        self.tmp_build_dir=tempfile.mkdtemp(prefix=os.path.dirname(self.tmp_file)+"/build-")
        self.config = self.get_config()
        self.config.save()

    def get_config(self):
        config = configfile.ConfigurationDescription(self.tmp_file)
        package = configfile.PackageDescription('test')
        package.license = "LGPL"
        package.license_file="LICENSES/file"
        package.copyright="copy right"
        platform = configfile.PlatformDescription()
        platform.build_directory = self.tmp_build_dir
        build_configuration = configfile.BuildConfigurationDescription()
        build_configuration.build = Executable(command="noop.py")
        build_configuration.default = True
        build_configuration.name = 'Release'
        platform.configurations['Release'] = build_configuration
        package.platforms[common.get_current_platform()] = platform
        config.package_description = package
        return config

    def tearDown(self):
        self.cleanup_tmp_file()
        if self.tmp_build_dir:
            basetest.clean_dir(self.tmp_build_dir)
        basetest.BaseTest.tearDown(self)

class TestBuild(LocalBase):
    def get_config(self):
        config = super(TestBuild, self).get_config()
        config.package_description.version = "0"
        logger.debug("config: %s" % pprint.pformat(config))
        return config

    def test_autobuild_build_default(self):
        self.autobuild('build', '--no-configure', '--config-file=' + self.tmp_file, '--id=123456')
        self.autobuild('build', '--config-file=' + self.tmp_file, '--id=123456', '--', '--foo', '-b')

    def test_autobuild_build_all(self):
        self.autobuild('build', '--config-file=' + self.tmp_file, '--id=123456', '-a')

    def test_autobuild_build_release(self):
        self.autobuild('build', '--config-file=' + self.tmp_file, '-c', 'Release', '--id=123456')

class TestEnvironment(LocalBase):
    def get_config(self):
        config = super(TestEnvironment, self).get_config()
        config.package_description.copyright="no copy"
        config.package_description.platforms[common.get_current_platform()] \
              .configurations["Release"].build = Executable(command="envtest.py")
        return config

    def test_env(self):
        # verify that the AUTOBUILD env var is set to point to something executable
        self.autobuild('build', '--no-configure', '--config-file=' + self.tmp_file, '--id=123456')

if __name__ == '__main__':
    unittest.main()
