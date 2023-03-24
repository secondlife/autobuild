import logging
import os
import posixpath
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler
from string import Template
from threading import Thread
from unittest import TestCase
from unittest.mock import MagicMock, patch

from autobuild import autobuild_tool_install, autobuild_tool_uninstall, common
from autobuild.autobuild_tool_install import CredentialsNotFoundError
from tests.basetest import *

# ****************************************************************************
#   TODO
# - Verify test for specific --install-dir (new select_directories() mechanism)
# - Test [un]installing to/from configuration-specific build directory
# - Test [un]installing to/from --all configurations
# - Test [un]installing to/from build directory(ies) for specified --configuration(s)
# ****************************************************************************

mydir = os.path.dirname(__file__)
HOST = '127.0.0.1'                      # localhost server
PORT = 8800                             # base port, may change
BASE_DIR = None                         # put all test temp files here for easy cleanup
STAGING_DIR = None                      # create archives/repos here, copy as needed
SERVER_DIR = None                       # populate this directory with files to "download"
INSTALL_DIR = None                      # where to find installed files

FakeOptions = None                      # placeholder for class defined in setup()

logger = logging.getLogger("autobuild.test_install")

# ****************************************************************************
#   utilities
# ****************************************************************************
def url_for(tail):
    return "http://%s:%s/%s" % (HOST, PORT, tail)

def in_dir(dir, file):
    return os.path.join(dir, os.path.basename(file))

def set_from_stream(stream):
    """
    For stream.getvalue() containing something like:

    Prefix: a, b, c\n

    return set(("a", "b", "c"))
    """
    # We expect output like: Packages: argparse, bogus\n
    # Split off the initial 'Packages:' by splitting on the first ':' and
    # taking only what's to the right of it; strip whitespace off both
    # ends of that; split on comma-space; load into a set for order-
    # independent equality comparison.
    return set(stream.getvalue().split(':', 1)[1].strip().split(", "))

def query_manifest(options=None):
    options = options.copy() if options else FakeOptions()
    options.export_manifest = True
    with CaptureStdout() as stream:
        autobuild_tool_install.AutobuildTool().run(options)
    raw = stream.getvalue()
    if not raw.strip():
        # If output is completely empty, eval() would barf -- but that's okay,
        # that means an empty sequence.
        sequence = ()
    else:
        # Output isn't empty: should be Python-parseable.
        try:
            sequence = eval(raw)
        except Exception as err:
            logger.error("couldn't parse --export-manifest output:\n" + raw)
            raise
    logger.debug("--export-manifest output:\n" + raw)
    # Convert sequence of dicts to dict of dicts -- much more useful
    return dict((item.get("package_description").get("name"), item) for item in sequence)

# ****************************************************************************
#   module setup() and teardown()
# ****************************************************************************
def setup_module(module):
    """
    Module-level setup
    """
    global BASE_DIR, STAGING_DIR, SERVER_DIR, INSTALL_DIR
    BASE_DIR = tempfile.mkdtemp()
    STAGING_DIR = os.path.join(BASE_DIR, "data")
    os.mkdir(STAGING_DIR)
    SERVER_DIR = os.path.join(BASE_DIR, "server")
    os.mkdir(SERVER_DIR)
    INSTALL_DIR = os.path.join(BASE_DIR, "packages")
    # We expect autobuild_tool_install to create INSTALL_DIR.

    # For development purposes, we often have an http_proxy environment
    # variable set to proxy through a remote server. But for trying to
    # connect to a localhost server, that's the OPPOSITE of what we want.
    os.environ.pop("http_proxy", None) # no error if missing

    # For the duration of this script, run a server thread from which to
    # direct autobuild to "download" test archives. Various tests will
    # populate SERVER_DIR with files whose URLs they will then request. But
    # first, claim a localhost port on which to run this temp server.
    global PORT
    httpd = HTTPServer((HOST, 0), DownloadServer)
    PORT = httpd.server_port
    # Here httpd is an HTTPServer instance waiting for a serve_forever() call.
    thread = MyHTTPServer(httpd, name="httpd")
    # Start server thread. Make it a daemon thread: we'll let it run
    # "forever," confident that the whole process will terminate when the main
    # thread (unittest) terminates.
    thread.daemon = True
    thread.start()

    # define FakeOptions class here (but in global namespace) because it
    # depends on INSTALL_DIR.
    global FakeOptions
    class FakeOptions(object):
        """
        Creates a fake argparse options structure to simulate
        passing in a number of command line options. Override with a keyword
        argument any specific options item you want to set, e.g.:

        FakeOptions(local_archives=["mypackage"])

        A default set of options is created in BaseTest.setup, and can be referenced in a test as
        self.options; options may be overridden by assignment:

        self.options.package=["other"]
        """
        def __init__(self,
                     install_filename=None,
                     installed_filename=os.path.join(INSTALL_DIR, "installed-packages.xml"),
                     select_dir=INSTALL_DIR, # uses common.select_directories() now
                     platform="common",
                     dry_run=False,
                     list_archives=False,
                     list_installed=False,
                     list_licenses=False,
                     copyrights=False,
                     versions=False,
                     list_installed_urls=False,
                     list_dirty=False,
                     all=False,
                     configurations=[],
                     query_installed_file=False,
                     check_license=True,
                     export_manifest=False,
                     logging_level=logging.DEBUG,
                     local_archives=[],
                     addrsize=32,
                     package=[],
                     skip_source_environment=False,
                     ):
            # Take all constructor params and assign as object attributes.
            params = locals().copy()
            # We have a couple locals() that aren't supposed to set attributes.
            del params["self"]
            params.pop("params", None)  # may or may not be there yet?
            self.__dict__.update(params)
            # Remember attribute names for copy() implementation
            self._attrs = list(params.keys())

        def copy(self):
            # Get a (key, value) pair for each attribute defined in our
            # constructor param list. From those, construct a dict; then pass
            # that dict as keyword arguments to our own class's constructor to
            # make a new instance.
            return self.__class__(**dict((attr, getattr(self, attr)) for attr in self._attrs))

    # -----------------------------------  -----------------------------------

