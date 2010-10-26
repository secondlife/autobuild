#!/usr/bin/env python
#
# Integration test to exercise archive installation
#

import os
import sys
import errno
import shutil
import socket
import logging
import tarfile
import tempfile
import unittest
import urllib
import urlparse
import posixpath
import subprocess
from threading import Thread
from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
from autobuild import autobuild_tool_install, autobuild_tool_uninstall, configfile, common

mydir = os.path.dirname(__file__)
HOST = '127.0.0.1'                      # localhost server
PORT = 8800                             # base port, may change
BASE_DIR = None                         # put all test temp files here for easy cleanup
STAGING_DIR = None                      # create archives/repos here, copy as needed
SERVER_DIR = None                       # populate this directory with files to "download"
INSTALL_DIR = None                      # where to find installed files
# If we could configure the autobuild download cache, we'd put it under
# BASE_DIR and let it be cleaned up generically. Since we can't, the cache is
# a resource we must share with production usage. When done, clean up extra
# files, restoring its original state.
INIT_CACHE = None

# We create archives in STAGING_DIR. Create a corresponding PackageDescription
# for each to keep the contents associated with the metadata. FIXTURES is a
# dict mapping an arbitrary string key to a BaseFixture object.
FIXTURES = {}

FakeOptions = None                      # placeholder for class defined in setup()

logger = logging.getLogger("autobuild.test_install")

# ****************************************************************************
#   utilities
# ****************************************************************************
def url_for(tail):
    return "http://%s:%s/%s" % (HOST, PORT, tail)

def in_dir(dir, file):
    return os.path.join(dir, os.path.basename(file))

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

def assert_equals(left, right):
    assert left == right, "%r != %r" % (left, right)

def assert_in(item, container):
    assert item in container, "%r not in %r" % (item, container)

def assert_not_in(item, container):
    assert item not in container, "%r should not be in %r" % (item, container)

