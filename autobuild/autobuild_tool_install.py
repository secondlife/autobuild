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
    list = "none"
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

    return False


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
            raise InstallError("no license specified for %s. Aborting... "
                               "(you can use --skip-license-check)" % pname)


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
        # if not specified, assume a default naming convention
        if not license_file:
            license_file = 'LICENSES/%s.txt' % pname
        # if a URL is given, assuming it's valid for now
        if license_file.startswith('http://'):
            continue
        # otherwise, assert that the license file is in the archive
        if not os.path.exists(os.path.join(installed_file.dependencies[package.name].install_dir,
                                           license_file)):
            raise InstallError("nonexistent license_file for %s: %s "
                               "(you can use --skip-license-check)" % (pname, license_file))


def check_package_for_duplicate_files(metadata, install_dir):
    duplicate_files = []
    for packaged_file in metadata.manifest:
        if os.path.exists(os.path.join(install_dir, packaged_file)):
            duplicate_files.append(packaged_file)
    if duplicate_files:
        raise InstallError("package '%s' contains %d conflicting files: %s"
                           % (metadata.package_description.name, len(duplicate_files), duplicate_files))


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
    package_name = package.name
    
    if dry_run:
        dry_run_msg("Dry run mode: not checking or installing %s" % package.name)
        return False

    # If this package has already been installed, first uninstall the older
    # version.
    uninstall(package_name, installed_file)

    metadata_file_name = configfile.PACKAGE_METADATA_FILE
    metadata_file = common.extract_metadata_from_package(package_path, metadata_file_name)
    if not metadata_file:
        raise InstallError("package '%s' does not contain metadata (%s)" % (package.name, metadata_file_name))
    else:
        metadata = configfile.MetadataDescription(stream=metadata_file)
        legacy = None

    logger.warn("installing %s from local archive" % package.name)

    # before installing, check the manifest data in the metadata for conf
    check_package_for_duplicate_files(metadata, install_dir)  # raises InstallError if it fails
    
    # check that the install dir exists...
    if not os.path.exists(install_dir):
        logger.debug("creating " + install_dir)
        os.makedirs(install_dir)

    # extract the files from the package
    files = common.install_package(package_path, install_dir, exclude=[metadata_file_name])
    if not files:
        return False
    for f in files:
        logger.debug("extracted: " + f)

    installed_package = package.copy()
    if platform not in package.platforms:
        installed_platform = configfile.PlatformDescription(dict(name=platform))
    else:
        installed_platform = installed_package.get_platform(platform)
    if installed_platform.archive is None:
        installed_platform.archive = configfile.ArchiveDescription()
    installed_platform.archive.url = "file://" + os.path.abspath(package_path)
    installed_platform.archive.hash = common.compute_md5(package_path)
    metadata.legacy = legacy
    metadata.install_type = 'local'
    _update_installed_package_files(metadata, installed_package,
                                    platform=platform, installed_file=installed_file,
                                    install_dir=install_dir, files=files)
    return True


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
    cachefile = common.get_package_in_cache(archive.url)

    # download the package, if it's not already in our cache
    download_required = False
    if os.path.exists(cachefile):
        if hash_algorithms.verify_hash(archive.hash_algorithm, cachefile, archive.hash):
            logger.debug("found in cache: " + cachefile)
        else:
            download_required = True
            common.remove_package(archive.url)
    else:
        download_required = True
    
    if download_required:
        # download the package to the cache
        logger.warn("downloading %s archive from %s" % (package.name, archive.url))
        if not common.download_package(archive.url):
            # Download failure has been observed to leave a zero-length file.
            common.remove_package(archive.url)
            raise InstallError("failed to download %s" % archive.url)
    
        # error out if MD5 doesn't match
        if not hash_algorithms.verify_hash(archive.hash_algorithm, cachefile, archive.hash):
            common.remove_package(archive.url)
            raise InstallError("download error--%s mismatch for %s" % ((archive.hash_algorithm or "md5"), cachefile))

    # dry run mode = download but don't install packages
    if dry_run:
        dry_run_msg("Dry run mode: not installing %s" % package.name)
        return False

    # If this package has already been installed, first uninstall the older
    # version.
    uninstall(package.name, installed_file)

    metadata_file_name = configfile.PACKAGE_METADATA_FILE
    metadata_file = common.extract_metadata_from_package(cachefile, metadata_file_name)
    if not metadata_file:
        raise InstallError("package '%s' does not contain metadata (%s)" % (package.name, metadata_file_name))
    else:
        metadata = configfile.MetadataDescription(stream=metadata_file)
        legacy = None

    # check that the install dir exists...
    if not os.path.exists(install_dir):
        logger.debug("creating " + install_dir)
        os.makedirs(install_dir)

    logger.warn("installing %s from archive" % package.name)
    # extract the files from the package
    files = common.extract_package(archive.url, install_dir, exclude=[metadata_file_name])
    for f in files:
        logger.debug("extracted: " + f)
        
    installed_package = package.copy()
    if platform not in package.platforms:
        installed_platform = configfile.PlatformDescription(dict(name=platform))
    else:
        installed_platform = installed_package.get_platform(platform)
    if installed_platform.archive is None:
        installed_platform.archive = configfile.ArchiveDescription()
    metadata.legacy = legacy
    metadata.install_type = 'package'
    _update_installed_package_files(metadata, package, 
                                    platform=platform, installed_file=installed_file,
                                    install_dir=install_dir, files=files)
    return True