def teardown_module(module):
    """
    Module-level teardown
    """
    # The MyHTTPServer thread created by setup() is a daemon, so it will
    # just go away when the process terminates.
    # But clean up directories.
    clean_dir(BASE_DIR)

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
        path = urllib.parse.urlparse(path)[2]
        path = posixpath.normpath(urllib.parse.unquote(path))
        words = path.split('/')
        words = [_f for _f in words if _f]
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
class BaseTest(TestCase):
    default_config="packages-install.xml"

    def setup_method(self, module):
        self.tempfiles = []
        self.tempdirs = []
        # construct default options
        self.options = FakeOptions(install_filename=self.localizedConfig(self.default_config))
        # do not use the normal system cache so that unit tests can't leave anything
        # in them even in the event of errors
        temp_cache_dir=tempfile.mkdtemp(suffix="_inst_cache")
        self.tempdirs.append(temp_cache_dir)
        self.cache_dir=temp_cache_dir
        os.environ['AUTOBUILD_INSTALLABLE_CACHE'] = temp_cache_dir
        # put the default archives in the server (some tests undo this or use other archives)
        self.server_tarball= self.copyto(os.path.join(mydir, "data", "bogus-0.1-common-111.tar.bz2"), SERVER_DIR)
        self.server_tarball= self.copyto(os.path.join(mydir, "data", "argparse-1.1-common-111.tar.bz2"), SERVER_DIR)
        logger.setLevel(self.options.logging_level)

    def copyto(self, source, destdir):
        return self.copy(source, in_dir(destdir, source))

    def copy(self, source, dest):
        shutil.copy2(source, dest)
        self.tempfiles.append(dest)
        return dest

    def instantiateTemplate(self, source, tmp_dest, changes):
        template_file=open(source,'r')
        template=Template(template_file.read())
        template_file.close()
        content=template.substitute(changes)
        tmp_dest.write(content)

    def localizedConfig(self, template):
        temp_config_basename=os.path.splitext(os.path.basename(template))[0]
        temp_config_fd, config_filename=tempfile.mkstemp(prefix=os.path.join(mydir, "data", temp_config_basename+"-"),suffix="-local.xml")
        temp_config=os.fdopen(temp_config_fd,'w')
        template_path=os.path.join(mydir,"data",template)
        logger.debug("localize config file '%s' -> '%s'" % (template_path,config_filename))
        self.instantiateTemplate(template_path, temp_config, {'PORT':PORT})
        self.tempfiles.append(config_filename)
        temp_config.close()
        return config_filename

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
        self.config.installables[package.name] = package.copy()

    def teardown_method(self, method):
        # Actually, for the same reason, undo any successful install. To test
        # reinstalling, or installing several packages, explicitly perform the
        # desired sequence within a single test method.
        clean_dir(INSTALL_DIR)
        # Clean any temp files we created with copy().
        for f in self.tempfiles:
            logger.debug("teardown deleting tempfile %s" % f)
            clean_file(f)
        # Clean up any temp dirs we explicitly added to tempdirs.
        for d in self.tempdirs:
            clean_dir(d)