# ****************************************************************************
#   module setup() and teardown()
# ****************************************************************************
def setup():
    """
    Module-level setup
    """
    global BASE_DIR, STAGING_DIR, SERVER_DIR, INSTALL_DIR, INIT_CACHE
    BASE_DIR = tempfile.mkdtemp()
    STAGING_DIR = os.path.join(BASE_DIR, "data")
    os.mkdir(STAGING_DIR)
    SERVER_DIR = os.path.join(BASE_DIR, "server")
    os.mkdir(SERVER_DIR)
    INSTALL_DIR = os.path.join(BASE_DIR, "packages")
    # We expect autobuild_tool_install to create INSTALL_DIR.

    # Capture initial state of the autobuild download cache. Use a set so we
    # can take set difference with subsequent snapshot.
    INIT_CACHE = set(os.listdir(common.get_default_install_cache_dir()))

    # For the duration of this script, run a server thread from which to
    # direct autobuild to "download" test archives. Various tests will
    # populate SERVER_DIR with files whose URLs they will then request. But
    # first, claim a localhost port on which to run this temp server -- it
    # would be a shame to bomb the test because something else (e.g. another
    # test instance) was already using the port.
    global PORT
    max_port = PORT + 4
    while True:
        try:
            httpd = HTTPServer((HOST, PORT), DownloadServer)
            # if that worked, break loop!
            break
        except socket.error, err:
            # Anything other than 'Address already in use', propagate
            if err.args[0] != 48:       # symbolic name somewhere??
                raise
            # Have we already tried as many ports as we intend?
            if PORT >= max_port:
                raise
            # 'Address already in use': increment and retry
            PORT += 1
    # Here httpd is an HTTPServer instance waiting for a serve_forever() call.
    thread = MyHTTPServer(httpd, name="httpd")
    # Start server thread. Make it a daemon thread: we'll let it run
    # "forever," confident that the whole process will terminate when the main
    # thread (unittest) terminates.
    thread.setDaemon(True)
    thread.start()

    # define FakeOptions class here (but in global namespace) because it
    # depends on INSTALL_DIR.
    global FakeOptions
    class FakeOptions(object):
        """
        Creates a fake argparse options structure to simulate
        passing in a number of command line options. Override with a keyword
        argument any specific options item you want to set, e.g.:

        FakeOptions(as_source=["mypackage"])
        """
        def __init__(self,
                     install_filename=os.path.join(mydir, "data", "packages-install.xml"),
                     installed_filename=os.path.join(INSTALL_DIR, "packages-installed.xml"),
                     install_dir=INSTALL_DIR,
                     platform="darwin",
                     dry_run=False,
                     list_archives=False,
                     list_installed=False,
                     check_license=True,
                     list_licenses=False,
                     export_manifest=False,
                     as_source=[],
                     verbose=False,
                     ):
            # Take all constructor params and assign as object attributes.
            params = locals().copy()
            # We have a couple locals() that aren't supposed to set attributes.
            del params["self"]
            params.pop("params", None)  # may or may not be there yet?
            self.__dict__.update(params)
            # Remember attribute names for copy() implementation
            self._attrs = params.keys()

        def copy(self):
            # Get a (key, value) pair for each attribute defined in our
            # constructor param list. From those, construct a dict; then pass
            # that dict as keyword arguments to our own class's constructor to
            # make a new instance.
            return self.__class__(**dict((attr, getattr(self, attr)) for attr in self._attrs))

        def use_temp_config(self):
            """
            Read the default config file, but set it to a temp pathname so we
            can modify it and save the modifications without trashing the
            pre-existing config file. (Since autobuild reads its config from
            disk, have to actually write such variations to a temp file.) Set
            our install_filename to that temp file so that passing this
            FakeOptions object into autobuild_tool_install will select it.

            Return ConfigurationDescription for caller to modify and save().
            """
            config = configfile.ConfigurationDescription(self.install_filename)
            # Make a temp file to overwrite when caller calls config.save()
            fh, config.path = tempfile.mkstemp(dir=BASE_DIR, prefix="autobuild-", suffix=".xml",
                                               text=True)
            os.close(fh)                # peculiar tempfile.mkstemp() protocol
            # Now select this new config file for subsequent use.
            self.install_filename = config.path
            return config

    # Define some fixture data that would be awkward to store in the autobuild
    # repository (tarballs, other repositories). Give each item a FIXTURES key
    # to retrieve them easily.
    FIXTURES["bogus-0.1"] = ArchiveFixture("bogus-0.1-darwin-20101022.tar.bz2",
        dict(lib={"bogus.lib": "fake object library"},
             include={"bogus.h": "fake header file"},
             LICENSES={"bogus.txt": "fake license file"}),
        license="N/A")
    # ------------------------ verify ArchiveFixture -------------------------
    fixture = FIXTURES["bogus-0.1"]
    package = fixture.package
    assert package.name == "bogus"
    assert package.version == "0.1"
    assert package.platforms["darwin"].archive.hash_algorithm == "md5"
    assert package.platforms["darwin"].archive.url == url_for(os.path.basename(fixture.pathname))
    assert package.license_file == os.path.join("LICENSES", "bogus.txt")
    # -----------------------------------  -----------------------------------
    FIXTURES["bogus-0.2"] = ArchiveFixture("bogus-0.2-darwin-20101025.tar.bz2",
        dict(lib={"bogus.lib": "fake object library"},
             include={"bogus.h": "fake header file 0.2"}),
        license="N/A")
    # Note intentional omission: "bogus-0.2" tarball has no LICENSES file.

    FIXTURES["sourcepkg"] = RepositoryFixture("sourcepkg",
        dict(indra=dict(newview={"something.cpp": "fake C++ source file",
                                 "something.h": "fake C++ header file"}),
             LICENSES={"sourcepkg.txt": "fake license file"}),
        license="internal")
    # ----------------------- verify RepositoryFixture -----------------------
    fixture = FIXTURES["sourcepkg"]
    package = fixture.package
    assert package.name == "sourcepkg"
    assert package.source == fixture.pathname
    assert package.sourcetype == "hg"
    assert package.source_directory == "externs"
    assert package.license_file == os.path.join("LICENSES", "sourcepkg.txt")
    # -----------------------------------  -----------------------------------

def teardown():
    """
    Module-level teardown
    """
    # The MyHTTPServer thread created by setup() is a daemon, so it will
    # just go away when the process terminates.
    # But clean up directories.
    clean_dir(BASE_DIR)
    # fwiw, the default FakeOptions installed_filename lives in INSTALL_DIR,
    # so shouldn't need special cleanup of its own.
    # See comments for INIT_CACHE.
    clean_cache()

