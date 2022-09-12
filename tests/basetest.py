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

from autobuild import common
from autobuild.util import cmd

autobuild_dir = Path(__file__).resolve().parent.parent.parent

# Small script used by tests such as test_source_environment's where
# autobuild needs to be called from an external script.
AUTOBUILD_BIN_SCRIPT = """#!/usr/bin/env python
from autobuild import autobuild_main

if __name__ == "__main__":
    autobuild_main.main()
"""

@contextmanager
def tmp_autobuild_bin():
    """
    Create a temporary directory with an autobuild shim script pointing to the
    autobuild_main in this package. Yields the path to the autobuild script.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        autobuild_bin = str(Path(tmp_dir) / "autobuild")

        # Write AUTOBUILD_BIN_SCRIPT contents into temporary directory
        with open(autobuild_bin, "w") as f:
            f.write(AUTOBUILD_BIN_SCRIPT)

        # Make script executable
        os.chmod(autobuild_bin, 0o775)

        # Insert both the temporary bin directory containing autobuild and local autobuild
        # python module location into the system path.
        sys.path.insert(0, autobuild_dir)
        sys.path.insert(0, tmp_dir)
        try:
            yield autobuild_bin
        finally:
            # Cleanup path
            sys.path.remove(tmp_dir)
            sys.path.remove(autobuild_dir)


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.this_dir = os.path.abspath(os.path.dirname(__file__))

    def run(self, result=None):
        with tmp_autobuild_bin() as autobuild_bin:
            self.autobuild_bin = autobuild_bin
            super(BaseTest, self).run(result)

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
    try:
        with tempfile.TemporaryDirectory() as root:
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
            cmd("git", "add", "-A")
            cmd("git", "commit", "-m", "Initial")
            cmd("git", "tag", "v1.0.0")
            yield root 
    finally:
        os.chdir(owd)
