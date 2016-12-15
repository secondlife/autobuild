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
import codecs

import common
import configfile
import autobuild_base
import hash_algorithms
from autobuild_tool_source_environment import get_enriched_environment

logger = logging.getLogger('autobuild.install')

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
        if config_file.package_description.license is not None:
            licenses = [config_file.package_description.license]
        else:
            licenses = []
        for installed in installed_file.dependencies.itervalues():
            license = installed['package_description'].get('license')
            if license is not None and license not in licenses:
                licenses.append(license)
        return print_list("Licenses", licenses)

    if options.copyrights:
        copyrights = dict()
        def recurse_dependencies(packages, copyrights):
            if 'dependencies' in packages:
                for pkg in packages['dependencies'].iterkeys():
                    # since we prevent two versions of the same package from being installed, 
                    # we don't need to worry about two different copyrights here for the same package
                    if pkg not in copyrights:
                        if 'copyright' in packages['dependencies'][pkg]['package_description']:
                            copyrights[pkg] = packages['dependencies'][pkg]['package_description']['copyright'].strip()+'\n'
                            recurse_dependencies(packages['dependencies'][pkg], copyrights)
                        else:
                            logger.warning("Package '%s' does not specify a copyright" % pkg)
        recurse_dependencies(installed_file, copyrights)
        if 'package_description' in config_file and config_file.package_description.get('copyright') is not None:
            all_copyrights="%s" % config_file.package_description['copyright'].strip()+'\n'
        else:
            # warning already issued by configfile
            all_copyrights=""
        for pkg in sorted(copyrights):
            all_copyrights+="%s: %s" % (pkg,copyrights[pkg])
        print all_copyrights.rstrip() # the rstrip prevents two newlines on the end
        return True

    if options.versions:
        versions = dict()
        def recurse_dependencies(packages, versions):
            if 'dependencies' in packages:
                for pkg in packages['dependencies'].iterkeys():
                    # since we prevent two versions of the same package from being installed, 
                    # we don't need to worry about two different versions here for the same package
                    if pkg not in versions:
                        if 'copyright' in packages['dependencies'][pkg]['package_description']:
                            versions[pkg] = packages['dependencies'][pkg]['package_description']['version'].strip()+'\n'
                            recurse_dependencies(packages['dependencies'][pkg], versions)
                        else:
                            logger.warning("Package '%s' does not specify a version" % pkg)
        recurse_dependencies(installed_file, versions)
        all_versions=""
        for pkg in sorted(versions):
            all_versions+="%s: %s" % (pkg,versions[pkg])
        print all_versions.rstrip() # the rstrip prevents two newlines on the end
        return True

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

    if options.list_installed_urls:
        installed = installed_file.dependencies
        archives=[]
        for name, package in installed.iteritems():
            if 'url' in package['archive']:
                archives.append('%s' % package['archive']['url'])
            else:
                archives.append('%s - no url' % name)
        print '\n'.join(archives)
        return True

    if options.query_installed_file:
        print_package_for(options.query_installed_file, installed_file)
        return True
    
    return False

def print_package_for(target_file, installed_file):
    found_package=None
    for package in installed_file.dependencies.itervalues():
        if 'manifest' in package and target_file in package['manifest']:
            found_package = package
            break
            
    if found_package:
        print "file '%s' installed by package '%s'" \
        % (target_file, package['package_description']['name'])
    else:
        print "file '%s' not found in installed files" % target_file

def package_cache_path(package):
    """
    Return the filename of the package in the local cache.
    The file may not actually exist.
    """
    return os.path.join(common.get_install_cache_dir(), os.path.basename(package))

