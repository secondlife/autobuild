#!/usr/bin/env python

import unittest
from autobuild import package
import StringIO

try:
    import hashlib
except ImportError:
    # for older (pre-2.5) versions of python...
    class __HashlibAdapter(object):
        import md5 as oldmd5
        md5 = oldmd5.new
    hashlib = __HashlibAdapter()

class TestPackager(unittest.TestCase):
    def setUp(self):
        pass

    def test_0(self):
        pass

class TestInstallAdapter(unittest.TestCase):
    def setUp(self):
        self.installer = package.Installer()

    def test_getMd5Sum(self):
        test_tarfile = StringIO.StringIO("foobar");
        self.assertEquals(self.installer.getMd5Sum(test_tarfile),
                          hashlib.md5("foobar").hexdigest())
        

if __name__ == '__main__':
    unittest.main()

