#!/usr/bin/python
# $LicenseInfo:firstyear=2010&license=mit$
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

"""
Low-level autobuild functionality common to all modules.

Any code that is potentially common to all autobuild sub-commands
should live in this module. This module should never depend on any
other autobuild module.

Importing this module will also guarantee that certain dependencies
are available, such as llbase

Author : Martin Reddy
Date   : 2010-04-13
"""

import os
import sys
import time
import itertools
import logging
import platform
import pprint
import shutil
import tempfile
import argparse

from version import AUTOBUILD_VERSION_STRING

logger = logging.getLogger('autobuild.common')


class AutobuildError(RuntimeError):
    pass

# define the supported platforms
PLATFORM_DARWIN    = 'darwin'
PLATFORM_DARWIN64  = 'darwin64'
PLATFORM_WINDOWS   = 'windows'
PLATFORM_WINDOWS64 = 'windows64'
PLATFORM_LINUX     = 'linux'
PLATFORM_LINUX64   = 'linux64'
PLATFORM_COMMON    = 'common'

DEFAULT_ADDRSIZE = 32

# Similarly, if we have an explicit platform in the environment, keep it. We
# used to query os.environ in establish_platform(), instead of up here. The
# trouble was that establish_platform() *sets* these os.environ entries -- so
# if the code made two different calls to establish_platform(), even if the
# second call had better information (from command-specific switches), the
# second call would notice the AUTOBUILD_PLATFORM[_OVERRIDE] variables already
# set by the first call and set the wrong thing. Capturing those variables
# here at load time lets each establish_platform() call make its decisions
# independently of any previous calls.
_AUTOBUILD_PLATFORM_OVERRIDE = os.environ.get('AUTOBUILD_PLATFORM_OVERRIDE')
_AUTOBUILD_PLATFORM          = os.environ.get('AUTOBUILD_PLATFORM')

Platform=None
def get_current_platform():
    """
    Return appropriate the autobuild name for the current platform.
    """
    global Platform
    if Platform is None:
        logger.debug("platform recurse")
        establish_platform(None) # uses the default for where we are running to set Platform
    return Platform

_build_dir=None
def establish_build_dir(directory):
    global _build_dir
    logger.debug("Establishing build dir as '%s'" % directory)
    _build_dir = directory

def get_current_build_dir():
    """
    Return the absolute path for the current build directory
    """
    global _build_dir
    if _build_dir is None:
        raise AutobuildError("No build directory established")
    return _build_dir

def build_dir_relative_path(path):
    """
    Returns a relative path derived from the input path rooted at the configuration file's
    directory when the input is an absolute path.
    """
    outpath=path
    if os.path.isabs(path):
        # ensure that there is a trailing os.pathsep
        # so that when this prefix is stripped below to make the
        # path relative, we don't start with os.pathsep
        build_dir=os.path.join(get_current_build_dir(),"")
        logger.debug("path '%s' build_dir '%s'" % (path, build_dir))
        if path.startswith(build_dir):
            outpath=path[len(build_dir):]
    return outpath

def is_system_64bit():
    """
    Returns True if the build system is 64-bit compatible.
    """
    return platform.machine().lower() in ("x86_64", "amd64")

def is_system_windows():
    # Note that Python has a commitment to the value "win32" even for 64-bit
    # Windows: http://stackoverflow.com/a/2145582/5533635
    return sys.platform == 'win32' or sys.platform == 'cygwin'

def check_platform_system_match(platform):
    """
    Confirm that the selected platform is compatibile with the system we're on
    """
    platform_should_be=None
    if platform in (PLATFORM_WINDOWS, PLATFORM_WINDOWS64):
        if not is_system_windows():
            platform_should_be="Windows"
    elif platform in (PLATFORM_LINUX, PLATFORM_LINUX64):
        if sys.platform != 'linux2':
            platform_should_be="Linux"
    elif platform in (PLATFORM_DARWIN, PLATFORM_DARWIN64):
        if sys.platform != 'darwin':
            platform_should_be="Mac OS X"
    elif platform != PLATFORM_COMMON:
        raise AutobuildError("Unsupported platform '%s'" % platform)

    if platform_should_be:
        raise AutobuildError("Platform '%s' is only supported running on %s" % (platform, platform_should_be))