def get_package_file(package_name, package_url, hash_algorithm='md5', expected_hash=None):
    """
    Get the package file in the cache, downloading if needed.
    Validate the cache file using the hash (removing it if needed)
    Returns None if there was a problem downloading the file.
    """
    cache_file = None
    download_retries = 3
    while cache_file is None and download_retries > 0:
        cache_file = package_cache_path(package_url)
        if os.path.exists(cache_file):
            # some failures seem to leave empty cache files... delete and retry
            if os.path.getsize(cache_file) == 0:
                logger.warning("empty cache file removed")
                os.remove(cache_file)
                cache_file = None
            elif hash_algorithm is not None \
              and not hash_algorithms.verify_hash(hash_algorithm, cache_file, expected_hash):
                logger.error("corrupt cached file removed: %s mismatch" % (hash_algorithm or "md5"))
                os.remove(cache_file)
                cache_file = None
            else:
                logger.info("package in cache: %s" % cache_file)
        else:
            # download timeout so a download doesn't hang
            download_timeout_seconds = 120
            
            # Attempt to download the remote file
            logger.info("downloading %s:\n  %s\n     to %s" % (package_name, package_url, cache_file))
            try:
                package_response = urllib2.urlopen(package_url, None, download_timeout_seconds)
            except urllib2.URLError as err:
                logger.error("error: %s\n  downloading package %s" % (err, package_url))
                package_response = None
                cache_file = None

            if package_response is not None:
                with file(cache_file, 'wb') as cache:
                    max_block_size = 1024*1024 # if this is changed, also change 'MB' in progress message below
                    package_size = int(package_response.headers.get("content-length", 0))
                    package_blocks = package_size / max_block_size if package_size else 0
                    if package_blocks < (package_size * max_block_size):
                        package_blocks += 1 
                    logger.debug("response size %d blocks %d" % (package_size, package_blocks))
                    blocks_recvd = 0
                    block = package_response.read(max_block_size)
                    while block:
                        blocks_recvd += 1
                        if logger.getEffectiveLevel() <= logging.INFO:
                            # use CR and trailing comma to rewrite the same line each time for progress
                            if package_blocks:
                                print "%d MB / %d MB (%d%%)\r" % (blocks_recvd, package_blocks, int(100*blocks_recvd/package_blocks)),
                                sys.stdout.flush()
                            else:
                                print "%d\r" % blocks_recvd,
                                sys.stdout.flush()
                        cache.write(block)
                        block = package_response.read(max_block_size)
                if logger.getEffectiveLevel() <= logging.INFO:
                    print "" # get a new line following progress message
                    sys.stdout.flush()
                # some failures seem to leave empty cache files... delete and retry
                if os.path.exists(cache_file) and os.path.getsize(cache_file) == 0:
                    logger.error("failed to write cache file: %s" % cache_file)
                    os.remove(cache_file)
                    cache_file = None

        # error out if MD5 doesn't match
        if cache_file is not None \
          and hash_algorithm is not None:
            logger.info("verifying %s" % package_name)
            if not hash_algorithms.verify_hash(hash_algorithm, cache_file, expected_hash):
                logger.error("download error: %s mismatch for %s" % ((hash_algorithm or "md5"), cache_file))
                os.remove(cache_file)
                cache_file = None
        if cache_file is None:
            download_retries -= 1
            if download_retries > 0:
                logger.warning("Retrying download")

    return cache_file

def _install_package(archive_path, install_dir, exclude=[]):
    """
    Install the archive at the provided path into the given installation directory.  Returns the
    list of files that were installed.
    """
    if not os.path.exists(archive_path):
        logger.error("cannot extract non-existing package: %s" % archive_path)
        return False
    logger.info("extracting from %s" % os.path.basename(archive_path))
    sys.stdout.flush() # so that the above will appear during uncompressing very large archives
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
        logger.error("no package found at: %s" % archive_path)
    else:
        logger.debug("extracting metadata from %s" % os.path.basename(archive_path))
        if tarfile.is_tarfile(archive_path):
            tar = tarfile.open(archive_path, 'r')
            try:
                metadata_file = tar.extractfile(metadata_file_name)
            except KeyError, err:
                metadata_file = None
                pass  # returning None will indicate that it was not there
        elif zipfile.is_zipfile(archive_path):
            try:
                zip = zipfile.ZipFile(archive_path, 'r')
                metadata_file = zip.open(metadata_file_name, 'r')
            except KeyError, err:
                metadata_file = None
                pass  # returning None will indicate that it was not there
        else:
            logger.error("package %s is not archived in a supported format" % archive_path)
    return metadata_file

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

def do_install(packages, config_file, installed, platform, install_dir, dry_run, local_archives=[]):
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

        logger.info("checking %s" % pname)
        
        # Existing tarball install, or new package install of either kind
        if pname in local_archives:
            if _install_local(pname, platform, package, local_archives[pname], install_dir, installed, dry_run):
                installed_pkgs.append(pname)
        else:
            if _install_binary(pname, platform, package, config_file, install_dir, installed, dry_run):
                installed_pkgs.append(pname)
    return installed_pkgs