def clean_cache():
    """
    Restore the autobuild cache directory to the state it was in at the time
    setup() was called. We should be able to call this any number of times
    during the script run to avoid unintentional interactions between
    different tests.

    NOTE: The trouble with this approach is that concurrent test runs on the
    same machine, or a test coinciding with production use of autobuild
    install, could interact badly: the test script might discard a tarball
    added to the cache by some other process before it can be used. Should
    that become a problem, the best fix is to make autobuild's cache directory
    configurable (even if only by Python code), and make this script configure
    it to a directory somewhere under our BASE_DIR.
    """
    # We don't expect this to happen. But if control should somehow reach a
    # clean_cache() call before we first take inventory of the initial cache
    # state, if we simply let INIT_CACHE default to [], we'd conclude that we
    # must delete *every* file in the autobuild cache. That seems Bad.
    if INIT_CACHE is None:
        raise RuntimeError("clean_cache() called before module setup()!?")
    # Okay, we believe INIT_CACHE is valid. Inventory cache directory again
    # to discover what we've added since we started.
    cachedir = common.get_default_install_cache_dir()
    for f in set(os.listdir(cachedir)) - INIT_CACHE:
        clean_file(os.path.join(cachedir, f))

# ****************************************************************************
#   Local server machinery
# ****************************************************************************
class MyHTTPServer(Thread):
    """thread on which to run temp HTTP server"""
    def __init__(self, server, *args, **kwds):
        super(MyHTTPServer, self).__init__(*args, **kwds)
        self.server = server

    def run(self):
        self.server.serve_forever()

class DownloadServer(SimpleHTTPRequestHandler):
    """
    Want a file server almost like SimpleHTTPRequestHandler, but without
    depending on OS current directory.
    """
    def translate_path(self, path):
        """
        Clone-and-edit base-class translate_path() method, sigh. Unfortunately
        the logic that starts from os.getcwd() is built into the middle of
        that method.
        """
        # abandon query parameters
        path = urlparse.urlparse(path)[2]
        path = posixpath.normpath(urllib.unquote(path))
        words = path.split('/')
        words = filter(None, words)
        path = SERVER_DIR # <== the one changed line
        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.curdir, os.pardir): continue
            path = os.path.join(path, word)
        return path

    def log_request(self, code, size=None):
        # For present purposes, we don't want the request splattered onto
        # stderr, as it would upset devs watching the test run
        pass

    def log_error(self, format, *args):
        # Suppress error output as well
        pass

# ****************************************************************************
#   tests
# ****************************************************************************
class BaseTest(object):
    def __init__(self):
        self.tempfiles = []
        self.tempdirs = []

    def setup(self):
        # Each of these tests wants a variant config file.
        self.options = FakeOptions()
        self.config = self.options.use_temp_config()

    def copyto(self, source, destdir):
        return self.copy(source, in_dir(destdir, source))

    def copy(self, source, dest):
        shutil.copy2(source, dest)
        self.tempfiles.append(dest)
        return dest

    def new_package(self, package):
        # The reason for using new_package() instead of simply calling
        # set_package() all the time is to avoid confusion with the predefined
        # install_config file found in tests/data. If this assertion fires, we
        # should pick a different package name for the test.
        assert_not_in(package.name, self.config.installables)
        self.set_package(package)

    def set_package(self, package):
        # Capture a copy of the PackageDescription so that any subsequent
        # modifications to that PackageDescription metadata don't affect,
        # e.g., a globally-visible FIXTURES["packagename"].package entry.
        self.config.installables[package.name] = package.copy()
        self.config.save()

    def teardown(self):
        # Discard the temp config file we created.
        clean_file(self.options.install_filename)
        # If this test got as far as saving an updated installed manifest
        # file, remove that too: otherwise these tests would become order-
        # dependent! Any test resulting in a successful install of a given
        # package could cause subsequent tests to be bypassed.
        clean_file(self.options.installed_filename)
        # Actually, for the same reason, undo any successful install. To test
        # reinstalling, or installing several packages, explicitly perform the
        # desired sequence within a single test method.
        clean_dir(INSTALL_DIR)
        # Clean any temp files we created with copy().
        for f in self.tempfiles:
            clean_file(f)
        # Clean up any temp dirs we explicitly added to tempdirs.
        for d in self.tempdirs:
            clean_dir(d)
        # Always clean the download cache.
        clean_cache()