# -------------------------------------  -------------------------------------
class TestInstallArchive(BaseTest):
    def setup_method(self, method):
        super(TestInstallArchive, self).setup_method(method)
        self.pkg = "bogus"
        self.options.package = [self.pkg]

    def test_success(self):
        assert_not_in(self.pkg, query_manifest(self.options))
        autobuild_tool_install.AutobuildTool().run(self.options)
        assert os.path.exists(os.path.join(INSTALL_DIR, "lib", "bogus.lib"))
        assert os.path.exists(os.path.join(INSTALL_DIR, "include", "bogus.h"))
        assert_in(self.pkg, query_manifest(self.options))
        with CaptureStdout() as stream:
            self.options.list_dirty=True
            autobuild_tool_install.AutobuildTool().run(self.options)
        self.assertEqual(stream.getvalue(), 'Dirty Packages: \n')

    def test_dry_run(self):
        dry_opts = self.options.copy()
        dry_opts.dry_run = True
        autobuild_tool_install.AutobuildTool().run(dry_opts)
        assert_not_in(self.pkg, query_manifest(self.options))
        assert not os.path.exists(os.path.join(INSTALL_DIR, "lib", "bogus.lib"))
        assert not os.path.exists(os.path.join(INSTALL_DIR, "include", "bogus.h"))

    def test_reinstall(self):
        # test_success() establishes that this first one should work
        autobuild_tool_install.AutobuildTool().run(self.options)
        # TestDownloadFail() establishes that when the tarball we need is
        # neither in cache nor in SERVER_DIR, we should get an InstallError.
        # Absence of that exception means AutobuildTool().run() didn't even try
        # to fetch the tarball -- which should mean it realized this package
        # is already up-to-date.
        # An earlier version of this test had both cleaned the cache and removed the
        # tarball from the server, expecting that the mere presence of the installed
        # archive would be sufficient to keep it from being installed again; we
        # now require that the file be validated against at least a cached file.
        logger.debug("attempt reinstall with cached file")
        autobuild_tool_install.AutobuildTool().run(self.options)
        clean_dir(self.cache_dir)
        logger.debug("attempt reinstall without cached file")
        autobuild_tool_install.AutobuildTool().run(self.options)

    def test_update(self):
        # test_success() establishes that this first one should work
        autobuild_tool_install.AutobuildTool().run(self.options)
        assert os.path.exists(os.path.join(self.options.select_dir, "lib", "bogus.lib"))
        assert os.path.exists(os.path.join(self.options.select_dir, "include", "bogus.h"))
        # Get ready to update with newer version of same package name
        self.server_tarball = self.copyto(os.path.join(mydir, "data", "bogus-0.2-common-222.tar.bz2"), SERVER_DIR)
        self.options=FakeOptions(install_filename=self.localizedConfig("package-update-install.xml"))
        self.options.package=["bogus"]
        autobuild_tool_install.AutobuildTool().run(self.options)
        # verify that the update actually updated a file still in package
        assert_in("0.2", open(os.path.join(INSTALL_DIR, "include", "bogus.h")).read())

    def test_update_move(self):
        # test_success() establishes that this first one should work - installs bogus 0.1
        autobuild_tool_install.AutobuildTool().run(self.options)
        assert os.path.exists(os.path.join(self.options.select_dir, "lib", "bogus.lib"))
        assert os.path.exists(os.path.join(self.options.select_dir, "include", "bogus.h"))
        # Get ready to update with newer version of same package name
        self.server_tarball = self.copyto(os.path.join(mydir, "data", "bogus-0.2-common-222.tar.bz2"), SERVER_DIR)
        # pass different --install-dir
        old_select_dir = self.options.select_dir
        self.options=FakeOptions(package=["bogus"],
                                 install_filename=self.localizedConfig("package-update-install.xml"),
                                 select_dir = os.path.join(os.path.dirname(old_select_dir), "other_packages"))
        self.tempdirs.append(self.options.select_dir)
        autobuild_tool_install.AutobuildTool().run(self.options)
        # verify uninstall in old_select_dir
        assert not os.path.exists(os.path.join(old_select_dir, "lib", "bogus.lib"))
        assert not os.path.exists(os.path.join(old_select_dir, "include", "bogus.h"))
        # verify install in new --install-dir
        assert os.path.exists(os.path.join(self.options.select_dir, "lib", "bogus.lib"))
        assert os.path.exists(os.path.join(self.options.select_dir, "include", "bogus.h"))
        assert_in("0.2", open(os.path.join(self.options.select_dir, "include", "bogus.h")).read())

    def test_unknown(self):
        with ExpectError("unknown package:", "Expected InstallError for unknown package name"):
            self.options.package=["no_such_package"]
            autobuild_tool_install.AutobuildTool().run(self.options)
        assert not os.path.exists(os.path.join(INSTALL_DIR, "lib", "bogus.lib"))
        assert not os.path.exists(os.path.join(INSTALL_DIR, "include", "bogus.h"))

    def test_no_platform(self):
        self.options=FakeOptions(install_filename=self.localizedConfig("packages-failures.xml"),package=["noplatform"])
        autobuild_tool_install.AutobuildTool().run(self.options)
        assert not os.path.exists(os.path.join(INSTALL_DIR, "lib", "bogus.lib"))
        assert not os.path.exists(os.path.join(INSTALL_DIR, "include", "bogus.h"))

    def test_no_archive(self):
        self.options=FakeOptions(install_filename=self.localizedConfig("packages-failures.xml"),package=["noarchive"])
        with ExpectError("noarchive", "Expected InstallError for missing ArchiveDescription"):
            autobuild_tool_install.AutobuildTool().run(self.options)

    def test_no_url(self):
        self.options=FakeOptions(package=["nourlconfig"],
                                 install_filename=self.localizedConfig("nourl-install.xml"))
        with ExpectError("no url specified", "Expected InstallError for missing archive url"):
            autobuild_tool_install.AutobuildTool().run(self.options)

    def test_no_license(self):
        # fail because both the package metadata and configuration lack a license
        self.server_tarball = self.copyto(os.path.join(mydir, "data", "nolicense-0.1-common-111.tar.bz2"), SERVER_DIR)
        self.options=FakeOptions(install_filename=self.localizedConfig("packages-failures.xml"),package=["nolicense"])
        with ExpectError("no license specified", "Expected InstallError for missing license"):
            autobuild_tool_install.AutobuildTool().run(self.options)

    def test_no_metadata(self):
        # package lacks metadata (autobuild-package.xml), so the result should be dirty
        self.server_tarball = self.copyto(os.path.join(mydir, "data", "nometa-0.1-common-111.tar.bz2"), SERVER_DIR)
        self.options=FakeOptions(install_filename=self.localizedConfig("packages-failures.xml"),package=["nometa"])
        autobuild_tool_install.AutobuildTool().run(self.options)
        with CaptureStdout() as stream:
            self.options.list_dirty=True
            autobuild_tool_install.AutobuildTool().run(self.options)
        self.assertEqual(stream.getvalue(), 'Dirty Packages: nometa\n')

    def test_conflicting_file(self):
        # fail because the package contains a file installed by another package
        # packages 'bogus' and 'conflict' both install include/bogus.txt
        # first, install the default 'bogus' package (should succeed)
        autobuild_tool_install.AutobuildTool().run(self.options)
        self.server_tarball = self.copyto(os.path.join(mydir, "data", "conflict-0.1-common-111.tar.bz2"), SERVER_DIR)
        # set up a new configuration file that defines the package with the conflict
        self.options=FakeOptions(install_filename=self.localizedConfig("package-update-install.xml"),package=["conflict"])
        # then try to install the 'conflict' package locally (should fail)
        self.options.local_archives = [os.path.join(mydir, "data", "conflict-0.1-common-111.tar.bz2")]
        with ExpectError("attempts to install files already installed", "Expected InstallError for conflicting files"):
            autobuild_tool_install.AutobuildTool().run(self.options)
        # then try to install the 'conflict' package remotely (should fail)
        self.options.local_archives = []
        with ExpectError("attempts to install files already installed", "Expected InstallError for conflicting files"):
            autobuild_tool_install.AutobuildTool().run(self.options)

    def test_conflicting_direct_depends(self):
        # fail because the package is a different version than an existing dependency
        # installing 'bingo', but already installed 'bongo' used a different 'bingo' version
        # first, install the default 'bogus' package (should succeed)
        self.server_tarball = self.copyto(os.path.join(mydir, "data", "bingo-0.1-common-111.tar.bz2"), SERVER_DIR)
        self.server_tarball = self.copyto(os.path.join(mydir, "data", "bongo-0.1-common-111.tar.bz2"), SERVER_DIR)
        # set up a new configuration file that installs 'bingo'
        self.options=FakeOptions(install_filename=self.localizedConfig("package-conflict.xml"),package=["bingo"])
        autobuild_tool_install.AutobuildTool().run(self.options)
        # then try to install the 'bongo' package (should fail)
        self.options.package=["bongo"]
        with ExpectError("not installable due to conflicts", "Expected InstallError for dependency conflicts"):
            autobuild_tool_install.AutobuildTool().run(self.options)
        # then try to install the 'bongo' package locally (should fail)
        self.options.local_archives = [os.path.join(mydir, "data", "bongo-0.1-common-111.tar.bz2")]
        with ExpectError("not installable due to conflicts", "Expected InstallError for dependency conflicts"):
            autobuild_tool_install.AutobuildTool().run(self.options)

    def test_conflicting_indirect_depends(self):
        # fail because the package is a different version than an existing dependency
        # installing 'bingo', but already installed 'bongo' used a different 'bingo' version
        # first, install the default 'bogus' package (should succeed)
        autobuild_tool_install.AutobuildTool().run(self.options)
        self.server_tarball = self.copyto(os.path.join(mydir, "data", "bingo-0.1-common-111.tar.bz2"), SERVER_DIR)
        self.server_tarball = self.copyto(os.path.join(mydir, "data", "bongo-0.1-common-111.tar.bz2"), SERVER_DIR)
        # set up a new configuration file that installs the first package
        self.options=FakeOptions(install_filename=self.localizedConfig("package-conflict.xml"),package=["bongo"])
        autobuild_tool_install.AutobuildTool().run(self.options)
        # then try to install the 'bongo' package (should fail)
        self.options.package=["bingo"]
        with ExpectError("not installable due to conflicts", "Expected InstallError for dependency conflicts"):
            autobuild_tool_install.AutobuildTool().run(self.options)
        # then try to install the 'bongo' package locally (should fail)
        self.options.local_archives = [os.path.join(mydir, "data", "bingo-0.1-common-111.tar.bz2")]
        with ExpectError("not installable due to conflicts", "Expected InstallError for dependency conflicts"):
            autobuild_tool_install.AutobuildTool().run(self.options)


    def test_list_archives(self):
        self.options.list_archives = True
        with CaptureStdout() as stream:
            autobuild_tool_install.AutobuildTool().run(self.options)
        self.assertEqual(set_from_stream(stream), set(('argparse', 'bogus')))

    def test_list_licenses(self):
        self.options.package = None # install all
        autobuild_tool_install.AutobuildTool().run(self.options)

        self.options.list_licenses = True
        with CaptureStdout() as stream:
            autobuild_tool_install.AutobuildTool().run(self.options)
        self.assertEqual(set_from_stream(stream), set(("GPL", "Apache 2.0", "tut")))

    def test_copyrights(self):
        self.options.package = None # install all
        autobuild_tool_install.AutobuildTool().run(self.options)

        self.options.copyrights = True
        with CaptureStdout() as stream:
            autobuild_tool_install.AutobuildTool().run(self.options)
        self.assertEqual(stream.getvalue(), "Copyright 2014 Linden Research, Inc.\nbogus: The Owner\n")

    def test_versions(self):
        self.options.platform=None
        self.options.package = None # install all
        autobuild_tool_install.AutobuildTool().run(self.options)

        self.options.versions = True
        with CaptureStdout() as stream:
            autobuild_tool_install.AutobuildTool().run(self.options)
        self.assertEqual(stream.getvalue(), "bogus: 1\n")