def _install_local(configured_name, platform, package, package_path, install_dir, installed, dry_run):
    logger.info("installing %s from local archive" % package.name)
    metadata, files = _install_common(configured_name, platform, package, package_path, install_dir, installed, dry_run)

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
                                        platform=platform, installed=installed,
                                        install_dir=install_dir, files=files)
        return True
    else:
        return False

def _install_binary(configured_name, platform, package, config_file, install_dir, installed, dry_run):
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
    installed_pkg = installed.dependencies.get(package.name)

    # Rely on ArchiveDescription's equality-comparison method to discover
    # whether the installed ArchiveDescription matches the requested one. This
    # test also handles the case when inst_plat.archive is None (not yet
    # installed).
    if installed_pkg and installed_pkg['install_type'] == 'local':
        logger.warning("""skipping %s package because it was installed locally from %s
  To allow new installation, run 
  autobuild uninstall %s""" % (package_name, installed_pkg['archive']['url'], package_name))
        return False
    
    # get the package file in the cache, downloading if needed, and verify the hash
    # (raises InstallError on failure, so no check is needed)
    cachefile = get_package_file(package_name, archive.url, hash_algorithm=(archive.hash_algorithm or 'md5'), expected_hash=archive.hash)
    if cachefile is None:
        raise InstallError("Failed to download package '%s' from '%s'" % (package_name, archive.url))

    metadata, files = _install_common(configured_name, platform, package, cachefile, install_dir, installed, dry_run)
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
                                        platform=platform, installed=installed,
                                        install_dir=install_dir, files=files)
        return True
    else:
        return False

def get_metadata_from_package(package_file, package=None):
    metadata_file_name = configfile.PACKAGE_METADATA_FILE
    metadata_file = extract_metadata_from_package(package_file, metadata_file_name)
    if not metadata_file:
        logger.warning("WARNING: Archive '%s' does not contain metadata; build will be marked as dirty"
                       % os.path.basename(package_file))
        # Create a dummy metadata description for a package whose archive does not have one
        metadata = configfile.MetadataDescription()
        # split_tarname() returns a sequence like:
        # ("/some/path", ["boost", "1.39.0", "darwin", "20100222a"], ".tar.bz2")
        ignore_dir, from_name, ignore_ext = common.split_tarname(package_file)
        metadata.platform = from_name[2]
        metadata.build_id = from_name[3]
        metadata.configuration = 'unknown'
        if package is not None:
            if from_name[0] != package.name:
                raise InstallError("configured package name '%s' does not match name from archive '%s'" \
                                   % (package.name, from_name[0]))
            metadata.archive = package['platforms'][metadata.platform]['archive']
            metadata.package_description = package.copy()
        else:
            metadata.archive = configfile.ArchiveDescription()
            metadata.package_description = configfile.PackageDescription({})
        metadata.package_description.version = from_name[1]
        metadata.package_description.name = from_name[0]
        del metadata.package_description['platforms']
        metadata.dirty = True
    else:
        metadata = configfile.MetadataDescription(stream=metadata_file)
    return metadata

def install_new_if_needed(package, metadata, installed, dry_run):
    """
    Uninstall any installed different version
    Returns a boolean value for whether or not a new install is needed
    """
    do_install=False
    installed_pkg = installed.dependencies.get(package.name, None)
    if installed_pkg:
        if installed_pkg['package_description']['version'] != metadata.package_description.version:
            logger.info("%s version changed from %s to %s" % (package.name,
                                                              installed_pkg['package_description']['version'],
                                                              metadata.package_description.version))
            do_install = True
        if installed_pkg['build_id'] != metadata.build_id:
            logger.info("%s build id changed from %s to %s" % (package.name,
                                                               installed_pkg['build_id'],
                                                               metadata.build_id))
            do_install = True
        if do_install:
            if not dry_run:
                uninstall(package.name, installed)
            else:
                logger.info("would have uninstalled %s %s" % (package.name,
                                                              installed_pkg['package_description']['version']))
    else:
        # If the package has never yet been installed, we're good.
        logger.debug("%s not installed" % package.name)
        do_install = True
    return do_install

