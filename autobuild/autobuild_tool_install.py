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
Install files into a repository.

This autobuild sub-command will read an autobuild.xml file and install any
new or updated packages defined in that file to the install directory.
An installed-packages.xml file is also maintained in the install directory
to specify all the files that have been installed.

Author : Martin Reddy
Date   : 2010-04-19
"""

# For reference, the old indra install.py specification at:
# https://wiki.lindenlab.com/wiki/User:Phoenix/Library_Installation
# Proposed platform spec: OS[/arch[/compiler[/compiler_version]]]
# e.g., windows/i686/vs/2005 or linux/x86_64/gcc/3.3
#
# *TODO: add an 'autobuild info' command to query config file contents

import os
import sys
import errno
import pprint
import logging
import tarfile
import zipfile
import urllib2
import subprocess
import socket
import itertools

import common
import configfile
import autobuild_base
import hash_algorithms

logger = logging.getLogger('autobuild.install')
# Emitting --dry-run messages at warning() level means they're displayed in a
# default run (no log-level switches specified), but can still be suppressed
# with --quiet if need be.
dry_run_msg = logger.warning


class InstallError(common.AutobuildError):
    pass

__help = """\
This autobuild command fetches and installs package archives.

The command will read an autobuild.xml file and install any new or
updated packages defined in that file to the install directory. An
installed-packages.xml manifest file is also maintained in the install
directory to specify all the files that have been installed.

Downloaded package archives are cached on the local machine so that
they can be shared across multiple repositories and to avoid unnecessary
downloads. A new package will be downloaded if the autobuild.xml files is
updated with a new package URL or MD5 sum.

If an MD5 checksum is provided for a package in the autobuild.xml file,
this will be used to validate the downloaded package. The package will
not be installed if the MD5 sum does not match.

A package description must include the name of the license that applies to
the package. It may also contain the archive-relative path(s) to the full
text license file that is stored in the package archive. Both of these
metadata will be checked during the install process.

If no packages are specified on the command line, then the defaut
behavior is to install all known archives appropriate for the platform
specified. You can specify more than one package on the command line.

