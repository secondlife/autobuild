#!/usr/bin/env python
#
# Unit testing of manifest subcommand.
#


import os
import sys
import unittest

from autobuild import configfile
from autobuild.autobuild_main import Autobuild
from baseline_compare import AutobuildBaselineCompare


class TestManifest(unittest.TestCase, AutobuildBaselineCompare):
    def setUp(self):
        pass

    def test_0(self):
        tmp_file = self.get_tmp_file(0)
        config = configfile.ConfigFile()
        config.save(tmp_file)
        argstr = "manifest --file=%s --platform=darwin *.dylib" % tmp_file
        Autobuild().main(argstr.split())
        self.diff_tmp_file_against_baseline("data/manifest_test_0.xml")
        
    def tearDown(self):
        self.cleanup_tmp_file()


if __name__ == '__main__':
    unittest.main()