def _install_common(configured_name, platform, package, package_file, install_dir, installed, dry_run):

    metadata = get_metadata_from_package(package_file, package)

    # Check for required package_description elements
    package_errors = configfile.check_package_attributes(metadata, additional_requirements=['version'])
    if package_errors:
        logger.warning(package_errors + "\n    in package %s\n    build will be marked as 'dirty'" % package.name)
        metadata.dirty = True

    if configured_name != package.name:
        raise InstallError("Configured package name '%s' does not match name in package '%s'" % (configured_name, package.name))

    # this checks for a different version and uninstalls it if needed
    if not install_new_if_needed(package, metadata, installed, dry_run):
        logger.info("%s is already installed" % package.name)
        return None, None
    # Check for transitive dependency conflicts
    dependancy_conflicts = transitive_search(metadata, installed)
    if dependancy_conflicts:
        raise InstallError("""Package not installable due to conflicts
%s
  configuration %s
  version       %s
  build_id      %s
Conflict: %s
  If you have updated the configuration for any of the conflicting packages,
  try uninstalling those packages and rerunning.""" % \
  (package.name, 
   metadata.configuration,
   metadata.package_description.version,
   metadata.build_id,
   dependancy_conflicts
   ))

    # check that the install dir exists...
    if not os.path.exists(install_dir):
        if not dry_run:
            logger.debug("creating " + install_dir)
            os.makedirs(install_dir)
        else:
            logger.debug("would have created " + install_dir)

    if not dry_run:
        logger.info("installing %s" % package.name)
    else:
        logger.info("would have attempted install of %s" % package.name)
        return None,None

    # extract the files from the package
    try:
        files = _install_package(package_file, install_dir, exclude=[configfile.PACKAGE_METADATA_FILE])
    except common.AutobuildError as details:
        raise InstallError("Package '%s' attempts to install files already installed.\n%s\n  use --what-installed <file> to find the package that installed a conflict" % (package.name, details))
    if files:
        for f in files:
            logger.debug("    extracted " + f)

    # Prefer the licence attribute and license file location from the metadata, 
    # but for backward compatibility with legacy packages, allow use of the attributes
    # in the installable description (which are otherwise not required)
    if not ( metadata.package_description.get('license') or package.license ):
        clean_files(install_dir, files) # clean up any partial install
        raise InstallError("no license specified in metadata or configuration for %s." % package.name)

    license_file = metadata.package_description.get('license_file') or package.license_file
    if license_file is None \
      or not (license_file in files \
              or license_file.startswith('http://') \
              or license_file.startswith('https://') \
              ):
        clean_files(install_dir, files) # clean up any partial install
        raise InstallError("nonexistent license_file for %s: %s" % (package.name, license_file))
    
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
        logger.debug("  found conflict in installed packages")
        conflicts += "with installed package "
        conflicts += conflict
    # Check for conflicts with the dependencies of the new package 
    TransitiveSearched.add(new_package['package_description']['name'])
    if 'dependencies' in new_package:
        logger.debug("  checking conflicts for dependencies of %s in installed" % new_package['package_description']['name'])
        for new_dependency in new_package['dependencies'].iterkeys():
            depend_conflicts=""
            if new_dependency not in TransitiveSearched:
                depend_conflicts = transitive_dependency_conflicts(new_package['dependencies'][new_dependency], installed)
                if depend_conflicts:
                    conflicts += "dependency %s " % new_dependency
                    conflicts += depend_conflicts
                TransitiveSearched.add(new_dependency)
    return conflicts

def package_in_installed(new_package, installed):
    """
    Searches for new_package in the installed tree, returns error message (or empty string)
    (checks the root of the tree and walks the installed tree)
    """
    conflict = ""
    if 'dependencies' in installed:
        previous = installed['dependencies']
        for used in previous.iterkeys():
            # logger.debug("=====\npackage\n%s\nvs\n%s" % (pprint.pformat(new_package), pprint.pformat(previous[used])))
            used_conflict=""
            if new_package['package_description']['name'] == used:
                if 'archive' in new_package and new_package['archive']:
                    # this is a dependency of the new package, so we have archive data
                    if new_package['archive']['url'].rsplit('/',1)[-1] \
                      != previous[used]['archive']['url'].rsplit('/',1)[-1]:
                        used_conflict += "  installed url  %s\n" % previous[used]['archive']['url']
                        used_conflict += "             vs  %s\n" % new_package['archive']['url']
                    if new_package['archive']['hash'] != previous[used]['archive']['hash']:
                        used_conflict += "  installed hash %s\n" % previous[used]['archive']['hash']
                        used_conflict += "             vs  %s\n" % new_package['archive']['hash']
                else:
                    # this is the newly imported package, so we don't have a url for it
                    pass
                if new_package['configuration'] != previous[used]['configuration']:
                    used_conflict += "  installed configuration %s\n" % previous[used]['configuration']
                    used_conflict += "                      vs  %s\n" % new_package['configuration']
                if new_package['package_description']['version'] != previous[used]['package_description']['version']:
                    used_conflict += "  installed version %s\n" % previous[used]['package_description']['version']
                    used_conflict += "                vs  %s\n" % new_package['package_description']['version']
                if new_package['build_id'] != previous[used]['build_id']:
                    used_conflict += "  installed build_id %s\n" % previous[used]['build_id']
                    used_conflict += "                 vs  %s\n" % new_package['build_id']
                if used_conflict:
                    conflict += used + "\n" + used_conflict
            else:
                # recurse to check the dependencies of previous[used]
                conflict += package_in_installed(new_package, previous[used])
                if conflict:
                    conflict += "used by %s version %s build %s\n" % \
                      ( previous[used]['package_description']['name'],
                        previous[used]['package_description']['version'],
                        previous[used]['build_id'])
                        
            if conflict:
                # in order to be able to add the import path, we only detect the first conflict
                return conflict
    return ""