def establish_platform(specified_platform=None, addrsize=DEFAULT_ADDRSIZE):
    """
    Select the appropriate the autobuild name for the platform.
    """
    global Platform
    specified_addrsize=addrsize
    if addrsize == 64 and not is_system_64bit():
        logger.warning("This system is not 64 bit capable; using 32 bit address size")
        addrsize = 32
    if specified_platform is not None:
        Platform=specified_platform
    elif _AUTOBUILD_PLATFORM_OVERRIDE:
        Platform=_AUTOBUILD_PLATFORM_OVERRIDE
    elif _AUTOBUILD_PLATFORM:
        Platform=_AUTOBUILD_PLATFORM
    elif sys.platform == 'darwin':
        if addrsize == 64:
            Platform = PLATFORM_DARWIN64
        else:
            Platform = PLATFORM_DARWIN
    elif sys.platform == 'linux2':
        if addrsize == 64:
            Platform = PLATFORM_LINUX64
        else:
            Platform = PLATFORM_LINUX
    elif is_system_windows():  
        if addrsize == 64:
            Platform = PLATFORM_WINDOWS64
        else:
            Platform = PLATFORM_WINDOWS
    else:
        AutobuildError("unrecognized platform '%s'" % sys.platform)

    check_platform_system_match(Platform)

    os.environ['AUTOBUILD_ADDRSIZE'] = str(addrsize) # for spawned commands
    os.environ['AUTOBUILD_PLATFORM'] = Platform # for spawned commands
    os.environ['AUTOBUILD_PLATFORM_OVERRIDE'] = Platform # for recursive invocations

    logger.debug("Specified platform %s address-size %d: result %s" \
                 % (specified_platform, specified_addrsize, Platform))
    
    return Platform

def get_version_tuple(version_string):
    try:
        return tuple(int(v) for v in version_string.split('.'))
    except (AttributeError, ValueError) as err:
        # version_string might not have a split() method: might not be str.
        # One or more components might not be int values.
        logger.debug("Can't parse version string %r: %s" % (version_string, err))
        # Treat any unparseable version as "very old"
        return (0,)

def get_current_user():
    """
    Get the login name for the current user.
    """
    try:
        # Unix-only.
        import getpass
        return getpass.getuser()
    except ImportError:
        import ctypes
        MAX_PATH = 260                  # according to a recent WinDef.h
        name = ctypes.create_unicode_buffer(MAX_PATH)
        namelen = ctypes.c_int(len(name))  # len in chars, NOT bytes
        if not ctypes.windll.advapi32.GetUserNameW(name, ctypes.byref(namelen)):
            raise ctypes.WinError()
        return name.value


def get_autobuild_environment():
    """
    Return an environment under which to execute autobuild subprocesses.
    """
    return dict(os.environ, AUTOBUILD=os.environ.get(
        'AUTOBUILD', get_autobuild_executable_path()))


def get_install_cache_dir():
    """
    In general, the package archives do not change much, so find a 
    host/user specific location to cache files.
    """
    cache = os.getenv('AUTOBUILD_INSTALLABLE_CACHE')
    if cache is None:
        cache = get_temp_dir("install.cache")
    else:
        if not os.path.exists(cache):
            os.makedirs(cache, mode=0755)
    return cache


def get_temp_dir(basename):
    """
    Return a temporary directory on the user's machine, uniquified
    with the specified basename string. You may assume that the
    directory exists.
    """
    user = get_current_user()
    if is_system_windows():
        installdir = '%s.%s' % (basename, user)
        tmpdir = os.path.join(tempfile.gettempdir(), installdir)
    else:
        tmpdir = "/var/tmp/%s/%s" % (user, basename)
    if not os.path.exists(tmpdir):
        os.makedirs(tmpdir, mode=0755)
    return tmpdir


def get_autobuild_executable_path():
    if not is_system_windows():
        # Anywhere but Windows, the AUTOBUILD executable should be the first
        # item on our command line.
        path = sys.argv[0]
    else:
        # "then there's Windows..."
        # pip's approach to creating a Windows 'autobuild' command that
        # invokes a particular function in a particular Python module has
        # changed over the years. pip used to create an autobuild.cmd batch
        # file; now it creates an actual autobuild.exe that invokes the Python
        # interpreter on a generated autobuild-script.py script -- so what
        # shows up in sys.argv[0] is /path/to/autobuild-script.py.
        # Unfortunately, despite the presence of a shbang in that script file,
        # since .py is not usually a recognized Windows command extension, we
        # can't just use that script name to run child autobuild commands.
        # That's the point: we call this function not to find the actual file
        # that was run, but to get a command path with which we can invoke
        # nested autobuild commands. We can do that by saying: regardless of
        # the actual filename identified in sys.argv[0], we can re-invoke
        # autobuild by running the command 'autobuild' in that directory. That
        # should work for either autobuild.cmd or autobuild.exe.
        path = os.path.join(os.path.dirname(sys.argv[0]), "autobuild")
    return os.path.realpath(os.path.abspath(path))


