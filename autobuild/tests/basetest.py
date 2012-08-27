#!/usr/bin/python
"""\
@file   basetest.py
@author Nat Goodspeed
@date   2012-08-24
@brief  Define BaseTest, a base class for all individual test classes.

$LicenseInfo:firstyear=2012&license=internal$
Copyright (c) 2012, Linden Research, Inc.
$/LicenseInfo$
"""

import os
import sys
import errno
import subprocess
import time
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