# -------------------------------------  -------------------------------------
class TestInstallArchive(BaseTest):
    def setup(self):
        BaseTest.setup(self)
        self.pkg = "bogus"
        fixture = FIXTURES[self.pkg + "-0.1"]
        # ArchiveFixture creates tarballs in STAGING_DIR. Have to copy to
        # SERVER_DIR if we want to be able to download.
        self.server_tarball = self.copyto(fixture.pathname, SERVER_DIR)
        # Create variant config file
        self.new_package(fixture.package)

    def test_success(self):
        autobuild_tool_install.install_packages(self.options, [self.pkg])
        assert os.path.exists(os.path.join(INSTALL_DIR, "lib", "bogus.lib"))
        assert os.path.exists(os.path.join(INSTALL_DIR, "include", "bogus.h"))

    def test_dry_run(self):
        dry_opts = self.options.copy()
        dry_opts.dry_run = True
        autobuild_tool_install.install_packages(dry_opts, [self.pkg])
        assert not os.path.exists(os.path.join(INSTALL_DIR, "lib", "bogus.lib"))
        assert not os.path.exists(os.path.join(INSTALL_DIR, "include", "bogus.h"))

    def test_reinstall(self):
        # test_success() establishes that this first one should work
        autobuild_tool_install.install_packages(self.options, [self.pkg])
        # Delete tarball from SERVER_DIR so our local server can't find it to
        # download. (Make darned sure it's gone: use os.remove() here instead
        # of clean_file(). If there's an exception, user should know why!)
        os.remove(self.server_tarball)
        # and clean cache
        clean_cache()
        # TestDownloadFail() establishes that when the tarball we need is
        # neither in cache nor in SERVER_DIR, we should get an InstallError.
        # Absence of that exception means install_packages() didn't even try
        # to fetch the tarball -- which should mean it realized this package
        # is already up-to-date.
        autobuild_tool_install.install_packages(self.options, [self.pkg])

    def test_update(self):
        # test_success() establishes that this first one should work
        autobuild_tool_install.install_packages(self.options, [self.pkg])
        # Get ready to update with newer version of same package name
        fixture = FIXTURES[self.pkg + "-0.2"]
        self.copyto(fixture.pathname, SERVER_DIR)
        # Modify config file with updated package description.
        self.set_package(fixture.package)
        try:
            autobuild_tool_install.install_packages(self.options, [self.pkg])
        except autobuild_tool_install.InstallError, err:
            # bogus-0.2 has no license file. We expect to fail
            # post_install_license_check().
            assert_in("license-check", str(err))
        else:
            assert False, "bogus-0.2 install failed to completely uninstall bogus-0.1"
        # okay, if we got this far, turn off license check
        self.options.check_license = False
        autobuild_tool_install.install_packages(self.options, [self.pkg])
        # verify that the update actually updated a file still in package
        assert_in("0.2", open(os.path.join(INSTALL_DIR, "include", "bogus.h")).read())

    def test_update_move(self):
        # test_success() establishes that this first one should work
        autobuild_tool_install.install_packages(self.options, [self.pkg])
        # Get ready to update with newer version of same package name
        fixture = FIXTURES[self.pkg + "-0.2"]
        self.copyto(fixture.pathname, SERVER_DIR)
        # Modify config file with updated package description.
        self.set_package(fixture.package)
        # turn off license check: we already know bogus-0.2 omits license file
        self.options.check_license = False
        # but pass different --install-dir
        old_install_dir = self.options.install_dir
        self.options.install_dir = os.path.join(os.path.dirname(old_install_dir), "other_packages")
        self.tempdirs.append(self.options.install_dir)
        autobuild_tool_install.install_packages(self.options, [self.pkg])
        # verify uninstall in old_install_dir
        assert not os.path.exists(os.path.join(old_install_dir, "lib", "bogus.lib"))
        assert not os.path.exists(os.path.join(old_install_dir, "include", "bogus.h"))
        # verify install in new --install-dir
        assert os.path.exists(os.path.join(self.options.install_dir, "lib", "bogus.lib"))
        assert os.path.exists(os.path.join(self.options.install_dir, "include", "bogus.h"))

