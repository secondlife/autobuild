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
from cStringIO import StringIO

from autobuild import common

class BaseTest(unittest.TestCase):
    def setUp(self):
        self.this_dir = os.path.abspath(os.path.dirname(__file__))
        # Unfortunately, when we run tests, sys.argv[0] is (e.g.) "nosetests"!
        # So we can't just call get_autobuild_executable_path(); in fact that
        # function is untestable. Derive a suitable autobuild command relative
        # to this module's location.
        self.autobuild_bin = os.path.abspath(os.path.join(self.this_dir, os.pardir, os.pardir,
                                                          "bin", "autobuild"))

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

def assert_in(item, container):
    assert item in container, "%r not in %r" % (item, container)

def assert_not_in(item, container):
    assert item not in container, "%r should not be in %r" % (item, container)
            
class ExpectError(object):
    """
    Usage:

    with ExpectError("text that should be in the exception", "Expected a bad thing to happen"):
        something(that, should, raise)

    replaces:

    try:
        self.options.package = ["no_such_package"]
        something(that, should, raise)
    except AutobuildError, err:
        assert_in("text that should be in the exception", str(err))
    else:
        assert False, "Expected a bad thing to happen"
    """
    def __init__(self, errfrag, expectation, exception=common.AutobuildError):
        self.errfrag = errfrag
        self.expectation = expectation
        self.exception = exception

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        # We expect an exception. If we get here without one, it's a problem.
        if not any((type, value, tb)):
            assert False, self.expectation
        # Okay, it's an exception; is it the type we want?
        if not isinstance(value, self.exception):
            return False                # let exception propagate
        # We reached here with an exception of the right type. Does it contain
        # the message fragment we're expecting?
        assert_in(self.errfrag, str(value))
        # If all the above is true, then swallow the exception and proceed.
        return True

class CaptureStdout(object):
    """
    Usage:

    with CaptureStdout() as stream:
        print "something"
        print "something else"
    assert stream.getvalue() == "something\n" "something else\n"
    print "This will display on console, as before."

    Note that this does NOT capture output emitted by a child process -- only
    data written to sys.stdout.
    """
    def __enter__(self):
        self.stdout = sys.stdout
        sys.stdout = StringIO()
        return sys.stdout

    def __exit__(self, *exc_info):
        sys.stdout = self.stdout

