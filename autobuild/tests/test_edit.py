#!/usr/bin/env python
#
# Unit testing of edit subcommand.
#


import os
import subprocess
import sys
import unittest

from autobuild import configfile
from autobuild import common
from autobuild.autobuild_main import Autobuild
from baseline_compare import AutobuildBaselineCompare
from autobuild.autobuild_tool_edit import AutobuildTool


class TestEdit(unittest.TestCase, AutobuildBaselineCompare):
    def setUp(self):
        os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.abspath(os.path.dirname(__file__))])
        self.tmp_file = self.get_tmp_file(4)
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        self.autobuild_tool = AutobuildTool()

    def _test_build(self):
        expected_config = {'package_description': {'platforms': {'windows': {'configurations': {'newbuild': {'build': {'command': 'make this'}}}}}},
                            'type': 'autobuild',
                            'version': '1.2'}
        args = ['build', 'name=newbuild', 'platform=windows', 'cmd="make this"']
        self.autobuild_tool.main(args)
        fh = open(self.tmp_file)
        built_config = fh.read()
        cmp_config = dict(built_config)
        assert (expected_config == built_config)
           
    def tearDown(self):
        self.cleanup_tmp_file()


if __name__ == '__main__':
    unittest.main()
