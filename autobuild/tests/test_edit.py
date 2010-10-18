#!/usr/bin/env python
#
# Unit testing of edit subcommand.
#


import os
import subprocess
import sys
import unittest

from llbase import llsd
from autobuild import configfile
from autobuild import common
from autobuild.autobuild_main import Autobuild
from baseline_compare import AutobuildBaselineCompare
from autobuild.autobuild_tool_edit import AutobuildToolEdit


class TestEdit(unittest.TestCase, AutobuildBaselineCompare):
    def setUp(self):
        os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.abspath(os.path.dirname(__file__))])
        self.tmp_file = self.get_tmp_file(4)
        self.edit_cmd = AutobuildToolEdit()

    def test_build(self):
        expected_config = {'package_description': {'platforms': {'windows': {'configurations': {'newbuild': {'build': {'command': 'make this', 'arguments': [], 'options': []}}}}}}, 'version': '1.2', 'type': 'autobuild'}
        args = ['build', 'name=newbuild', 'platform=windows', 'cmd=make this', "--config-file=%s" % self.tmp_file]
        self.edit_cmd.main(args)
        built_config = llsd.parse(file(self.tmp_file, 'rb').read())
        assert (expected_config == built_config)
           
    def tearDown(self):
        self.cleanup_tmp_file()


if __name__ == '__main__':
    unittest.main()
