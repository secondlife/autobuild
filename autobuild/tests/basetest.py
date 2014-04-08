#!/usr/bin/python
"""\
@file   basetest.py
@author Nat Goodspeed
@date   2012-08-24
@brief  Define BaseTest, a base class for all individual test classes.
"""
# $LicenseInfo:firstyear=2012&license=mit$
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

import os
import sys
import errno
import subprocess
import time
import shutil
import unittest

class BaseTest(unittest.TestCase):
    def setUp(self):
        self.this_dir = os.path.abspath(os.path.dirname(__file__))
        self.autobuild_bin = os.path.abspath(os.path.join(self.this_dir, os.pardir, os.pardir,
                                                          "bin", "autobuild"))
        if sys.platform.startswith("win"):
            self.autobuild_bin += ".cmd"

    def autobuild(self, *args, **kwds):
        """
        All positional args are collected as string arguments to the
        self.autobuild_bin command. If you want to pass additional arguments
        to subprocess.call(), pass them as keyword arguments; those are passed
        through.
        """
        command = (self.autobuild_bin,) + args
        rc = subprocess.call(command, **kwds)
        assert rc == 0, "%s => %s" % (' '.join(command), rc)

    # On Windows, need some retry logic wrapped around removing files (SIGHH)
    if not sys.platform.startswith("win"):
        remove = os.remove
    else:
        def remove(self, path):
            start = time.time()
            tries = 0
            while True:
                tries += 1
                try:
                    os.remove(path)
                except OSError, err:
                    if err.errno == errno.ENOENT:
                        return
                    if err.errno != errno.EACCES:
                        print "*** Unknown %s (errno %s): %s: %s" % \
                              (err.__class__.__name__, err.errno, err, path)
                        sys.stdout.flush()
                        raise
                    if (time.time() - start) > 10:
                        print "*** remove(%r) timed out after %s retries" % (path, tries)
                        sys.stdout.flush()
                        raise
                    time.sleep(1)

    def tearDown(self):
        pass

def clean_file(pathname):
    try:
        os.remove(pathname)
    except OSError, err:
        if err.errno != errno.ENOENT:
            print >>sys.stderr, "*** Can't remove %s: %s" % (pathname, err)
            # But no exception, we're still trying to clean up.

def clean_dir(pathname):
    try:
        shutil.rmtree(pathname)
    except OSError, err:
        # Nonexistence is fine.
        if err.errno != errno.ENOENT:
            print >>sys.stderr, "*** Can't remove %s: %s" % (pathname, err)