# -------------------------------------  -------------------------------------
class TestInstallCachedArchive(BaseTest):
    def setup(self):
        BaseTest.setup(self)
        self.pkg = "bogus"
        fixture = FIXTURES[self.pkg + "-0.1"]
        # ArchiveFixture creates tarballs in STAGING_DIR. Don't copy to
        # SERVER_DIR; in fact ensure it's not there.
        assert not os.path.exists(in_dir(SERVER_DIR, fixture.pathname))
        # Instead copy directly to cache dir.
        self.copyto(fixture.pathname, common.get_default_install_cache_dir())
        # Create variant config file
        self.new_package(fixture.package)

    def test_success(self):
        autobuild_tool_install.install_packages(self.options, [self.pkg])
        assert os.path.exists(os.path.join(INSTALL_DIR, "lib", "bogus.lib"))
        assert os.path.exists(os.path.join(INSTALL_DIR, "include", "bogus.h"))

# -------------------------------------  -------------------------------------
class TestDownloadFail(BaseTest):
    def setup(self):
        BaseTest.setup(self)
        self.pkg = "bogus"
        fixture = FIXTURES[self.pkg + "-0.1"]
        # ArchiveFixture creates tarballs in STAGING_DIR. Don't copy to
        # SERVER_DIR; in fact ensure it's neither there nor in cache dir.
        assert not os.path.exists(in_dir(SERVER_DIR, fixture.pathname))
        self.cache_name = in_dir(common.get_default_install_cache_dir(), fixture.pathname)
        assert not os.path.exists(self.cache_name)
        # Create variant config file
        self.new_package(fixture.package)

    def test_bad(self):
        try:
            autobuild_tool_install.install_packages(self.options, [self.pkg])
        except autobuild_tool_install.InstallError, err:
            assert_in("download", str(err))
            assert not os.path.exists(self.cache_name)
        else:
            assert False, "expected InstallError for download failure"

# -------------------------------------  -------------------------------------
class TestGarbledDownload(BaseTest):
    def setup(self):
        BaseTest.setup(self)
        self.pkg = "bogus"
        fixture = FIXTURES[self.pkg + "-0.1"]
        # ArchiveFixture creates tarballs in STAGING_DIR. Have to copy to
        # SERVER_DIR if we want to be able to download.
        self.copyto(fixture.pathname, SERVER_DIR)
        self.cache_name = in_dir(common.get_default_install_cache_dir(), fixture.pathname)
        assert not os.path.exists(self.cache_name)
        # Fake up a PackageDescription with bad MD5 without disturbing
        # FIXTURES["bogus-0.1"], which is shared with several other tests.
        badpkg = fixture.package.copy()
        badpkg.platforms["darwin"].archive.hash = "BAADBAAD"
        # Create variant config file
        self.new_package(badpkg)

    def test_bad(self):
        try:
            autobuild_tool_install.install_packages(self.options, [self.pkg])
        except autobuild_tool_install.InstallError, err:
            assert_in("md5", str(err))
            assert not os.path.exists(self.cache_name)
        else:
            assert False, "expected InstallError for md5 mismatch"