def _update_installed_package_files(metadata, package,
                                    platform=None, installed=None, install_dir=None, files=None):
    installed_package = metadata
    installed_package.install_dir = common.build_dir_relative_path(install_dir)

    installed_platform = package.get_platform(platform)
    installed_package.archive = installed_platform.archive
    installed_package.manifest = files
    installed.dependencies[metadata.package_description.name] = installed_package


def uninstall(package_name, installed_config):
    """
    Uninstall specified package_name: remove related files and delete
    package_name from the installed_config ConfigurationDescription.

    Saving the modified installed_config is the caller's responsibility.
    """
    try:
        # Retrieve this package's installed PackageDescription, and
        # remove it from installed_config at the same time.
        package = configfile.MetadataDescription(parsed_llsd=installed_config.dependencies.pop(package_name))
    except KeyError:
        # If the package has never yet been installed, we're good.
        logger.debug("%s not installed, no uninstall needed" % package_name)
        return

    logger.info("uninstalling %s version %s" % (package_name, package.package_description.version))
    clean_files(os.path.join(common.get_current_build_dir(),package.install_dir), package.manifest)
    installed_config.save()

def clean_files(install_dir, files):
    # Tarballs that name directories name them before the files they contain,
    # so the unpacker will create the directory before creating files in it.
    # For exactly that reason, we must remove things in reverse order.
    logger.debug("uninstalling from '%s'" % install_dir)
    directories=set() # directories we've removed files from
    for filename in files:
        install_path = os.path.join(install_dir, filename)
        if not os.path.isdir(install_path): # deal with directories below, after all files
            try:
                os.remove(install_path)
                # We used to print "removing f" before the call above, the
                # assumption being that we'd either succeed or produce a
                # traceback. But there are a couple different ways we could get
                # through this logic without actually deleting. So produce a
                # message only when we're sure we've actually deleted something.
                logger.debug("    removed " + filename)
            except OSError, err:
                if err.errno == errno.ENOENT:
                    # this file has already been deleted for some reason -- fine
                    logger.warning("    expected file not found: " + install_path)
                    pass
                else:
                    raise common.AutobuildError(str(err))
        directories.add(os.path.dirname(filename))

    # Check to see if any of the directories from which we removed files are now 
    # empty; if so, delete them (they will not have been listed in the manifest).
    # Do the checks in descending length order so that subdirectories will appear
    # before their containing directory. The loop is nested in order to clean up
    # directories that previously contained only subdirectories, so they were not
    # added to the list when deleting files above.
    while directories:
        parents=set()
        for dirname in sorted(directories, cmp=lambda x,y: cmp(len(y),len(x))):
            dir_path = os.path.join(install_dir, dirname)
            if os.path.exists(dir_path) and not os.listdir(dir_path):
                os.rmdir(dir_path)
                logger.debug("    removed " + dirname)
                parent=os.path.dirname(dirname)
                if dir_path:
                    parents.add(parent)
        directories=parents

