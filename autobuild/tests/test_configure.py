#!/usr/bin/env python

import unittest
from autobuild import configure
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

