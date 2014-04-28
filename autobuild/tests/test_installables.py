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

from autobuild import configfile
from autobuild import common
from autobuild.autobuild_main import Autobuild
from baseline_compare import AutobuildBaselineCompare
import autobuild.autobuild_tool_installables as installables
from basetest import BaseTest, assert_in


class TestInstallables(BaseTest, AutobuildBaselineCompare):
    def setUp(self):
        BaseTest.setUp(self)
        os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.abspath(os.path.dirname(__file__))])
        self.tmp_file = self.get_tmp_file(0)
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        self.datadir = os.path.join(os.path.dirname(__file__), "data")
        
    def test_add_edit_remove(self):
        local_archive=os.path.join(self.datadir,'bogus-0.1-common-111.tar.bz2')
        data = ('license=tut', 'license_file=LICENSES/bogus.txt', 'platform=darwin',
            'url='+local_archive)
        installables.add(self.config, 'bogus', None, data)
        self.assertEquals(len(self.config.installables), 1)
        package_description = self.config.installables['bogus']
        self.assertEquals(package_description.name, 'bogus')
        self.assertEquals(package_description.license, 'tut')
        assert_in('darwin', package_description.platforms)
        platform_description = package_description.platforms['darwin']
        assert platform_description.archive is not None
        assert platform_description.archive.url.endswith(local_archive)
        edit_data = ('license=Apache', 'platform=darwin', 'hash_algorithm=sha-1')
        installables.edit(self.config, 'bogus', None, edit_data)
        self.assertEquals(package_description.license, 'Apache')
        self.assertEquals(platform_description.archive.hash_algorithm, 'sha-1')
        installables.remove(self.config, 'bogus')
        self.assertEquals(len(self.config.installables), 0)
                    
    def tearDown(self):
        self.cleanup_tmp_file()
        BaseTest.tearDown(self)