# -------------------------------------  -------------------------------------
class TestInstallCachedBZ2Archive(BaseTest):
    def setup_method(self, method):
        super(TestInstallCachedBZ2Archive, self).setup_method(method)
        self.pkg = "bogus"
        # make sure that the archive is not in the server
        clean_file(os.path.join(SERVER_DIR, "bogus-0.1-common-111.tar.bz2"))
        assert not os.path.exists(in_dir(SERVER_DIR, "bogus-0.1-common-111.tar.bz2"))
        self.cache_name = in_dir(common.get_install_cache_dir(), "bogus-0.1-common-111.tar.bz2")

        # Instead copy directly to cache dir.
        self.copyto(os.path.join(mydir, "data", "bogus-0.1-common-111.tar.bz2"), common.get_install_cache_dir())

    def test_success(self):
        self.options.package = [self.pkg]
        autobuild_tool_install.AutobuildTool().run(self.options)
        assert os.path.exists(os.path.join(INSTALL_DIR, "lib", "bogus.lib"))
        assert os.path.exists(os.path.join(INSTALL_DIR, "include", "bogus.h"))
        with CaptureStdout() as stream:
            self.options.list_dirty=True
            autobuild_tool_install.AutobuildTool().run(self.options)
        self.assertEqual(stream.getvalue(), 'Dirty Packages: \n')