def find_executable(executables, exts=None, path=None):
    """
    Given an executable name, or a list of executable names, return the
    name of the executable that can be found in the path. The names can
    have wildcards in them.

    exts can accept a list of extensions to search (e.g. [".exe", ".com"]).
    The empty extension (exact match for one of the names in executables) is
    always implied, but it's checked last.

    You can force find_executable() to consider only an exact match for one of
    the specified executables by passing exts=[].

    However, if exts is omitted (or, equivalently, None), the default is
    platform-sensitive. On Windows, find_executable() will look for some of
    the usual suspects (a subset of a typical PATHEXT value). On non-Windows
    platforms, the default is []. This allows us to place an extensionless
    script file 'foo' for most platforms, plus a 'foo.cmd' beside it for use
    on Windows.

    path should either be None (search os.environ['PATH']) or a sequence of
    directory names to be searched in order.
    """
    if isinstance(executables, basestring):
        executables = [executables]
    if exts is None:
        exts = sys.platform.startswith("win") and [".com", ".exe", ".bat", ".cmd"] or []
    if path is None:
        path=os.environ.get('PATH', '').split(os.pathsep)
    # The original implementation iterated over directories in PATH, checking
    # for each name in 'executables' in a given directory. This makes
    # intuitive sense -- but it's wrong. When 'executables' is (e.g.) ['foobar',
    # 'foo'] it means that if foobar exists on this platform, we need to
    # prioritize that over plain 'foo' -- even if the directory containing
    # plain 'foo' comes first. So the outer loop should be over 'executables'.
    for e in executables:
        for p in path:
            for ext in itertools.chain(exts, [""]):
                candidate = os.path.join(p, e + ext)
                if os.path.isfile(candidate):
                    return candidate
    return None


def compute_md5(path):
    """
    Returns the MD5 sum for the given file.
    """
    try:
        from hashlib import md5      # Python 2.6
    except ImportError:
        from md5 import new as md5   # Python 2.5 and earlier

    try:
        stream = open(path, 'rb')
    except IOError, err:
        raise AutobuildError("Can't compute MD5 for %s: %s" % (path, err))

    try:
        hasher = md5(stream.read())
    finally:
        stream.close()

    return hasher.hexdigest()


def split_tarname(pathname):
    """
    Given a tarfile pathname of the form:
    "/some/path/boost-1.39.0-darwin-20100222a.tar.bz2"
    return the following:
    ("/some/path", ["boost", "1.39.0", "darwin", "20100222a"], ".tar.bz2")
    """
    # Split off the directory name from the unqualified filename.
    dir, filename = os.path.split(pathname)
    # dir = "/some/path"
    # filename = "boost-1.39.0-darwin-20100222a.tar.bz2"
    # Conceptually we want to split off the extension at this point. It would
    # be great to use os.path.splitext(). Unfortunately, at least as of Python
    # 2.5, os.path.splitext("woof.tar.bz2") returns ('woof.tar', '.bz2') --
    # not what we want. Instead, we'll have to split on '.'. But as the
    # docstring example points out, doing that too early would confuse things,
    # as there are dot characters in the embedded version number. So we have
    # to split on '-' FIRST.
    fileparts = filename.split('-')
    # fileparts = ["boost", "1.39.0", "darwin", "20100222a.tar.bz2"]
    # Almost there -- we just have to lop off the extension. NOW split on '.'.
    # We know there's at least fileparts[-1] because splitting a string with
    # no '-' -- even the empty string -- produces a list containing the
    # original string.
    extparts = fileparts[-1].split('.')
    # extparts = ["20100222a", "tar", "bz2"]
    # Replace the last entry in fileparts with the first part of extparts.
    fileparts[-1] = extparts[0]
    # Now fileparts = ["boost", "1.39.0", "darwin", "20100222a"] as desired.
    # Reconstruct the extension. To preserve the leading '.', don't just
    # delete extparts[0], replace it with the empty string. Yes, this does
    # assume that split() returns a list.
    extparts[0] = ""
    ext = '.'.join(extparts)
    # One more funky case. We've encountered "version numbers" like
    # "2009-08-30", "1-0" or "1.2-alpha". This would produce too many
    # fileparts, e.g. ["boost", "2009", "08", "30", "darwin", "20100222a"].
    # Detect that and recombine.
    if len(fileparts) > 4:
        fileparts[1:-2] = ['-'.join(fileparts[1:-2])]
    if len(fileparts) < 4:
        raise AutobuildError("Incompatible archive name '%s' lacks some components" \
                             % filename)
    return dir, fileparts, ext


