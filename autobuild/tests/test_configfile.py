#!/usr/bin/env python
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

