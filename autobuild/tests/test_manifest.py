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
# Unit testing of manifest subcommand.
#


import os
import sys
import unittest

from autobuild import configfile
from autobuild import common
from autobuild.autobuild_main import Autobuild
from baseline_compare import AutobuildBaselineCompare
import autobuild.autobuild_tool_manifest as manifest
from basetest import BaseTest


class TestManifest(BaseTest, AutobuildBaselineCompare):
    def setUp(self):
        BaseTest.setUp(self)
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
        self.autobuild("manifest", "--config-file=" + self.tmp_file,
                       "-p", "common", "add", "*.cpp", "*.h", "*.py")
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        common_manifest = self.config.get_platform('common').manifest
        assert ('*.cpp' in common_manifest) and ('*.h' in common_manifest) and ('*.py' in common_manifest)
        self.autobuild('manifest', '--config-file=' + self.tmp_file,
                       '-p', 'common', 'remove', '*.cpp')
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        common_manifest = self.config.get_platform('common').manifest
        assert (not '*.cpp' in common_manifest) 
        assert ('*.h' in common_manifest) and ('*.py' in common_manifest)
        
    def tearDown(self):
        self.cleanup_tmp_file()
        BaseTest.tearDown(self)


if __name__ == '__main__':
    unittest.main()
