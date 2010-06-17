#!/usr/bin/env python

import unittest
import subprocess
from autobuild import autobuild_tool_build

class TestBuild(unittest.TestCase):
    def setUp(self):
        self.orig_call = subprocess.call
        subprocess.call = self.mock_call
        class FakeOptions(object):
            build_command = 'build.sh'
        self.options = FakeOptions()

    def test_0(self):
        autobuild_tool_build.do_build("sh", "./build.sh")

    def mock_call(self, *args, **kwargs):
        "monkey patched version of subprocess.call for unit testing"
        print "MONKEY %r" % ((args, kwargs),)

    def tearDown(self):
        subprocess.call = self.orig_call

if __name__ == '__main__':
    unittest.main()