# -------------------------------------  -------------------------------------
class TestInstallCachedGZArchive(BaseTest):
    def setup_method(self, method):
        super(TestInstallCachedGZArchive, self).setup_method(method)
        self.pkg = "bogus"
        # make sure that the archive is not in the server
        clean_file(os.path.join(SERVER_DIR, "bogus-0.1-common-111.tar.gz"))
        assert not os.path.exists(in_dir(SERVER_DIR, "bogus-0.1-common-111.tar.gz"))
        self.cache_name = in_dir(common.get_install_cache_dir(), "bogus-0.1-common-111.tar.gz")

        # Instead copy directly to cache dir.
        self.copyto(os.path.join(mydir, "data", "bogus-0.1-common-111.tar.gz"), common.get_install_cache_dir())

    def test_success(self):
        self.options.package = [self.pkg]
        autobuild_tool_install.AutobuildTool().run(self.options)
        assert os.path.exists(os.path.join(INSTALL_DIR, "lib", "bogus.lib"))
        assert os.path.exists(os.path.join(INSTALL_DIR, "include", "bogus.h"))
        with CaptureStdout() as stream:
            self.options.list_dirty=True
            autobuild_tool_install.AutobuildTool().run(self.options)
        self.assertEqual(stream.getvalue(), 'Dirty Packages: \n')