# -------------------------------------  -------------------------------------
class TestInstallRepository(BaseTest):
    def setup(self):
        BaseTest.setup(self)
        self.pkg = "sourcepkg"
        fixture = FIXTURES[self.pkg]
        self.new_package(fixture.package)
        self.options.as_source.append(fixture.package.name)
        self.install_dir = os.path.join(os.path.dirname(self.options.install_filename),
                                        fixture.package.source_directory, self.pkg)
        self.tempdirs.append(self.install_dir)

    def test_success(self):
        autobuild_tool_install.install_packages(self.options, [self.pkg])
        assert os.path.exists(os.path.join(self.install_dir, "indra", "newview", "something.cpp"))
        assert os.path.exists(os.path.join(self.install_dir, "indra", "newview", "something.h"))

    def test_dry_run(self):
        dry_opts = self.options.copy()
        dry_opts.dry_run = True
        autobuild_tool_install.install_packages(dry_opts, [self.pkg])
        assert not os.path.exists(os.path.join(self.install_dir, "indra", "newview", "something.cpp"))
        assert not os.path.exists(os.path.join(self.install_dir, "indra", "newview", "something.h"))

    def test_bad_source_attrs(self):
        # Use nose test generator functionality. We want to run a number of
        # independent tests, all of which are very similar. This generator
        # approach is shorthand for writing individual named test methods,
        # each of whose bodies consists solely of a call to bad_source_attr().
        yield self.bad_source_attr, "nonexistent source repository", \
              "source", os.path.join(STAGING_DIR, "nonexistent"), "cloning"
        yield self.bad_source_attr, "missing source URL", "source", None, "url"
        yield self.bad_source_attr, "missing source type", "sourcetype", None, "type"
        yield self.bad_source_attr, "bad source type", "sourcetype", "xyz", "type"
        yield self.bad_source_attr, "missing source directory", \
              "source_directory", None, "directory"

    def bad_source_attr(self, desc, attr, value, errfrag):
        # Set the specified attribute ("source", "sourcetype", "source_directory")
        setattr(self.config.installables[self.pkg], attr, value)
        # Save the resulting config file, without which the above is pointless.
        self.config.save()
        try:
            # Try to install --as-source with the specified value.
            autobuild_tool_install.install_packages(self.options, [self.pkg])
        except autobuild_tool_install.InstallError, err:
            # Verify the expected error fragment.
            assert_in(errfrag, str(err))
        else:
            assert False, "expected InstallError for %s %s" % (desc, value)

    def test_reinstall_no_as_source(self):
        # First make a temp clone of this repository because, in this test, we
        # modify it.
        temprepobase = tempfile.mkdtemp(dir=STAGING_DIR)
        logger.debug("created %s" % temprepobase)
        self.tempdirs.append(temprepobase)
        temprepo = os.path.join(temprepobase, self.pkg)
        command = ["hg", "clone", "-q", self.config.installables[self.pkg].source, temprepo]
        logger.debug(' '.join(command))
        subprocess.check_call(command)
        # Update source URL to point to the new clone.
        self.config.installables[self.pkg].source = temprepo
        self.config.save()
        # test_success() establishes that this works
        autobuild_tool_install.install_packages(self.options, [self.pkg])
        something_relpath = os.path.join("indra", "newview", "something.cpp")
        something_source = os.path.join(self.install_dir, something_relpath)
        assert os.path.exists(something_source)
        assert_not_in("changed", open(something_source).read())
        # Now change the repository.
        f = open(os.path.join(temprepo, something_relpath), "w")
        f.write("changed data\n")
        f.close()
        subprocess.check_call(["hg", "--cwd", temprepo,
                               "commit", "-m", "change", something_relpath])
        # Remove --as-source flag from next command line to prove we remember
        # that this package was previously installed --as-source.
        self.options.as_source.remove(self.pkg)
        autobuild_tool_install.install_packages(self.options, [self.pkg])
        # If we fail to remember this package was previously installed
        # --as-source, we'll blow up trying to install a nonexistent archive.
        # If we try to clone over the previous install_dir, we'll blow up.
        # If we update it, we'll change something_source.
        assert_not_in("changed", open(something_source).read())
        # Prove that the last test was meaningful by manually updating the
        # installed repo and observing the change.
        subprocess.check_call(["hg", "--repository", self.install_dir, "pull", "-u", "-q"])
        assert_in("changed", open(something_source).read())

    def test_uninstall_reinstall(self):
        # test_success() already verifies this
        autobuild_tool_install.install_packages(self.options, [self.pkg])
        assert os.path.exists(os.path.join(self.install_dir, "indra", "newview", "something.cpp"))
        assert os.path.exists(os.path.join(self.install_dir, "indra", "newview", "something.h"))
        # ensure that uninstall leaves it alone
        autobuild_tool_uninstall.uninstall_packages(self.options, [self.pkg])
        assert os.path.exists(os.path.join(self.install_dir, "indra", "newview", "something.cpp"))
        assert os.path.exists(os.path.join(self.install_dir, "indra", "newview", "something.h"))
        # but now we no longer remember the previous install, so will try to
        # install over existing directory, which will blow up.
        try:
            autobuild_tool_install.install_packages(self.options, [self.pkg])
        except autobuild_tool_install.InstallError, err:
            assert_in("existing", str(err))
        else:
            assert False, "Expecting InstallError from reinstall --as-source over existing dir"

