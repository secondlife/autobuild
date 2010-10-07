#!/usr/bin/env python
#
# Unit testing of manifest subcommand.
#


import os
import subprocess
import sys
import unittest

from autobuild import configfile
from autobuild import common
from autobuild.autobuild_main import Autobuild
from baseline_compare import AutobuildBaselineCompare
import autobuild.autobuild_tool_manifest as manifest


class TestManifest(unittest.TestCase, AutobuildBaselineCompare):
    def setUp(self):
        os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.abspath(os.path.dirname(__file__))])
        self.tmp_file = self.get_tmp_file(4)
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        package = configfile.PackageDescription('test')
        working_platform = configfile.PlatformDescription()
        common_platform = configfile.PlatformDescription()
        package.platforms[common.get_current_platform()] = working_platform
        package.platforms['common'] = common_platform
        self.config.package_description = package

    def test_add(self):
        manifest.add(self.config, 'common', '*.cpp')
        manifest.add(self.config, 'common', '*.h')
        manifest.add(self.config, 'common', '*.py')
        common_manifest = self.config.get_platform('common').manifest
        assert ('*.cpp' in common_manifest) and ('*.h' in common_manifest) and ('*.py' in common_manifest)
        assert len(common_manifest) == 3
   
    def test_remove(self):
        manifest.add(self.config, 'common', '*.cpp')
        manifest.add(self.config, 'common', '*.h')
        manifest.add(self.config, 'common', '*.py')
        manifest.remove(self.config, 'common', '*.cpp')
        common_manifest = self.config.get_platform('common').manifest
        assert (not '*.cpp' in common_manifest) 
        assert ('*.h' in common_manifest) and ('*.py' in common_manifest)
        assert len(common_manifest) == 2
   
    def test_clear(self):
        manifest.add(self.config, 'common', '*.cpp')
        manifest.add(self.config, 'common', '*.h')
        manifest.add(self.config, 'common', '*.py')
        manifest.clear(self.config, 'common')
        common_manifest = self.config.get_platform('common').manifest
        assert not common_manifest

    def test_autobuild_manifest(self):
        self.config.save()
        print self.config.get_platform('common')
        result = subprocess.call("autobuild manifest --config-file=%s -p common add *.cpp *.h '*.py'" % \
            self.tmp_file, shell=True)
        assert result == 0
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        common_manifest = self.config.get_platform('common').manifest
        print self.config.get_platform('common')
        assert ('*.cpp' in common_manifest) and ('*.h' in common_manifest) and ('*.py' in common_manifest)
        result = subprocess.call('autobuild manifest --config-file=%s -p common remove *.cpp' % \
            self.tmp_file, shell=True)
        assert result == 0
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        common_manifest = self.config.get_platform('common').manifest
        assert (not '*.cpp' in common_manifest) 
        assert ('*.h' in common_manifest) and ('*.py' in common_manifest)
        
    def tearDown(self):
        pass


if __name__ == '__main__':
    unittest.main()
