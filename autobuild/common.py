"""\
@file common.py
@author Martin Reddy
@date 2010-04-13
@brief Low-level autobuild functionality common to all modules.

This module should never depend on any other autobuild module.

$LicenseInfo:firstyear=2007&license=mit$

Copyright (c) 2007-2009, Linden Research, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
$/LicenseInfo$
"""

import os
import sys
import shutil
import tarfile
import tempfile
import urllib2

# define the supported platforms
PLATFORM_DARWIN  = 'darwin'
PLATFORM_WINDOWS = 'windows'
PLATFORM_LINUX   = 'linux'
PLATFORM_SOLARIS = 'solaris'
PLATFORM_UNKNOWN = 'unknown'

class Options:
    """
    A class to capture all autobuild run-time options.
    """
    scp_cmd = "scp"
    s3_url = "http://s3.amazonaws.com/viewer-source-downloads/install_pkgs"
    install_cache_dir = None

    def getSCPCommand(self):
        """
        Return the full path to the scp command
        """
        return Options.scp_cmd

    def getInstallCacheDir(self):
        """
        In general, the installable files do not change much, so find a 
        host/user specific location to cache files.
        """
        if not Options.install_cache_dir:
            Options.install_cache_dir = getTempDir("install.cache")
        return Options.install_cache_dir

    def getS3Url(self):
        """
        Return the base URL for Amazon S3 package locations.
        """
        return Options.s3_url

def getCurrentPlatform():
    """
    Return appropriate the autobuild name for the current platform.
    """
    platform_map = {
        'darwin': PLATFORM_DARWIN,
        'linux2': PLATFORM_LINUX,
        'win32' : PLATFORM_WINDOWS,
        'cygwin' : PLATFORM_WINDOWS,
        'solaris' : PLATFORM_SOLARIS
        }
    return platform_map.get(sys.platform, PLATFORM_UNKNOWN)

def getCurrentUser():
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
        namelen = ctypes.c_int(len(name)) # len in chars, NOT bytes
        if not ctypes.windll.advapi32.GetUserNameW(name, ctypes.byref(namelen)):
            raise ctypes.WinError()
        return name.value



def getTempDir(basename):
    """
    Return a temporary directory on the user's machine, uniquified
    with the specified basename string. You may assume that the
    directory exists.
    """
    user = getCurrentUser()
    if getCurrentPlatform() == PLATFORM_WINDOWS:
        installdir = '%s.%s' % (basename, user)
        tmpdir = os.path.join(tempfile.gettempdir(), installdir)
    else:
        tmpdir = "/var/tmp/%s/%s" % (user, basename)
    if not os.path.exists(tmpdir):
        os.makedirs(tmpdir, mode=0755)
    return tmpdir

def isPackageInCache(package):
    """
    Return True if the specified package has already been downloaded
    to the local package cache.
    """
    filename = os.path.basename(package)
    cachename = os.path.join(Options().getInstallCacheDir(), filename)
    return os.path.exists(cachename)

def doesPackageMatchMD5(package, md5sum):
    """
    Returns True if the MD5 sum of the downloaded package archive
    matches the specified MD5 string.
    """
    try:
        from hashlib import md5      # Python 2.6
    except ImportError:
        from md5 import new as md5   # Python 2.5 and earlier

    filename = os.path.basename(package)
    cachename = os.path.join(Options().getInstallCacheDir(), filename)
    try:
        hasher = md5(file(cachename, 'rb').read())
    except:
        return False
    return hasher.hexdigest() == md5sum

def downloadPackage(package):
    """
    Download a package, specified as a URL, to the install cache.
    If the package already exists in the cache then this is a no-op.
    Returns False if there was a problem downloading the file.
    """

    # have we already downloaded this file to the cache?
    filename = os.path.basename(package)
    cachename = os.path.join(Options().getInstallCacheDir(), filename)
    if os.path.exists(cachename):
        print "Package already in cache: %s" % cachename
        return True

    # Set up the 'scp' handler
    opener = urllib2.build_opener()
    scp_or_http = __SCPOrHTTPHandler(Options().getSCPCommand())
    opener.add_handler(scp_or_http)
    urllib2.install_opener(opener)

    # Attempt to download the remote file 
    print "Downloading %s to %s" % (package, cachename)
    result = True
    try:
        file(cachename, 'wb').write(urllib2.urlopen(package).read())
    except Exception, e:
        print "Unable to download file: %s" % e
        result = False
    
    # Clean up and return True if the download succeeded
    scp_or_http.cleanup()
    return result

def extractPackage(package, install_dir):
    """
    Extract the contents of a downloaded package to the specified directory.
    Returns False if the package could not be found or extracted.
    """

    # Find the name of the package in the install cache
    filename = os.path.basename(package)
    cachename = os.path.join(Options().getInstallCacheDir(), filename)
    if not os.path.exists(cachename):
        print "Cannot extract non-existing package: %s" % cachename
        return False

    # Attempt to extract the package from the install cache
    print "Extracting %s to %s" % (cachename, install_dir)
    tar = tarfile.open(cachename, 'r')
    try:
        # try to call extractall in python 2.5. Phoenix 2008-01-28
        tar.extractall(path=install_dir)
    except AttributeError:
        # or fallback on pre-python 2.5 behavior
        __extractall(tar, path=install_dir)

    return True

######################################################################
#
#   Private module classes and functions below here.
#
######################################################################