# -------------------------------------  -------------------------------------
class TestMockSubversion(BaseTest):
    def setup(self):
        BaseTest.setup(self)
        self.pkg = "sourcepkg"
        fixture = FIXTURES[self.pkg]
        svnpkg = fixture.package.copy()
        svnpkg.sourcetype = "svn"
        self.new_package(svnpkg)
        self.options.as_source.append(svnpkg.name)

    def test_mock_svn(self):
        real_subprocess = autobuild_tool_install.subprocess
        mock_subprocess = MockSubprocess()
        autobuild_tool_install.subprocess = mock_subprocess
        try:
            try:
                autobuild_tool_install.install_packages(self.options, [self.pkg])
            except autobuild_tool_install.InstallError, err:
                assert_in("checking out", str(err))
            else:
                assert False, "Expected InstallError from mock svn checkout"
        finally:
            autobuild_tool_install.subprocess = real_subprocess
        assert_equals(len(mock_subprocess.commands), 1)
        assert_equals(mock_subprocess.commands[0][:2], ["svn", "checkout"])

class MockSubprocess(object):
    def __init__(self):
        self.commands = []

    def call(self, command):
        logger.debug("MockSubprocess: " + ' '.join(command))
        self.commands.append(command)
        # Fake that we fail the checkout
        return 2

    # Tests to add:
    # - have get_packages_to_install() reject packages for each reason
    #   - unknown package
    #   - no platform entry for this platform
    #   - no platform entry, but "common" -- should succeed
    #   - no archive for platform entry
    # - test each handle_query_args() argument:
    #   - list-installed
    #   - list-archives
    #   - list-licenses
    #   - export-manifest <- visibility into modified installed-packages.xml
    # - fail pre_install_license_check()
    #   - no license entry
    #   - specify --skip-license-check -- should succeed

# -------------------------------------  -------------------------------------
class TestInstall(unittest.TestCase):
    def test_0(self):
        """
        Try to download and install the packages to tests/packages
        """
        # Use all default options, bearing in mind that FakeOptions defaults
        # are biased towards our fixture data.
        options = FakeOptions()
        autobuild_tool_install.install_packages(options, None)

        # do an extra check to make sure the install worked
        lic_dir = os.path.join(options.install_dir, "LICENSES")
        if not os.path.exists(lic_dir):
            self.fail("Installation did not install a LICENSES dir")
        for f in "argparse.txt", "tut.txt":
            if not os.path.exists(os.path.join(lic_dir, f)):
                self.fail("Installing all packages failed to install LICENSES/%s" % f)

# ****************************************************************************
#   Fixture data creation
# ****************************************************************************
class BaseFixture(object):
    """
    Subclass objects are stored as values in the FIXTURES dict.
    """
    def __init__(self):
        self.pathname = None            # pathname to archive/repos
        self.package = None             # PackageDescription describing this item

    def _set_default_license_file(self, kwds, _contents):
        # Trickiness: if _contents specifies a LICENSES directory, and if that
        # directory contains at least one file, and if license_file= wasn't
        # explicitly specified, set license_file to that relative path.
        try:
            license_dir = _contents["LICENSES"]
        except KeyError:
            pass
        else:
            try:
                license_file = license_dir.iterkeys().next()
            except StopIteration:
                pass
            else:
                kwds.setdefault("license_file", os.path.join("LICENSES", license_file))

class ArchiveFixture(BaseFixture):
    """
    Construct an object of this class with a tarball name, a dict specifying
    tarball content (a la make_tarball_from_dict()), plus arbitrary keyword
    args specifying PackageDescription metadata. Certain fields are filled in
    for you based on the tarball in hand.

    A relative tarball name is constructed in STAGING_DIR.
    """
    def __init__(self, _tarname, _contents, **kwds):
        self.pathname = os.path.join(STAGING_DIR, _tarname)
        make_tarball_from_dict(self.pathname, _contents)
        # If name= wasn't explicitly passed, derive from first part of tarball
        # name, e.g. bogus-0.1-darwin-20101022.tar.bz2 produces "bogus".
        name, version, platform, _ = common.split_tarname(_tarname)[1]
        kwds.setdefault("name", name)
        kwds.setdefault("version", version)
        archive_dict = kwds.setdefault("platforms", {}).setdefault(platform, {}).setdefault("archive", {})
        archive_dict.setdefault("hash_algorithm", "md5")
        archive_dict.setdefault("hash", common.compute_md5(self.pathname))
        archive_dict.setdefault("url", url_for(os.path.basename(_tarname)))
        self._set_default_license_file(kwds, _contents)
        self.package = configfile.PackageDescription(kwds)