Supported platforms include: windows, darwin, linux, and a common platform
to represent a platform-independent package.
"""


def print_list(label, array):
    """
    Pretty print an array of strings with a given label prefix.
    """
    list = ""
    if array:
        array.sort()
        list = ", ".join(array)
    print "%s: %s" % (label, list)
    return True


def handle_query_args(options, config_file, installed_file):
    """
    Handle any arguments to query for package information.
    Returns True if an argument was handled.
    """
    if options.list_installed:
        return print_list("Installed", installed_file.dependencies.keys())

    if options.list_archives:
        return print_list("Packages", config_file.installables.keys())

    if options.list_licenses:
        licenses = [package.license for package in config_file.installables.itervalues()
                    if package.license]
        return print_list("Licenses", licenses)

    if options.export_manifest:
        for package in installed_file.dependencies.itervalues():
            item = pprint.pformat(package).rstrip()  # trim final newline
            sys.stdout.writelines((item, ",\n"))  # permit parsing -- bad syntax otherwise
        return True

    if options.list_dirty:
        installed = installed_file.dependencies
        dirty_pkgs = [installed[package]['package_description']['name'] for package in installed.keys()
                      if 'dirty' in  installed[package] and installed[package]['dirty']]
        return print_list("Dirty Packages", dirty_pkgs)

    return False

def get_package_in_cache(package):
    """
    Return the filename of the package in the local cache.
    The file may not actually exist.
    """
    filename = os.path.basename(package)
    return os.path.join(common.get_install_cache_dir(), filename)

def get_default_scp_command():
    """
    Return the full path to the scp command
    """
    scp = common.find_executable(['pscp', 'scp'], ['.exe'])
    return scp

def download_package(package):
    """
    Download a package, specified as a URL, to the install cache.
    If the package already exists in the cache then this is a no-op.
    Returns False if there was a problem downloading the file.
    """

    # download timeout so a download doesn't hang
    download_timeout_seconds = 120
    download_timeout_retries = 5

    # save the old timeout
    old_download_timeout = socket.getdefaulttimeout()

    # have we already downloaded this file to the cache?
    cachename = get_package_in_cache(package)
    if os.path.exists(cachename):
        logger.info("package already in cache: %s" % cachename)
        return True

    # Set up the 'scp' handler
    opener = urllib2.build_opener()
    scp_or_http = __SCPOrHTTPHandler(get_default_scp_command())
    opener.add_handler(scp_or_http)
    urllib2.install_opener(opener)

    # Attempt to download the remote file
    logger.info("downloading %s to %s" % (package, cachename))
    result = True

    #
    # Exception handling:
    # 1. Isolate any exception from the setdefaulttimeout call.
    # 2. urllib2.urlopen supposedly wraps all errors in URLErrror. Include socket.timeout just in case.
    # 3. This code is here just to implement socket timeouts. The last general exception was already here so just leave it.
    #

    socket.setdefaulttimeout(download_timeout_seconds)

    for tries in itertools.count(1):
        try:
            file(cachename, 'wb').write(urllib2.urlopen(package).read())
            break
        except (socket.timeout, urllib2.URLError), e:
            if tries >= download_timeout_retries:
                result = False
                logger.exception("  error %s from class %s downloading package: %s"
                                 % (e, e.__class__.__name__, package))
                break
            logger.info("  error %s from class %s downloading package: %s. Retrying."
                        % (e, e.__class__.__name__, package))
            continue
        except Exception, e:
            logger.exception("error %s from class %s downloading package: %s. "
                             % (e, e.__class__.__name__, package))
            result = False
            break

    socket.setdefaulttimeout(old_download_timeout)

    # Clean up and return True if the download succeeded
    scp_or_http.cleanup()
    return result

def _install_package(archive_path, install_dir, exclude=[]):
    """
    Install the archive at the provided path into the given installation directory.  Returns the
    list of files that were installed.
    """
    if not os.path.exists(archive_path):
        logger.error("cannot extract non-existing package: %s" % archive_path)
        return False
    logger.warn("extracting from %s" % os.path.basename(archive_path))
    if tarfile.is_tarfile(archive_path):
        return __extract_tar_file(archive_path, install_dir, exclude=exclude)
    elif zipfile.is_zipfile(archive_path):
        return __extract_zip_archive(archive_path, install_dir, exclude=exclude)
    else:
        logger.error("package %s is not archived in a supported format" % archive_path)
        return False


def extract_metadata_from_package(archive_path, metadata_file_name):
    """
    Get the package metadata from the archive
    """
    metadata_file = None
    if not os.path.exists(archive_path):
        logger.error("cannot extract metadata from non-existing package: %s" % archive_path)
        return False
    logger.debug("extracting metadata from %s" % os.path.basename(archive_path))
    if tarfile.is_tarfile(archive_path):
        tar = tarfile.open(archive_path, 'r')
        try:
            metadata_file = tar.extractfile(metadata_file_name)
        except KeyError, err:
            pass  # returning None will indicate that it was not there
    elif zipfile.is_zipfile(archive_path):
        try:
            zip = zipfile.ZipFile(archive_path, 'r')
            metadata_file = zip.open(metadata_file_name, 'r')
        except KeyError, err:
            pass  # returning None will indicate that it was not there
    else:
        logger.error("package %s is not archived in a supported format" % archive_path)
    return metadata_file


def remove_package(package):
    """
    Delete the downloaded package from the cache, if it exists there.
    """
    cachename = get_package_in_cache(package)
    if os.path.exists(cachename):
        os.remove(cachename)

def pre_install_license_check(packages, config_file):
    """
    Raises a runtime exception if any of the specified packages do not have a
    license property set.
    """
    for pname in packages:
        # We already cover the nonexistent-package case elsewhere. Just avoid
        # crashing if we reach this code first.
        package = config_file.installables.get(pname)
        if not package:
            continue
        license = package.license
        if not license:
            raise InstallError("no license specified for %s." % pname)


def __extract_tar_file(cachename, install_dir, exclude=[]):
    # Attempt to extract the package from the install cache
    tar = tarfile.open(cachename, 'r')
    extract = [member for member in tar.getmembers() if member.name not in exclude]
    conflicts = [member.name for member in extract 
                 if os.path.exists(os.path.join(install_dir, member.name))
                 and not os.path.isdir(os.path.join(install_dir, member.name))]
    if conflicts:
        raise common.AutobuildError("conflicting files:\n  "+'\n  '.join(conflicts))
    tar.extractall(path=install_dir, members=extract)
    return [member.name for member in extract]


def __extract_zip_archive(cachename, install_dir, exclude=[]):
    zip_archive = zipfile.ZipFile(cachename, 'r')
    extract = [member for member in zip_archive.namelist() if member not in exclude]
    conflicts = [member for member in extract 
                 if os.path.exists(os.path.join(install_dir, member))
                 and not os.path.isdir(os.path.join(install_dir, member))]
    if conflicts:
        raise common.AutobuildError("conflicting files:\n  "+'\n  '.join(conflicts))
    zip_archive.extractall(path=install_dir, members=extract)
    return extract


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
        url = remote.split(':', 1)
        if not url[1].startswith('/'):
            # in case it's in a homedir or something
            url.insert(1, '/')
        url.insert(0, "http://")
        url = ''.join(url)
        logger.info("using HTTP: " + url)
        return urllib2.urlopen(url)

    def do_scp(self, remote):
        if not self._dir:
            self._dir = tempfile.mkdtemp()
        local = os.path.join(self._dir, remote.split('/')[-1])
        if not self._scp:
            raise common.AutobuildError("no scp command available; cannot fetch %s" % remote)
        command = (self._scp, remote, local)
        logger.info("using SCP: " + remote)
        rv = subprocess.call(command)
        if rv != 0:
            raise common.AutobuildError("cannot fetch %s" % remote)
        return file(local, 'rb')

    def cleanup(self):
        if self._dir:
            shutil.rmtree(self._dir)

def post_install_license_check(packages, config_file, installed_file):
    """
    Raises a runtime exception if the license_file property for any of
    the specified packages does not refer to a valid file in the
    extracted archive, or does not specify an http:// URL to the
    license description.
    """
    for pname in packages:
        package = config_file.installables[pname]
        license_file = package.license_file
        # if a URL is given, assuming it's valid for now
        if license_file.startswith('http://'):
            continue
        # otherwise, assert that the license file is in the archive
        if not os.path.exists(os.path.join(installed_file.dependencies[package.name].install_dir,
                                           license_file)):
            raise InstallError("nonexistent license_file for %s: %s" % (pname, license_file))


def do_install(packages, config_file, installed_file, platform, install_dir, dry_run, local_archives=[]):
    """
    Install the specified list of packages. By default this will download the
    packages to the local cache, extract the contents of those
    archives to the install dir, and update the installed_file config.  
    For packages listed in the local_archives, the local archive will be
    installed in place of the configured one.
    """
    # Decide whether to install a local package or download a tarball
    installed_pkgs = []
    for pname in packages:
        try:
            package = config_file.installables[pname]
        except KeyError:
            # raise error if named package doesn't exist in autobuild.xml
            raise InstallError('unknown package: %s' % pname)

        logger.warn("checking package %s" % pname)
        
        # Existing tarball install, or new package install of either kind
        if pname in local_archives:
            if _install_local(platform, package, local_archives[pname], install_dir, installed_file, dry_run):
                installed_pkgs.append(pname)
        else:
            if _install_binary(package, platform, config_file, install_dir, installed_file, dry_run):
                installed_pkgs.append(pname)
    return installed_pkgs


def _install_local(platform, package, package_path, install_dir, installed_file, dry_run):
    logger.warn("installing %s from local archive" % package.name)
    metadata, files = _install_common(platform, package, package_path, install_dir, installed_file, dry_run)

    if metadata:
        installed_package = package.copy()
        if platform not in package.platforms:
            installed_platform = configfile.PlatformDescription(dict(name=platform))
        else:
            installed_platform = installed_package.get_platform(platform)
        if installed_platform.archive is None:
            installed_platform.archive = configfile.ArchiveDescription()
        installed_platform.archive.url = "file://" + os.path.abspath(package_path)
        installed_platform.archive.hash = common.compute_md5(package_path)
        metadata.install_type = 'local'
        metadata.dirty = True
        logger.warning("Using --local install flags any resulting package as 'dirty'")
        _update_installed_package_files(metadata, installed_package,
                                        platform=platform, installed_file=installed_file,
                                        install_dir=install_dir, files=files)
        return True
    else:
        return False

def _install_binary(package, platform, config_file, install_dir, installed_file, dry_run):
    # Check that we have a platform-specific or common url to use.
    req_plat = package.get_platform(platform)
    package_name = getattr(package, 'name', '(undefined)')
    if not req_plat:
        logger.warning("package %s has no installation information configured for platform %s"
                       % (package_name, platform))
        return False
    archive = req_plat.archive
    if not archive:
        raise InstallError("no archive specified for package %s for platform %s" %
                           (package_name, platform))
    if not archive.url:
        raise InstallError("no url specified for package %s for platform %s" % (package_name, platform))
    # Is this package already installed?
    installed = installed_file.dependencies.get(package.name)
    ##TBD inst_plat = installed and installed.get_platform(platform)
    ##TBD inst_archive = inst_plat and inst_plat.archive
    # Rely on ArchiveDescription's equality-comparison method to discover
    # whether the installed ArchiveDescription matches the requested one. This
    # test also handles the case when inst_plat.archive is None (not yet
    # installed).
    if installed:
        if installed['install_type'] == 'local':
            logger.warn("""skipping %s package because it was installed locally from %s
  To allow new installation, run 
  autobuild uninstall %s""" % (package_name, installed['archive']['url'], package_name))
            return
        elif installed['archive'] == archive:
            logger.debug("%s is already installed")
            return
        # otherwise, fall down to below and it will be uninstalled
    
    # compute the cache name for this package from its url
    cachefile = get_package_in_cache(archive.url)

    # download the package, if it's not already in our cache
    download_required = False
    if os.path.exists(cachefile):
        if hash_algorithms.verify_hash(archive.hash_algorithm, cachefile, archive.hash):
            logger.debug("found in cache: " + cachefile)
        else:
            download_required = True
            remove_package(archive.url)
    else:
        download_required = True
    
    if download_required:
        # download the package to the cache
        logger.warn("downloading %s archive from %s" % (package.name, archive.url))
        if not download_package(archive.url):
            # Download failure has been observed to leave a zero-length file.
            remove_package(archive.url)
            raise InstallError("failed to download %s" % archive.url)
    
        # error out if MD5 doesn't match
        if not hash_algorithms.verify_hash(archive.hash_algorithm, cachefile, archive.hash):
            remove_package(archive.url)
            raise InstallError("download error--%s mismatch for %s" % ((archive.hash_algorithm or "md5"), cachefile))
    metadata, files = _install_common(platform, package, cachefile, install_dir, installed_file, dry_run)
    if metadata:
        installed_package = package.copy()
        if platform not in package.platforms:
            installed_platform = configfile.PlatformDescription(dict(name=platform))
        else:
            installed_platform = installed_package.get_platform(platform)
        if installed_platform.archive is None:
            installed_platform.archive = configfile.ArchiveDescription()
        metadata.install_type = 'package'
        _update_installed_package_files(metadata, package, 
                                        platform=platform, installed_file=installed_file,
                                        install_dir=install_dir, files=files)
        return True
    else:
        return False

def _install_common(platform, package, package_file, install_dir, installed_file, dry_run):
    # dry run mode = download but don't install packages
    if dry_run:
        dry_run_msg("Dry run mode: not installing %s" % package.name)
        return None, None

    # If this package has already been installed, first uninstall the older
    # version.
    uninstall(package.name, installed_file)

    metadata_file_name = configfile.PACKAGE_METADATA_FILE
    metadata_file = extract_metadata_from_package(package_file, metadata_file_name)
    if not metadata_file:
        logger.warning("WARNING: Archive '%s' does not contain metadata; build will be marked as dirty" % package_file)
        # Create a dummy metadata description for a package whose archive does not have one
        metadata = configfile.MetadataDescription()
        ignore_dir, from_name, ignore_ext = common.split_tarname(package_file)
        metadata.build_id = from_name[3]
        metadata.platform = platform
        metadata.configuration = 'unknown'
        metadata.archive = package['platforms'][platform]['archive']
        metadata.package_description = package.copy()
        metadata.package_description.version = from_name[1]
        del metadata.package_description['platforms']
        metadata.dirty = True
    else:
        metadata = configfile.MetadataDescription(stream=metadata_file)

    # Check for transitive dependency conflicts
    dependancy_conflicts = transitive_search(metadata, installed_file)
    if dependancy_conflicts:
        raise InstallError("Package '%s' not installed due to conflicts\n%s" % (package.name, dependancy_conflicts))

    # check that the install dir exists...
    if not os.path.exists(install_dir):
        logger.debug("creating " + install_dir)
        os.makedirs(install_dir)

    logger.warn("installing %s from archive" % package.name)
    # extract the files from the package
    try:
        files = _install_package(package_file, install_dir, exclude=[metadata_file_name])
    except common.AutobuildError as details:
        raise InstallError("Package '%s' attempts to install files already installed.\n%s" % (package.name, details))
    if files:
        for f in files:
            logger.debug("extracted: " + f)
    return metadata, files

TransitiveSearched = set()

def transitive_search(new_package, installed):
    TransitiveSearched.clear()
    return transitive_dependency_conflicts(new_package, installed)
    
def transitive_dependency_conflicts(new_package, installed):
    """
    Searches for new_package and each of its dependencies in the installed tree
    (checks the root of the tree and walks its dependency tree)
    """
    conflicts = ""
    logger.debug("  checking conflicts for %s in installed" % new_package['package_description']['name'])
    conflict = package_in_installed(new_package, installed)
    if conflict:
        conflicts += conflict
    else:
        TransitiveSearched.add(new_package['package_description']['name'])
        if 'dependencies' in new_package:
            logger.debug("  checking conflicts for dependencies of %s in installed" % new_package['package_description']['name'])
            for new_dependency in new_package['dependencies'].iterkeys():
                if new_dependency not in TransitiveSearched:
                    conflict = transitive_dependency_conflicts(new_package['dependencies'][new_dependency], installed)
                    if conflict:
                        conflicts += conflict
                        conflicts += "conflicts with %s dependency %s\n" \
                          % (new_package['package_description']['name'],new_package['dependencies'][new_dependency]['archive']['url'])
                    TransitiveSearched.add(new_dependency)
    return conflicts

def package_in_installed(new_package, installed):
    """
    Searches for new_package in the installed tree, returns error message (or empty string)
    (checks the root of the tree and walks the intstalled tree)
    """
    conflict = ""
    if 'dependencies' in installed:
        previous = installed['dependencies']
        for used in previous.iterkeys():
            # logger.debug("=====\npackage\n%s\nvs\n%s" % (pprint.pformat(new_package), pprint.pformat(previous[used])))
            if new_package['package_description']['name'] == used:
                if 'archive' in new_package and new_package['archive']:
                    # this is a dependency of the new package, so we have archive data
                    if new_package['archive']['url']  != previous[used]['archive']['url']:
                        conflict += "  url           %s\n" % previous[used]['archive']['url']
                    if new_package['archive']['hash'] != previous[used]['archive']['hash']:
                        conflict += "  hash          %s\n" % previous[used]['archive']['hash']
                else:
                    # this is the newly imported package, so we don't have a url for it
                    pass
                if new_package['configuration'] != previous[used]['configuration']:
                    conflict += "  configuration %s\n" % previous[used]['configuration']
                if new_package['package_description']['version'] != previous[used]['package_description']['version']:
                    conflict += "  version       %s\n" % previous[used]['package_description']['version']
                if new_package['build_id'] != previous[used]['build_id']:
                    conflict += "  build_id      %s\n" % previous[used]['build_id']
            else:
                # recurse to check the dependencies of previous[used]
                conflict += package_in_installed(new_package, previous[used])
                if conflict:
                    conflict += "    used by %s\n" % previous[used]['archive']['url']
            if conflict:
                # in order to be able to add the import path, we only detect the first conflict
                return conflict
    return ""


def _update_installed_package_files(metadata, package,
                                    platform=None, installed_file=None, install_dir=None, files=None):
    installed_package = metadata
    installed_package.install_dir = install_dir

    installed_platform = package.get_platform(platform)
    installed_package.archive = installed_platform.archive
    installed_package.manifest = files
    installed_file.dependencies[metadata.package_description.name] = installed_package


def uninstall(package_name, installed_config):
    """
    Uninstall specified package_name: remove related files and delete
    package_name from the installed_config ConfigurationDescription.

    Saving the modified installed_config is the caller's responsibility.
    """
    try:
        # Not only retrieve this package's installed PackageDescription, but
        # remove it from installed_config at the same time.
        package = configfile.MetadataDescription(parsed_llsd=installed_config.dependencies.pop(package_name))
    except KeyError:
        # If the package has never yet been installed, we're good.
        logger.debug("%s not installed, no uninstall needed" % package_name)
        return

    logger.warn("uninstalling %s" % package_name)
    # Tarballs that name directories name them before the files they contain,
    # so the unpacker will create the directory before creating files in it.
    # For exactly that reason, we must remove things in reverse order.
    directories=set() # directories we've removed files from
    for fn in package.manifest:
        install_path = os.path.join(package.install_dir, fn)
        try:
            os.remove(install_path)
            # We used to print "removing f" before the call above, the
            # assumption being that we'd either succeed or produce a
            # traceback. But there are a couple different ways we could get
            # through this logic without actually deleting. So produce a
            # message only when we're sure we've actually deleted something.
            logger.debug("    removed " + fn)
        except OSError, err:
            if err.errno == errno.ENOENT:
                # this file has already been deleted for some reason -- fine
                pass
        directories.add(os.path.dirname(fn))
    # Check to see if any of the directories from which we removed files are now 
    # empty; if so, delete them.  Do the checks in descending length order so that
    # subdirectories will appear before their containing directory.
    for dn in sorted(directories, cmp=lambda x,y: cmp(len(y),len(x))):
        dir_path = os.path.join(package.install_dir, dn)
        if not os.listdir(dir_path):
            os.rmdir(dir_path)
            logger.debug("    removed " + dn)

def install_packages(options, config_file, install_dir, args):
    logger.debug("installing to directory: " + install_dir)
    # If installed_filename is already an absolute pathname, join() is smart
    # enough to leave it alone. Therefore we can do this unconditionally.
    installed_filename = os.path.join(install_dir, options.installed_filename)

    # load the list of already installed packages
    logger.debug("loading " + installed_filename)
    installed_file = configfile.Dependencies(installed_filename)

    # handle any arguments to query for information
    if handle_query_args(options, config_file, installed_file):
        return 0

    # get the list of packages to install -- if none specified, consider all.
    packages = args or config_file.installables.keys()

    # check the license properties for the packages to install
    if not options.check_license:
        logger.warning("The --skip-license-check option is deprecated; it now has no effect")
    pre_install_license_check(packages, config_file)

    # collect any locally built archives.
    local_archives = {}
    for archive_path in options.local_archives:
        try:
            # split_tarname() returns a sequence like:
            # ("/some/path", ["boost", "1.39.0", "darwin", "20100222a"], ".tar.bz2")
            # We want just the package name, 'boost' in the example above.
            package = common.split_tarname(archive_path)[1][0]
        except IndexError:
            # But if the archive filename doesn't conform to our expectations,
            # either subscript operation above might raise IndexError.
            raise InstallError("cannot get package name from local archive " + archive_path)
        local_archives[package] = archive_path

    # do the actual install of the new/updated packages
    packages = do_install(packages, config_file, installed_file, options.platform, install_dir,
                          options.dry_run, local_archives=local_archives)

    # check the license_file properties for actually-installed packages
    if not options.check_license:
        logger.warning("The --skip-license-check option is deprecated; it now has no effect")
    if not options.dry_run:
        post_install_license_check(packages, config_file, installed_file)

    # update the installed-packages.xml file
    try:
        # in case we got this far without ever having created installed_file's
        # parent directory
        os.makedirs(os.path.dirname(installed_file.path))
    except OSError, err:
        if err.errno != errno.EEXIST:
            raise
    installed_file.save()
    return 0


# define the entry point to this autobuild tool
class AutobuildTool(autobuild_base.AutobuildBase):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description='Fetch and install package archives.')

    def register(self, parser):
        parser.description = "install artifacts of dependency packages for use during the build of the current package"
        parser.add_argument(
            'package',
            nargs='*',
            help='List of packages to consider for installation.')
        parser.add_argument(
            '--config-file',
            default=configfile.AUTOBUILD_CONFIG_FILE,
            dest='install_filename',
            help="The file used to describe what should be installed\n  (defaults to $AUTOBUILD_CONFIG_FILE or \"autobuild.xml\").")
        parser.add_argument(
            '--installed-manifest',
            default=configfile.INSTALLED_CONFIG_FILE,
            dest='installed_filename',
            help='The file used to record what is installed.')
        parser.add_argument(
            '-p', '--platform',
            default=common.get_current_platform(),
            dest='platform',
            help='Override the automatically determined platform.')
        parser.add_argument(
            '--install-dir',
            default=None,
            dest='select_dir',          # see common.select_directories()
            help='Where to unpack the installed files.')
        parser.add_argument(
            '--list',
            action='store_true',
            default=False,
            dest='list_archives',
            help="List the archives specified in the package file.")
        parser.add_argument(
            '--list-installed',
            action='store_true',
            default=False,
            dest='list_installed',
            help="List the installed package names and exit.")
        parser.add_argument(
            '--skip-license-check',
            action='store_false',
            default=True,
            dest='check_license',
            help="(deprecated - now has no effect)")
        parser.add_argument(
            '--list-licenses',
            action='store_true',
            default=False,
            dest='list_licenses',
            help="List known licenses and exit.")
        parser.add_argument(
            '--list-dirty',
            action='store_true',
            default=False,
            dest='list_dirty',
            help="List any dirty installables and exit.")
        parser.add_argument(
            '--export-manifest',
            action='store_true',
            default=False,
            dest='export_manifest',
            help="Print the install manifest to stdout and exit.")
        parser.add_argument('--local',
                            action='append',
                            dest='local_archives',
                            default=[],
                            help="Install this locally built archive in place of the configured installable.")
        parser.add_argument('--all', '-a',
                            dest='all',
                            default=False,
                            action="store_true",
                            help="install packages for all configurations")
        parser.add_argument('--configuration', '-c',
                            nargs='?',
                            action="append",
                            dest='configurations',
                            help="install packages for a specific build configuration\n(may be specified as comma separated values in $AUTOBUILD_CONFIGURATION)",
                            metavar='CONFIGURATION',
                            default=self.configurations_from_environment())

    def run(self, args):
        # load the list of packages to install
        logger.debug("loading " + args.install_filename)
        config = configfile.ConfigurationDescription(args.install_filename)

        # write packages into 'packages' subdir of build directory by default
        install_dirs = \
            common.select_directories(args, config,
                                      "install", "installing packages for",
                                      lambda cnf:
                                      os.path.join(config.make_build_directory(cnf, args.dry_run),
                                                   "packages"))

        # get the absolute paths to the install dir and installed-packages.xml file
        for install_dir in install_dirs:
            install_dir = os.path.realpath(install_dir)
            install_packages(args, config, install_dir, args.package)

if __name__ == '__main__':
    sys.exit("Please invoke this script using 'autobuild %s'" %
             AutobuildTool().get_details()["name"])
