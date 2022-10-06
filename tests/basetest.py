from __future__ import annotations

import errno
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import contextmanager, redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path

import pytest

from autobuild import common
from autobuild.common import cmd, has_cmd


@contextmanager
def temp_dir():
    """
    A PermissionError can be thrown on windows when cleaning up temporary directories.
    This was addressed in python 3.10 with TemporaryDirectory(ignore_cleanup_errors=True) but
    until 3.10 is used everywhere we need this hack.
    """
    try:
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp
    except PermissionError:
        pass


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.this_dir = os.path.abspath(os.path.dirname(__file__))
        self.autobuild_bin = str(Path(__file__).parent / "bin" / "autobuild")

        if os.name == "nt":
            self.autobuild_bin += ".cmd"

    def autobuild(self, *args, **kwds):
        """
        All positional args are collected as string arguments to the
        self.autobuild_bin command. If you want to pass additional arguments
        to subprocess.call(), pass them as keyword arguments; those are passed
        through.
        """
        command = (self.autobuild_bin,) + args
        return subprocess.check_output(command, universal_newlines=True, **kwds).rstrip()

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
                except OSError as err:
                    if err.errno == errno.ENOENT:
                        return
                    if err.errno != errno.EACCES:
                        print("*** Unknown %s (errno %s): %s: %s" % \
                              (err.__class__.__name__, err.errno, err, path))
                        sys.stdout.flush()
                        raise
                    if (time.time() - start) > 10:
                        print("*** remove(%r) timed out after %s retries" % (path, tries))
                        sys.stdout.flush()
                        raise
                    time.sleep(1)

    def tearDown(self):
        pass

def clean_file(pathname):
    try:
        os.remove(pathname)
    except OSError as err:
        if err.errno != errno.ENOENT:
            print("*** Can't remove %s: %s" % (pathname, err), file=sys.stderr)
            # But no exception, we're still trying to clean up.

def clean_dir(pathname):
    try:
        shutil.rmtree(pathname)
    except OSError as err:
        # Nonexistence is fine.
        if err.errno != errno.ENOENT:
            print("*** Can't remove %s: %s" % (pathname, err), file=sys.stderr)

def assert_in(item, container):
    assert item in container, "%r not in %r" % (item, container)

def assert_not_in(item, container):
    assert item not in container, "%r should not be in %r" % (item, container)

def assert_found_in(regex, container):
    pattern = re.compile(regex)
    assert any(pattern.search(item) for item in container), "search failed for %r in %r" % (regex, container)

def assert_not_found_in(regex, container):
    pattern = re.compile(regex)
    assert not any(pattern.search(item) for item in container), "search found %r in %r" % (regex, container)


@contextmanager
def exc(exceptionslist, pattern=None, without=None, message=None):
    """
    Usage:

    # succeeds
    with exc(ValueError):
        int('abc')

    # fails with AssertionError
    with exc(ValueError):
        int('123')

    # can specify multiple expected exceptions
    with exc((IndexError, ValueError)):
        int(''[0])
    with exc((IndexError, ValueError)):
        int('a'[0])

    # can match expected message, when exception type isn't sufficient
    with exc(Exception, 'badness'):
        raise Exception('much badness has occurred')

    # or can verify that exception message does NOT contain certain text
    with exc(Exception, without='string'):
        raise Exception('much int badness has occurred')
    """
    try:
        # run the body of the with block
        yield
    except exceptionslist as err:
        # okay, with block did raise one of the expected exceptions;
        # did the caller need the exception message to match a pattern?
        if pattern:
            if not re.search(pattern, str(err)):
                raise AssertionError("exception %s does not match '%s': '%s'" %
                                     (err.__class__.__name__, pattern, err))
        # or not to match a pattern?
        if without:
            if re.search(without, str(err)):
                raise AssertionError("exception %s should not match '%s': '%s'" %
                                     (err.__class__.__name__, without, err))
    else:
        # with block did not raise any of the expected exceptions: FAIL
        try:
            # did caller pass a tuple of exceptions?
            iter(exceptionslist)
        except TypeError:
            # just one exception class: use its name
            exceptionnames = exceptionslist.__name__
        else:
            # tuple of exception classes: format their names
            exceptionnames = "any of (%s)" % \
                ','.join(ex.__name__ for ex in exceptionslist)
        raise AssertionError(message or
                             ("with block did not raise " + exceptionnames))

def ExpectError(errfrag, expectation, exception=common.AutobuildError):
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
    return exc(exception, pattern=errfrag, message=expectation)


@contextmanager
def capture_stdout_buffer():
    """
    Capture sys.stdout.buffer
    """
    _ = StringIO() # Not needed for any tests yet
    buf = BytesIO()
    with redirect_stdout(_):
        sys.stdout.buffer = buf
        yield buf


class CaptureStd(object):
    """
    Usage:

    with CaptureStd("stdout") as stream:
        print "something"
        print "something else"
    assert stream.getvalue() == "something\n" "something else\n"
    print "This will display on console, as before."

    Note that this does NOT capture output emitted by a child process -- only
    data written to sys.stdout.
    """
    def __init__(self, attr):
        self.attr = attr

    def __enter__(self):
        self.save = getattr(sys, self.attr)
        stream = StringIO()
        setattr(sys, self.attr, stream)
        return stream

    def __exit__(self, *exc_info):
        setattr(sys, self.attr, self.save)

class CaptureStdout(CaptureStd):
    def __init__(self):
        super(CaptureStdout, self).__init__("stdout")

class CaptureStderr(CaptureStd):
    def __init__(self):
        super(CaptureStderr, self).__init__("stderr")


@contextmanager
def chdir(dir: str):
    owd = os.getcwd()
    os.chdir(dir)
    try:
        yield
    finally:
        os.chdir(owd)


@contextmanager
def envvar(key: str, val: str | None):
    """Temporarily set or unset an environment variable"""
    old_val = os.environ.get(key)
    if val is None:
        if old_val:
            del os.environ[key]
    else:
        os.environ[key] = val
        print(f"set {key}={val}")
    yield
    if old_val is None:
        if val:
            del os.environ[key]
    else:
        os.environ[key] = old_val


@contextmanager
def git_repo():
    """
    Initialize a new git repository in a temporary directory, yield its path, clean after context exit.

    Layout:
        .
        ├── dir
        │   └── file
        ├── file
        ├── .gitignore
        └── stage
    """
    owd = os.getcwd()
    with temp_dir() as root:
        try:
            os.chdir(root)
            with open(os.path.join(root, "file"), "w"):
                pass
            os.mkdir(os.path.join(root, "dir"))
            with open(os.path.join(root, "dir", "file"), "w"):
                pass
            os.mkdir(os.path.join(root, "stage"))
            with open(os.path.join(root, ".gitignore"), "w") as f:
                f.write("stage")
            cmd("git", "init")
            cmd("git", "remote", "add", "origin", "https://example.com/foo.git")
            cmd("git", "add", "-A")
            cmd("git", "commit", "-m", "Initial")
            cmd("git", "tag", "v1.0.0")
            yield root
        finally:
            # Make sure to chdir out of temp_dir before closing it, otherwise windows
            # will freak out. https://github.com/python/cpython/issues/86962
            os.chdir(owd)


needs_git = pytest.mark.skipif(not has_cmd("git"), reason="git not present on system")
needs_nix = pytest.mark.skipif(not has_cmd("which", "bash"), reason="needs unix-like environment")
needs_cygwin = pytest.mark.skipif(not has_cmd("cygpath", "-h"), reason="needs windows environment")