class RepositoryFixture(BaseFixture):
    """
    Construct an object of this class with a repository name, a dict
    specifying repository content (a la make_repos_from_dict()), plus
    arbitrary keyword args specifying PackageDescription metadata. Certain
    fields are filled in for you based on the repository in hand.

    A relative repository name is constructed in STAGING_DIR.
    """
    def __init__(self, _repo_name, _contents, **kwds):
        self.pathname = os.path.join(STAGING_DIR, _repo_name)
        make_repos_from_dict(self.pathname, _contents)
        # If name= wasn't explicitly specified, set it to the repository name.
        kwds.setdefault("name", os.path.basename(_repo_name))
        kwds.setdefault("source", self.pathname)
        kwds.setdefault("sourcetype", "hg")
        kwds.setdefault("source_directory", "externs")
        self._set_default_license_file(kwds, _contents)
        self.package = configfile.PackageDescription(kwds)

def make_tarball_from_dict(pathname, tree):
    """
    This function allows you to construct a fixture tarball at the specified
    pathname from a dict. 'pathname' should not yet exist. 'tree' is of the
    form required by make_dir_from_dict() -- although we don't support the
    degenerate case in which the top-level 'tree' is simply a string. That
    would imply that the desired 'tarball' is simply a compressed file. If
    that's really what you want, do it yourself.
    """
    tempdir = tempfile.mkdtemp()
    try:
        # Construct the desired subdirectory tree in tempdir.
        make_dir_from_dict(tempdir, tree)
        # Now make a tarball at pathname from tempdir.
        tarball = tarfile.open(pathname, "w:bz2")
        # Add the directory found at 'tempdir', but do not embed its full
        # pathname in the tarball.
        tarball.add(tempdir, ".")
        tarball.close()
        return pathname
    finally:
        # Clean up tempdir.
        clean_dir(tempdir)

def make_repos_from_dict(pathname, tree):
    """
    This function allows you to construct a local Mercurial repository at the
    specified pathname from a dict. 'pathname' should not yet exist. 'tree' is
    of the form required by make_dir_from_dict() (non-degenerate case).
    """
    subprocess.check_call(["hg", "init", pathname])
    make_dir_from_dict(pathname, tree)
    subprocess.check_call(["hg", "--repository", pathname, "add", "-q"])
    subprocess.check_call(["hg", "--repository", pathname, "commit", "-m", "create"])

def make_dir_from_dict(pathname, tree):
    """
    This function allows you to specify fixture data -- a directory tree in
    the filesystem -- by constructing a dict.

    It's always valid to specify a 'pathname' that doesn't exist (though its
    parent directory should exist). Otherwise:

    - If 'tree' is a simple string, 'pathname' should identify a file that can
      be replaced.

    - If 'tree' is a dict, 'pathname' should identify a directory.

    We recursively walk the passed tree. For each (key, value) item:

    - If 'value' is a string, write it to a file with name 'key' in the
      current subdirectory.

    - If 'value' is a dict, create a subdirectory with name 'key' in the
      current subdirectory and recur.
    """
    if isinstance(tree, basestring):
        # This node of the tree is a string.
        f = open(pathname, "w")
        f.write(tree)
        f.close()
        return pathname

    try:
        # A dict will have an iteritems method.
        iteritems = tree.iteritems
    except AttributeError:
        # At least as of Python 2.5, even builtin values like 5 or 3.14 can be
        # queried for __class__.__name__! ("int" and "float", respectively)
        raise TypeError("make_dir_from_dict(): entry %s must either be string or dict, "
                        "not %s %r" % (os.path.basename(pathname), tree.__class__.__name__, tree))

    # Since 'tree' is a dict, create a subdir in which to hold its entries.
    try:
        os.mkdir(pathname)
    except OSError, err:
        if err.errno != errno.EEXIST:
            raise
    # Okay, now walk its entries.
    for key, value in iteritems():
        make_dir_from_dict(os.path.join(pathname, key), value)

    return pathname

if __name__ == '__main__':
    unittest.main()