def _update_installed_package_files(metadata, package,
                                    platform=None, installed_file=None, install_dir=None, files=None):
    installed_package = metadata
    installed_package.install_dir = install_dir

    installed_platform = package.get_platform(platform)
    installed_package.archive = installed_platform.archive
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
    logger.debug("uninstalling %s from %s" % (package_name, package.install_dir))
    # Tarballs that name directories name them before the files they contain,
    # so the unpacker will create the directory before creating files in it.
    # For exactly that reason, we must remove things in reverse order.
    for f in reversed(package.manifest):
        # Some tarballs contain funky directory name entries (".//"). Use
        # realpath() to dewackify them.
        fn = os.path.normpath(os.path.join(package.install_dir, f))
        try:
            os.remove(fn)
            # We used to print "removing f" before the call above, the
            # assumption being that we'd either succeed or produce a
            # traceback. But there are a couple different ways we could get
            # through this logic without actually deleting. So produce a
            # message only when we're sure we've actually deleted something.
            logger.debug("    removed " + f)
        except OSError, err:
            if err.errno == errno.ENOENT:
                # this file has already been deleted for some reason -- fine
                pass
            elif err.errno == dict(win32=errno.EACCES,
                                   darwin=errno.EPERM,
                                   linux2=errno.EISDIR).get(sys.platform):
                # This can happen if we're trying to remove a directory.
                # Obnoxiously, the specific errno for this error varies by
                # platform. While we could call isdir(fn) beforehand, we
                # expect directory names to pop up only a small fraction of
                # the time, and doing it reactively improves usual-case
                # performance.
                if not os.path.isdir(fn):
                    # whoops, permission error trying to remove a file?!
                    raise
                # Okay, it's a directory, remove it with rmdir().
                try:
                    os.rmdir(fn)
                    logger.debug("    removed " + f)
                except OSError, err:
                    # We try to remove directories named in the install
                    # archive in case these directories were created solely
                    # for this package. But the package can't know whether a
                    # given target directory is shared with other packages, so
                    # the attempt to remove the dir may fail because it still
                    # contains files.
                    if err.errno != errno.ENOTEMPTY:
                        raise
                    logger.debug("    leaving " + f)
            else:
                # no idea what this exception is, better let it propagate
                raise


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
    if options.check_license:
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
    if options.check_license and not options.dry_run:
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
            help="Do not perform the license check.")
        parser.add_argument(
            '--list-licenses',
            action='store_true',
            default=False,
            dest='list_licenses',
            help="List known licenses and exit.")
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