# -------------------------------------  -------------------------------------
class TestInstallCachedXZArchive(BaseTest):
    def setup_method(self, method):
        super(TestInstallCachedXZArchive, self).setup_method(method)
        self.pkg = "bogus"
        # make sure that the archive is not in the server
        clean_file(os.path.join(SERVER_DIR, "bogus-0.1-common-111.tar.xz"))
        assert not os.path.exists(in_dir(SERVER_DIR, "bogus-0.1-common-111.tar.xz"))
        self.cache_name = in_dir(common.get_install_cache_dir(), "bogus-0.1-common-111.tar.xz")

        # Instead copy directly to cache dir.
        self.copyto(os.path.join(mydir, "data", "bogus-0.1-common-111.tar.xz"), common.get_install_cache_dir())

    def test_success(self):
        self.options.package = [self.pkg]
        autobuild_tool_install.AutobuildTool().run(self.options)
        assert os.path.exists(os.path.join(INSTALL_DIR, "lib", "bogus.lib"))
        assert os.path.exists(os.path.join(INSTALL_DIR, "include", "bogus.h"))
        with CaptureStdout() as stream:
            self.options.list_dirty=True
            autobuild_tool_install.AutobuildTool().run(self.options)
        self.assertEqual(stream.getvalue(), 'Dirty Packages: \n')

# -------------------------------------  -------------------------------------
class TestInstallCachedZSTArchive(BaseTest):
    def setup_method(self, method):
        super(TestInstallCachedZSTArchive, self).setup_method(method)
        self.pkg = "bogus"
        # make sure that the archive is not in the server
        clean_file(os.path.join(SERVER_DIR, "bogus-0.1-common-111.tar.zst"))
        assert not os.path.exists(in_dir(SERVER_DIR, "bogus-0.1-common-111.tar.zst"))
        self.cache_name = in_dir(common.get_install_cache_dir(), "bogus-0.1-common-111.tar.zst")

        # Instead copy directly to cache dir.
        self.copyto(os.path.join(mydir, "data", "bogus-0.1-common-111.tar.zst"), common.get_install_cache_dir())

    def test_success(self):
        self.options.package = [self.pkg]
        autobuild_tool_install.AutobuildTool().run(self.options)
        assert os.path.exists(os.path.join(INSTALL_DIR, "lib", "bogus.lib"))
        assert os.path.exists(os.path.join(INSTALL_DIR, "include", "bogus.h"))
        with CaptureStdout() as stream:
            self.options.list_dirty=True
            autobuild_tool_install.AutobuildTool().run(self.options)
        self.assertEqual(stream.getvalue(), 'Dirty Packages: \n')

# -------------------------------------  -------------------------------------
class TestInstallCachedZIPArchive(BaseTest):
    def setup_method(self, method):
        super(TestInstallCachedZIPArchive, self).setup_method(method)
        self.pkg = "bogus"
        # make sure that the archive is not in the server
        clean_file(os.path.join(SERVER_DIR, "bogus-0.1-common-111.zip"))
        assert not os.path.exists(in_dir(SERVER_DIR, "bogus-0.1-common-111.zip"))
        self.cache_name = in_dir(common.get_install_cache_dir(), "bogus-0.1-common-111.zip")

        # Instead copy directly to cache dir.
        self.copyto(os.path.join(mydir, "data", "bogus-0.1-common-111.zip"), common.get_install_cache_dir())

    def test_success(self):
        self.options.package = [self.pkg]
        autobuild_tool_install.AutobuildTool().run(self.options)
        assert os.path.exists(os.path.join(INSTALL_DIR, "lib", "bogus.lib"))
        assert os.path.exists(os.path.join(INSTALL_DIR, "include", "bogus.h"))
        with CaptureStdout() as stream:
            self.options.list_dirty=True
            autobuild_tool_install.AutobuildTool().run(self.options)
        self.assertEqual(stream.getvalue(), 'Dirty Packages: \n')

