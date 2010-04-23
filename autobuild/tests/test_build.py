#!/usr/bin/env python

import unittest
import subprocess
#from autobuild import build

class TestBuild(unittest.TestCase):
    def setUp(self):
        self.orig_call = subprocess.call
        subprocess.call = self.mock_call
        pass

    def test_0(self):
        class Options(object):
            build_command = 'build.sh'
        #build.main(Options(), [])
        pass

    def mock_call(self, *args):
        "monkey patched version of subprocess.call for unit testing"
        print "MONKEY %r" % args
        pass

    def tearDown(self):
        subprocess.call = self.orig_call

if __name__ == '__main__':
    unittest.main()