class __SCPOrHTTPHandler(urllib2.BaseHandler):
    """
    Evil hack to allow both the build system and developers consume
    proprietary binaries.
    To use http, export the environment variable:
    INSTALL_USE_HTTP_FOR_SCP=true
    """
    def __init__(self, scp_binary):
        self._scp = scp_binary
        self._dir = None

    def scp_open(self, request):
        #scp:codex.lindenlab.com:/local/share/install_pkgs/package.tar.bz2
        remote = request.get_full_url()[4:]
        if os.getenv('INSTALL_USE_HTTP_FOR_SCP', None) == 'true':
            return self.do_http(remote)
        try:
            return self.do_scp(remote)
        except:
            self.cleanup()
            raise

    def do_http(self, remote):
        url = remote.split(':',1)
        if not url[1].startswith('/'):
            # in case it's in a homedir or something
            url.insert(1, '/')
        url.insert(0, "http://")
        url = ''.join(url)
        print "Using HTTP:",url
        return urllib2.urlopen(url)

    def do_scp(self, remote):
        if not self._dir:
            self._dir = tempfile.mkdtemp()
        local = os.path.join(self._dir, remote.split('/')[-1:][0])
        command = []
        for part in (self._scp, remote, local):
            if ' ' in part:
                # I hate shell escaping.
                part.replace('\\', '\\\\')
                part.replace('"', '\\"')
                command.append('"%s"' % part)
            else:
                command.append(part)
        #print "forking:", command
        rv = os.system(' '.join(command))
        if rv != 0:
            raise RuntimeError("Cannot fetch: %s" % remote)
        return file(local, 'rb')

    def cleanup(self):
        if self._dir:
            shutil.rmtree(self._dir)

#
# *NOTE: PULLED FROM PYTHON 2.5 tarfile.py Phoenix 2008-01-28
#
def __extractall(tar, path=".", members=None):
    """Extract all members from the archive to the current working
       directory and set owner, modification time and permissions on
       directories afterwards. `path' specifies a different directory
       to extract to. `members' is optional and must be a subset of the
       list returned by getmembers().
    """
    directories = []

    if members is None:
        members = tar

    for tarinfo in members:
        if tarinfo.isdir():
            # Extract directory with a safe mode, so that
            # all files below can be extracted as well.
            try:
                os.makedirs(os.path.join(path, tarinfo.name), 0777)
            except EnvironmentError:
                pass
            directories.append(tarinfo)
        else:
            tar.extract(tarinfo, path)

    # Reverse sort directories.
    directories.sort(lambda a, b: cmp(a.name, b.name))
    directories.reverse()

    # Set correct owner, mtime and filemode on directories.
    for tarinfo in directories:
        path = os.path.join(path, tarinfo.name)
        try:
            tar.chown(tarinfo, path)
            tar.utime(tarinfo, path)
            tar.chmod(tarinfo, path)
        except tarfile.ExtractError, e:
            if tar.errorlevel > 1:
                raise
            else:
                tar._dbg(1, "tarfile: %s" % e)

#
# Dependent package bootstrapping
#
class Boostrap:
    """
    Autobuild can depend upon a number of external python modules
    that are also distributed as autobuild packages. This Bootstrap
    class deals with downloading and installing those dependencies.
    This is needed for ConfigFile, so has to be done at this low
    level. This is why we have methods for downloading and extracting
    packages in this module.
    """

    # specify the name and md5sum for all dependent pkgs on S3
    deps = {
        'llbase': {
            'windows' : {
                'filename' : "llbase-0.2.0-windows-20100225.tar.bz2",
                'md5sum'   : "436c1abe6be73b287b8d0b29cf3cc764",
                },
            'darwin' : {
                'filename' : "llbase-0.2.0-darwin-20100225.tar.bz2",
                'md5sum'   : "9d29c1e8c1b26894a5e317ae5d1a6e30",
                },
            'linux' : {
                'filename' : "llbase-0.2.0-linux-20100225.tar.bz2",
                'md5sum'   : "a5d3edb6b43c46e9392c1c96e51cc3e7",
                },
            },
        }

    def __init__(self):
        """
        Install any dependent packages that are not already installed.
        Then import the python modules into the global namespace for
        this module. This results in the following global symbols:

        llsd - the llsd module from the llbase package
        """

        # get the directory where we keep autobuild's dependencies
        install_dir = getTempDir("autobuild")

        # add its lib/pythonX.X directory to our module search path
        python_dir = os.path.join(install_dir, "lib", "python2.5")
        if python_dir not in sys.path:
            sys.path.append(python_dir)

        # install all of our dependent packages, as needed
        platform = getCurrentPlatform()
        for name in self.deps:

            # get the package specs for this platform
            if self.deps[name].has_key(platform):
                specs = self.deps[name][platform]
            elif self.deps[name].has_key('common'):
                specs = self.deps[name]['common']
            else:
                sys.exit("No package defined for %s for %s" %
                         (name, platform))
            
            # get the url and md5 for this package dependency
            md5sum = specs['md5sum']
            url = os.path.join(Options().getS3Url(), specs['filename'])

            # download & extract the package, if not done already
            if not isPackageInCache(url):
                print "Installing package '%s'..." % name
                if downloadPackage(url):
                    if not doesPackageMatchMD5(url, md5sum):
                        sys.exit("MD5 mismatch for: %s" % url)
                    else:
                        extractPackage(url, install_dir)

        # try to import the llbase package into the global namespace
        global llsd
        try:
            from llbase import llsd
        except ImportError:
            sys.exit("Fatal Error: Could not install llbase package!")

#
# call the bootstrap code whenever this module is imported
#
Boostrap()