# -------------------------------------  -------------------------------------
class TestInstallLocalArchive(BaseTest):
    def setup_method(self, method):
        super(TestInstallLocalArchive, self).setup_method(method)
        self.pkg = "bogus"
        target_archive="bogus-0.1-common-111.tar.bz2"
        # Make sure the archive isn't in either the server directory or cache:
        clean_file(in_dir(SERVER_DIR, "bogus-0.1-common-111.tar.bz2"))
        clean_file(in_dir(common.get_install_cache_dir(), "bogus-0.1-common-111.tar.bz2"))
        assert not os.path.exists(in_dir(SERVER_DIR, target_archive))
        assert not os.path.exists(in_dir(common.get_install_cache_dir(), target_archive))

    def test_success(self):
        self.options.local_archives=[os.path.join(mydir, "data", "bogus-0.1-common-111.tar.bz2")]
        self.options.package=["bogus"]
        assert not os.path.exists(os.path.join(INSTALL_DIR, "lib", "bogus.lib"))
        assert not os.path.exists(os.path.join(INSTALL_DIR, "include", "bogus.h"))
        autobuild_tool_install.AutobuildTool().run(self.options)
        assert os.path.exists(os.path.join(INSTALL_DIR, "lib", "bogus.lib"))
        assert os.path.exists(os.path.join(INSTALL_DIR, "include", "bogus.h"))
        with CaptureStdout() as stream:
            self.options.list_dirty=True
            autobuild_tool_install.AutobuildTool().run(self.options)
        self.assertEqual(stream.getvalue(), 'Dirty Packages: bogus\n')

    def test_only_local(self):
        self.options.local_archives=[os.path.join(mydir, "data", "bogus-0.1-common-111.tar.bz2")]
        self.options.package=[]
        assert not os.path.exists(os.path.join(INSTALL_DIR, "lib", "bogus.lib"))
        assert not os.path.exists(os.path.join(INSTALL_DIR, "include", "bogus.h"))
        autobuild_tool_install.AutobuildTool().run(self.options)
        assert os.path.exists(os.path.join(INSTALL_DIR, "lib", "bogus.lib"))
        assert os.path.exists(os.path.join(INSTALL_DIR, "include", "bogus.h"))
        # when a local package is specified without any package names,
        # the usual rules that not specifying packages means install all
        # should not happen
        assert not os.path.exists(os.path.join(self.options.select_dir, "LICENSES", "argparse.txt"))


# -------------------------------------  -------------------------------------
class TestDownloadFail(BaseTest):
    def setup_method(self, method):
        super(TestDownloadFail, self).setup_method(method)
        self.pkg = "notthere"
        clean_file(os.path.join(SERVER_DIR, "bogus-0.1-common-111.tar.bz2"))
        self.cache_name = in_dir(common.get_install_cache_dir(), "bogus-0.1-common-111.tar.bz2")
        clean_file(self.cache_name)

    def test_bad(self):
        self.options=FakeOptions(install_filename=self.localizedConfig("packages-failures.xml"),package=["notthere"])
        with ExpectError("Failed to download", "expected for download failure"):
            autobuild_tool_install.AutobuildTool().run(self.options)

# -------------------------------------  -------------------------------------
class TestGarbledDownload(BaseTest):
    def setup_method(self, method):
        super(TestGarbledDownload, self).setup_method(method)
        self.cache_name = in_dir(common.get_install_cache_dir(), "bogus-0.1-common-111.tar.bz2")
        assert not os.path.exists(self.cache_name)

    def test_bad(self):
        self.options=FakeOptions(install_filename=self.localizedConfig("packages-failures.xml"),package=["badhash"])
        with ExpectError("Failed to download", "expected InstallError for md5 mismatch"):
            autobuild_tool_install.AutobuildTool().run(self.options)
        assert not os.path.exists(self.cache_name)