def install_packages(args, config_file, install_dir, platform, packages):
    if not args.check_license:
        logger.warning("The --skip-license-check option is deprecated; it now has no effect")

    logger.debug("installing to directory: " + install_dir)
    # If installed_filename is already an absolute pathname, join() is smart
    # enough to leave it alone. Therefore we can do this unconditionally.
    installed_filename = os.path.join(install_dir, args.installed_filename)

    # load the list of already installed packages
    logger.debug("loading " + installed_filename)
    installed = configfile.Dependencies(installed_filename)

    # handle any arguments to query for information
    if handle_query_args(args, config_file, installed):
        return 0

    local_packages=[]
    if not packages: # no package names were specified on the command line
        if args.local_archives: # one or more --local packages were specified
            logger.warning("Using --local with no package names listed installs only those local packages")
            local_packages = config_file.installables.keys()
        else:
            logger.debug("no package names specified; installing all packages")
            packages = config_file.installables.keys()
        
    # examine any local archives to match then with package names.
    local_archives = {}
    for archive_path in args.local_archives:
        logger.info("Checking local archive '%s'" % archive_path)
        local_metadata = get_metadata_from_package(archive_path)
        if local_metadata.package_description.name in local_packages:
            packages.append(local_metadata.package_description.name)
        if local_metadata.package_description.name in packages:
            local_archives[local_metadata.package_description.name] = archive_path
        else:
            raise InstallError("no package '%s' found for local archive '%s'"
                               % (local_metadata.package_description.name, archive_path))


    # do the actual install of any new/updated packages
    packages = do_install(packages, config_file, installed, platform, install_dir,
                          args.dry_run, local_archives=local_archives)

    if not args.dry_run:
        # update the installed-packages.xml file
        try:
            # in case we got this far without ever having created installed_file's
            # parent directory
            os.makedirs(os.path.dirname(installed.path))
        except OSError, err:
            if err.errno != errno.EEXIST:
                raise AutobuildError(str(err))
        installed.save()
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
            '--what-installed',
            default=None,
            dest='query_installed_file',
            help="Identify the package that installed .")
        parser.add_argument(
            '--skip-license-check',
            action='store_false',
            default=True,
            dest='check_license',
            help="(deprecated - now has no effect)")
        parser.add_argument(
            '--list-installed-urls',
            action='store_true',
            default=False,
            dest='list_installed_urls',
            help="List installed package archive urls.")
        parser.add_argument(
            '--list-licenses',
            action='store_true',
            default=False,
            dest='list_licenses',
            help="List licenses for this package and all installed dependencies.")
        parser.add_argument(
            '--copyrights',
            action='store_true',
            default=False,
            dest='copyrights',
            help="Print copyrights for this package and all installed dependencies.")
        parser.add_argument(
            '--versions',
            action='store_true',
            default=False,
            dest='versions',
            help="Print versions for all installed dependencies.")
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
        UTF8Writer = codecs.getwriter('utf8')
        sys.stdout = UTF8Writer(sys.stdout)

        platform=common.get_current_platform()
        logger.debug("installing platform "+platform)

        # load the list of packages to install
        logger.debug("loading " + args.install_filename)
        config = configfile.ConfigurationDescription(args.install_filename)

        # establish a build directory so that the install directory is relative to it
        build_configurations = common.select_configurations(args, config, "installing for")
        if not build_configurations:
            logger.error("no applicable configurations found.\n"
                         "did you remember to mark a configuration as default?\n"
                         "autobuild cowardly refuses to do nothing!")

        for build_configuration in build_configurations:
            # Get enriched environment based on the current configuration
            environment = get_enriched_environment(build_configuration.name)
            # then get a copy of the config specific to this build
            # configuration
            bconfig = config.copy()
            # and expand its $variables according to the environment.
            bconfig.expand_platform_vars(environment)
            # Re-fetch the build configuration so we have its expansions.
            build_configuration = bconfig.get_build_configuration(build_configuration.name, platform_name=platform)
            build_directory = bconfig.get_build_directory(build_configuration, platform_name=platform)

            # write packages into 'packages' subdir of build directory
            install_dirs = \
                common.select_directories(args, bconfig,
                                          "install", "installing packages for",
                                          lambda cnf:
                                          os.path.join(bconfig.make_build_directory(cnf, platform=platform, dry_run=args.dry_run),
                                                       "packages"))

            # get the absolute paths to the install dir and installed-packages.xml file
            for install_dir in install_dirs:
                install_dir = os.path.realpath(install_dir)
                install_packages(args, bconfig, install_dir, platform, args.package)

if __name__ == '__main__':
    sys.exit("Please invoke this script using 'autobuild %s'" %
             AutobuildTool().get_details()["name"])
