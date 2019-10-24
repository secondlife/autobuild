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
# Unit testing of edit subcommand.
#

from __future__ import absolute_import

import os
import subprocess
import sys
import unittest

try:
    from llbase import llsd
except:
    sys.exit("Failed to import llsd via the llbase module; to install, use:\n"
             +"  pip install llbase")

from autobuild import configfile
from autobuild import common
from autobuild.autobuild_main import Autobuild
from .baseline_compare import AutobuildBaselineCompare
from autobuild.autobuild_tool_edit import AutobuildTool
from .basetest import BaseTest
from nose.tools import *                # assert_equals() et al.


class TestEdit(BaseTest, AutobuildBaselineCompare):
    def setUp(self):
        BaseTest.setUp(self)
        os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.abspath(os.path.dirname(__file__))])
        self.tmp_file = self.get_tmp_file(4)
        self.edit_cmd = AutobuildTool()

    def _try_cmd(self, args):
        """
        Try running an edit 'command with args'.
        Return results.
        """
        self.edit_cmd.main(args)
        return llsd.parse(open(self.tmp_file, 'rb').read())

    def test_build(self):
        """
        Perform non-interactive configuration of build command.
        Check results.
        """
        args = ['build', "--config-file=%s" % self.tmp_file, 'name=newbuild', 'platform=windows', 'command=makethis']
        expected_config = {'package_description': {'platforms': {'windows': {'name': 'windows', 'configurations': {'newbuild': {'build': {'command': 'makethis'}, 'name': 'newbuild'}}}}}, 'version': configfile.AUTOBUILD_CONFIG_VERSION, 'type': 'autobuild'}
        built_config = self._try_cmd(args)
        assert_equals(expected_config, built_config)
           
    def test_configure(self):
        """
        Perform non-interactive configuration of configure command.
        Check results.
        """
        args = ['configure', "--config-file=%s" % self.tmp_file, 'name=newbuild', 'platform=windows', 'command=makethat']
        expected_config = {'package_description': {'platforms': {'windows': {'name': 'windows', 'configurations': {'newbuild': {'configure': {'command': 'makethat'}, 'name': 'newbuild'}}}}}, 'version': configfile.AUTOBUILD_CONFIG_VERSION, 'type': 'autobuild'}
        built_config = self._try_cmd(args)
        assert_equals(expected_config, built_config)

    def test_build_configure(self):
        """
        Perform two updates to the config file in series. 
        Check results after each iteration.
        """
        args = ['configure', "--config-file=%s" % self.tmp_file, 'name=newbuild', 'platform=windows', 'command=makethat']
        built_config1 = self._try_cmd(args)
        expected_config1 = {'package_description': {'platforms': {'windows': {'name': 'windows', 'configurations': {'newbuild': {'configure': {'command': 'makethat'}, 'name': 'newbuild'}}}}}, 'version': configfile.AUTOBUILD_CONFIG_VERSION, 'type': 'autobuild'}
        assert_equals(expected_config1, built_config1)
        args = ['build', "--config-file=%s" % self.tmp_file, 'name=newbuild', 'platform=windows', 'command=makethis']
        built_config2 = self._try_cmd(args)
        expected_config2 = {'package_description': {'platforms': {'windows': {'name': 'windows', 'configurations': {'newbuild': {'build': {'command': 'makethis'}, 'name': 'newbuild', 'configure': {'command': 'makethat'}}}}}}, 'version': configfile.AUTOBUILD_CONFIG_VERSION, 'type': 'autobuild'}
        assert_equals(expected_config2, built_config2)
        
    def test_platform_configure(self):
        args = ['platform', "--config-file=%s" % self.tmp_file, 'name=windows', 'build_directory=foo/bar/baz']
        built_config = self._try_cmd(args)
        assert_equals(built_config['package_description']['platforms']['windows']['build_directory'], 'foo/bar/baz')

    def test_platform_configure_ios(self):
        args = ['platform', "--config-file=%s" % self.tmp_file, 'name=common', 'build_directory=foo/bar/baz']
        built_config = self._try_cmd(args)
        args = ['platform', "--config-file=%s" % self.tmp_file, 'name=darwin_ios', 'build_directory=foo/bar/baz_ios']
        built_config = self._try_cmd(args)
        assert_equals(built_config['package_description']['platforms']['common']['build_directory'], 'foo/bar/baz')
        assert_equals(built_config['package_description']['platforms']['darwin_ios']['build_directory'], 'foo/bar/baz_ios')

    def tearDown(self):
        self.cleanup_tmp_file()
        BaseTest.tearDown(self)


class TestEditCmdLine(BaseTest, AutobuildBaselineCompare):
    def setUp(self):
        BaseTest.setUp(self)
        os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.abspath(os.path.dirname(__file__))])
        self.tmp_file = self.get_tmp_file(0)

    def test_autobuild_edit(self):
        self.autobuild('edit', '--config-file=' + self.tmp_file, '--help')
        self.autobuild('edit', 'build', '--config-file=' + self.tmp_file,
                       'name=foo', 'command=buildme.py')

    def tearDown(self):
        self.cleanup_tmp_file()
        BaseTest.tearDown(self)


if __name__ == '__main__':
    unittest.main()