# -------------------------------------  -------------------------------------
class TestUninstallArchive(BaseTest):
    def setup_method(self, method):
        super(TestUninstallArchive, self).setup_method(method)
        # Preliminary setup just like TestInstallArchive
        self.pkg = "bogus"
        self.options.package=[self.pkg]
        # but for uninstall testing, part of setup() is to install.
        # TestInstallArchive verifies that this part works.
        autobuild_tool_install.AutobuildTool().run(self.options)
        assert os.path.exists(os.path.join(INSTALL_DIR, "lib", "bogus.lib"))
        assert os.path.exists(os.path.join(INSTALL_DIR, "include", "bogus.h"))

    def test_success(self):
        autobuild_tool_uninstall.AutobuildTool().run(self.options)
        assert not os.path.exists(os.path.join(INSTALL_DIR, "lib", "bogus.lib"))
        assert not os.path.exists(os.path.join(INSTALL_DIR, "include", "bogus.h"))
        # Did the uninstall in fact clean up the subdirectories?
        assert not os.path.exists(os.path.join(INSTALL_DIR, "lib"))
        assert not os.path.exists(os.path.join(INSTALL_DIR, "include"))
        # Did it uninstall the license file?
        assert not os.path.exists(os.path.join(INSTALL_DIR, "LICENSES", "bogus.txt"))

        # Trying to uninstall a not-installed package is a no-op.
        autobuild_tool_uninstall.AutobuildTool().run(self.options)

    def test_unknown(self):
        # Trying to uninstall an unknown package is a no-op. uninstall() only
        # checks installed-packages.xml; it doesn't even use autobuild.xml.
        self.options=FakeOptions(install_filename=self.localizedConfig("packages-failures.xml"),package=["no_such_package"])
        autobuild_tool_uninstall.AutobuildTool().run(self.options)

# -------------------------------------  -------------------------------------
class TestInstall(BaseTest):
    def test_install_all(self):
        # Use all default options
        self.options.package = None
        autobuild_tool_install.AutobuildTool().run(self.options)
        assert os.path.exists(os.path.join(self.options.select_dir, "LICENSES"))
        assert os.path.exists(os.path.join(self.options.select_dir, "LICENSES", "argparse.txt"))
        assert os.path.exists(os.path.join(self.options.select_dir, "LICENSES", "bogus.txt"))
        assert os.path.exists(os.path.join(self.options.select_dir, "lib", "bogus.lib"))
        assert os.path.exists(os.path.join(self.options.select_dir, "include", "bogus.h"))
        assert os.path.exists(os.path.join(self.options.select_dir, "lib","python2.5","argparse.py"))
        # list installed archives
        with CaptureStdout() as stream:
            self.options.list_archives=True
            autobuild_tool_install.AutobuildTool().run(self.options)
        self.assertEqual(set_from_stream(stream), set(("argparse", "bogus")))

# -------------------------------------  -------------------------------------
class TestDownloadPackage(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_download(self, mock_urlopen: MagicMock):
        mock_urlopen.return_value = None
        with envvar("AUTOBUILD_GITHUB_TOKEN", None):
            autobuild_tool_install.download_package("https://example.org/foo.tar.bz2")
            mock_urlopen.assert_called()
            got_req = mock_urlopen.mock_calls[0].args[0]
            self.assertIsNone(got_req.unredirected_hdrs.get("Authorization"))

    @patch("urllib.request.urlopen")
    def test_download_github(self, mock_urlopen: MagicMock):
        mock_urlopen.return_value = None
        with envvar("AUTOBUILD_GITHUB_TOKEN", "token-123"):
            autobuild_tool_install.download_package("https://example.org/foo.tar.bz2", creds="github")
            mock_urlopen.assert_called()
            got_req = mock_urlopen.mock_calls[0].args[0]
            self.assertEqual(got_req.unredirected_hdrs["Authorization"], "Bearer token-123")
            self.assertEqual(got_req.unredirected_hdrs["Accept"], "application/octet-stream")

    @patch("urllib.request.urlopen")
    def test_download_gitlab(self, mock_urlopen: MagicMock):
        mock_urlopen.return_value = None
        with envvar("AUTOBUILD_GITLAB_TOKEN", "token-123"):
            autobuild_tool_install.download_package("https://example.org/foo.tar.bz2", creds="gitlab")
            mock_urlopen.assert_called()
            got_req = mock_urlopen.mock_calls[0].args[0]
            self.assertEqual(got_req.unredirected_hdrs["Authorization"], "Bearer token-123")

    @patch("urllib.request.urlopen")
    def test_download_github_without_creds(self, mock_urlopen: MagicMock):
        mock_urlopen.return_value = None
        with envvar("AUTOBUILD_GITHUB_TOKEN", None):
            with self.assertRaises(CredentialsNotFoundError):
                autobuild_tool_install.download_package("https://example.org/foo.tar.bz2", creds="github")