def search_up_for_file(path):
    """
    Search up the file tree for a file matching the base name of the path provided.

    Returns either the path to the file found or None if search fails.
    """
    path = os.path.abspath(path)
    filename = os.path.basename(path)
    dir = os.path.dirname(path)
    while not os.path.exists(os.path.join(dir, filename)):
        newdir = os.path.dirname(dir)
        if newdir == dir:
            return None
        dir = newdir
    return os.path.abspath(os.path.join(dir, filename))


class Serialized(dict, object):
    """
    A base class for serialized objects.  Regular attributes are stored in the inherited dictionary
    and will be serialized. Class variables will be handled normally and are not serialized.
    """

    def __getattr__(self, name):
        if name in self:
            return self[name]
        else:
            raise AttributeError("object has no attribute '%s'" % name)

    def __setattr__(self, name, value):
        if name in self.__class__.__dict__:
            self.__dict__[name] = value
        else:
            self[name] = value

    def copy(self):
        """
        Intercept attempts to copy like a dict, need to preserve leaf class
        instead of letting dict.copy() return a simple dict.
        """
        return self.__class__(self)


def select_directories(args, config, desc, verb, dir_from_config):
    """
    Several of our subcommands provide the ability to specify an individual
    build tree on which to operate, or the build tree for each specified
    configuration, or --all build trees. Factor out the common selection logic.

    Returns: possibly-empty list of directories on which to operate.

    Pass:

    args: from argparse. Build your argparse subcommand arguments to set at least:
        select_dir: a specific individual directory (e.g. from "--install-dir")
        all: True when --all is specified
        configurations: list of configuration names, e.g. "Debug"

    config: loaded configuration file (from "autobuild.xml")

    desc: debugging output: modifies 'directory', e.g. "install" directory

    verb: debugging output: what we're doing to configurations, e.g.
    "packaging" configurations x, y and z

    dir_from_config: callable(configuration): when deriving directories from
    build configurations (at present, unless args.select_dir is specified),
    call this to obtain the directory for the passed build configuration.
    Example: lambda cnf: config.get_build_directory(cnf, args.platform)
    """
    if args.select_dir:
        logger.debug("specified %s directory: %s" % (desc, args.select_dir))
        return [args.select_dir]

    return [dir_from_config(conf)
            for conf in select_configurations(args, config, verb)]


def select_configurations(args, config, verb):
    """
    Several of our subcommands provide the ability to specify an individual
    build configuration on which to operate, or several specified
    configurations, or --all configurations. Factor out the common selection
    logic.

    Returns: possibly-empty list of configurations on which to operate.

    Pass:

    args: from argparse. Build your argparse subcommand arguments to set at least:
        all: True when --all is specified
        configurations: list of configuration names, e.g. "Debug"

    config: loaded configuration file (from "autobuild.xml")

    verb: debugging output: what we're doing to the selected configurations, e.g.
    "packaging" configurations x, y and z
    """
    platform = get_current_platform()

    if args.all:
        configurations = config.get_all_build_configurations(platform)
    elif args.configurations:
        configurations = [config.get_build_configuration(name, platform)
                          for name in args.configurations]
    else:
        configurations = config.get_default_build_configurations(platform)
    logger.debug("common.select_configurations %s configuration(s)\n%s" % (verb, pprint.pformat(configurations)))
    return configurations


def establish_build_id(build_id_arg):
    """determine and return a build_id based on (in preference order):
       the --id argument, 
       the AUTOBUILD_BUILD_ID environment variable,
       the date/time
    If we reach the date fallback, a warning is logged
    In addition to returning the id value, this sets the AUTOBUILD_BUILD_ID environment
    variable for any descendent processes so that recursive invocations will have access
    to the same value.
    """

    build_id = None
    if build_id_arg:
        build_id = build_id_arg
    elif 'AUTOBUILD_BUILD_ID' in os.environ:
        build_id = os.environ['AUTOBUILD_BUILD_ID']
    else:
        # construct a timestamp that will fit into a signed 32 bit integer:
        #   <two digit year><three digit day of year><two digit hour><two digit minute>
        build_id = time.strftime("%y%j%H%M", time.gmtime())
        logger.warn("Warning: no --id argument or AUTOBUILD_BUILD_ID environment variable specified;\n    using a value from the UTC date and time (%s), which may not be unique" % build_id)
    os.environ['AUTOBUILD_BUILD_ID'] = build_id
    return build_id


