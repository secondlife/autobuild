# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
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
# *TODO: add support for an 'autobuild uninstall' command
# *TODO: add an 'autobuild info' command to query config file contents

# alain: twould be nice if you could add some logging to the install tool.
# nat: What's the model? I had some test failures due to no such thing as common.log().
# alain: most other commands are using the logging package.  See, e.g., package.
# nat: Is that centrally constructed?
# alain: common.log was removed.
# nat: s/constructed/configured/
# alain: you can look at the python package logging if you are interested.
# alain: the usual metaphor is to use logging.getLogger('autobuild.<tool>')
# nat: I've used it before. Will look at autobuild_tool_package.py.
# alain: the 'autobuild' logger is configured from the main.
# alain: sub loggers inherit.
# nat: Aha, that's what I was asking, thanks.
# alain: One thing I'd like to see is a message for each package installed at info level so when I use --verbose I can actually see what's getting installed.
# alain: feel free to be profligate with debug logging if you so desire ;-)
# alain: (I haven't really, if truth be told).
# nat: So at what level would you like to see the individual files belonging to package tarballs?
# alain: INFO should be the default for all things not warning or error.
# alain: INFO only gets printed when --verbose is used.
# nat: And --verbose setting log level INFO is part of the main configuration? Cool.
# alain: at --quiet, only ERROR is printed.

import os
import sys
import errno
import pprint
import common
import configfile
import autobuild_base
from llbase import llsd
import subprocess
import hash_algorithms

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

def add_arguments(parser):
    parser.add_argument(
        'package',
        nargs='*',
        help='List of packages to consider for installation.')
    parser.add_argument(
        '--config-file',
        default=configfile.AUTOBUILD_CONFIG_FILE,
        dest='install_filename',
        help='The file used to describe what should be installed.')
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
        dest='install_dir',
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
    parser.add_argument(
        '--as-source',
        action='append',
        dest='as_source',
        default=[],
        help="Get the source for this package instead of prebuilt binary.")

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
        return print_list("Installed", installed_file.installables.keys())

    if options.list_archives:
        return print_list("Packages", config_file.installables.keys())

    if options.list_licenses:
        licenses = [package.license for package in config_file.installables.itervalues()
                    if package.license]
        return print_list("Licenses", licenses)

    if options.export_manifest:
        for package in installed_file.installables.itervalues():
            pprint.pprint(package)
        return True

    return False

def get_packages_to_install(packages, config_file, installed_config, platform):
    """
    Given the (potentially empty) list of package archives on the command line, work out
    the set of packages that are out of date and require a new download/install. This will
    return [] if all packages are up to date.
    """

    # if no packages specified, consider all
    if not packages:
        packages = config_file.installables.keys()

    # compile a subset of packages we actually need to install
    return [pname for pname in packages
            if should_install(pname, config_file, installed_config, platform)]

def should_install(package_name, config_file, installed_config, platform):
    try:
        toinstall = config_file.installables[package_name]
    except KeyError:
        # raise error if named package doesn't exist in autobuild.xml
        raise InstallError('unknown package: %s' % package_name)

    # Has this package ever been installed before?
    try:
        installed = installed_config.installables[package_name]
    except KeyError:
        # package hasn't yet been installed at all
        return True

    # Here the package has already been installed. Need to update it?

    # The --as_source command-line switch only affects the installation of new
    # packages. When we first install a package, we remember whether it's
    # --as_source. Every subsequent 'autobuild install' affecting that package
    # must honor the original --as_source setting. After an initial
    # --as_source install, it's HANDS OFF! The possibility of local source
    # changes makes any further autobuild operations on that repository
    # ill-advised.
    if installed.as_source:
        return False

    # Not a source package, but a reference to a binary archive. Check that we
    # have a platform-specific or common url to use.
    req_platform = toinstall.get_platform(platform)
    if not req_platform:
       raise InstallError("no platform %s for %s" % (platform, package_name))
    if not req_platform.archive:
       raise InstallError("no archive specified for platform %s for %s" %
                            (platform, package_name))

    # install this package if it is new or out of date
    inst_platform = installed.get_platform(platform)
    if not inst_platform:
        # This package appears in installed_config, but with no entry for this
        # platform, so can't be installed yet for this platform.
        return True

    # Rely on ArchiveDescription's equality-comparison method to discover
    # whether the installed ArchiveDescription matches the requested one. This
    # test also handles the case when inst_platform.archive is None (not yet
    # installed).
    # Note the sense of the test: if the data does not match, then we
    # should_install(). If everything matches, there's no need.
    return req_platform.archive != inst_platform.archive

def pre_install_license_check(packages, config_file):
    """
    Raises a runtime exception if any of the specified packages do not have a
    license property set.
    """
    for pname in packages:
        package = config_file.installables[pname]
        license = package.license
        if not license:
            raise InstallError("no license specified for %s. Aborting... "
                                 "(you can use --skip-license-check)" % pname)

def post_install_license_check(packages, config_file, install_dir):
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
        if not os.path.exists(os.path.join(install_dir, license_file)):
            raise InstallError("invalid or undefined license_file for %s: %s "
                                 "(you can use --skip-license-check)" % (pname, license_file))

def do_install(packages, config_file, installed_file, platform, install_dir, dry_run, as_source=[]):
    """
    Install the specified list of packages. By default this will download the
    packages to the local cache, extract the contents of those
    archives to the install dir, and update the installed_file config.  For packages
    listed in the optional 'as_source' list, the source will be downloaded in place
    of the prebuilt binary.
    """

    # check that the install dir exists...
    if not os.path.exists(install_dir):
        os.makedirs(install_dir)

    # Decide whether to check out (or update) source, or download a tarball
    for pname in packages:
        package = config_file.installables[pname]
        try:
            installed = installed_file.installables[pname]
        except KeyError:
            # New install, so honor --as_source switch.
            source_install = (pname in as_source)
        else:
            # Existing install. If pname was previously installed --as_source,
            # do not mess with it now.
            source_install = installed.as_source
            if source_install:
                continue

        # Existing tarball install, or new package install of either kind
        if source_install:
            _install_source(package, installed_file, config_file, dry_run)
        else:
            _install_binary(package, platform, config_file, install_dir, installed_file, dry_run)

def _install_source(package, installed_config, config_file, dry_run):
    if dry_run:
        print "Dry run mode: not installing %s source for %s from %s" % \
              (package.sourcetype, package.name, package.source)
        return

    if not package.source:
        raise InstallError("no source url specified for %s" % package.name)
    if not package.sourcetype:
        raise InstallError("no source repository type specified for %s" % package.name)
    if not package.source_directory:
        raise InstallError("no source_directory specified for %s" % package.name)

    # Question: package.source_directory is specific to each
    # PackageDescription; do we need to further qualify the pathname with the
    # package.name?
    sourcepath = config_file.absolute_path(os.path.join(package.source_directory, package.name))
    if os.path.isdir(sourcepath):
        raise InstallError("trying to install %s --as_source over existing directory %s" %
                           (package.name, sourcepath))
    if package.sourcetype == 'svn':
        if subprocess.call(['svn', 'checkout', package.source, sourcepath]) != 0:
            raise InstallError("error checking out %s" % package.name)
    elif package.sourcetype == 'hg':
        if subprocess.call(['hg', 'clone', package.source, sourcepath]) != 0:
            raise InstallError("error cloning %s" % package.name)
    else:
        raise InstallError("unsupported repository type %s for %s" %
                           (package.sourcetype, package.name))

    # Copy PackageDescription metadata from the autobuild.xml entry.
    ipkg = package.copy()
    # Set it as the installed package.
    installed_config.installables[package.name] = ipkg
    ipkg.as_source = True
    # But clear platforms: we only use platforms for tarball installs.
    ipkg.platforms.clear()

def _install_binary(package, platform, config_file, install_dir, installed_file, dry_run):
    # find the url/md5 for the platform, or fallback to 'common'
    pf = package.get_platform(platform)
    archive = pf.archive
    cachefile = common.get_package_in_cache(archive.url)

    # download the package, if it's not already in our cache
    if not os.path.exists(cachefile):

        # download the package to the cache
        if not common.download_package(archive.url):
            raise InstallError("failed to download %s" % archive.url)

        # error out if MD5 doesn't match
        if not hash_algorithms.verify_hash(archive.hash_algorithm, cachefile, archive.hash):
            common.remove_package(archive.url)
            raise InstallError("%s mismatch for %s" % (archive.hash_algorithm, cachefile))

    # dry run mode = download but don't install packages
    if dry_run:
        print "Dry run mode: not installing %s" % package.name
        return

    # If this package has already been installed, first uninstall the older
    # version.
    uninstall(package.name, installed_file, install_dir)

    # extract the files from the package
    files = common.extract_package(archive.url, install_dir)

    # Update the installed-packages.xml file. The above uninstall() call
    # should have removed any existing entry in installed_file. Copy
    # PackageDescription metadata from the autobuild.xml entry.
    ipkg = package.copy()
    # Set it as the installed package.
    installed_file.installables[package.name] = ipkg
    ipkg.as_source = False
    # But clear platforms: there should be exactly one.
    ipkg.platforms.clear()

    # Even if we end up using the "common" specification in autobuild.xml,
    # in installed-packages.xml we should say we've installed this package
    # on THIS platform rather than on "common".
    iplat = pf.copy()
    ipkg.platforms[platform] = iplat
    iplat.manifest = files

def uninstall(package_name, installed_config, install_dir):
    """
    Uninstall specified package_name: remove related files and delete
    package_name from the installed_config ConfigurationDescription.

    For a package_name installed with --as_source, simply remove the
    PackageDescription from installed_config.

    Saving the modified installed_config is the caller's responsibility.
    """
    try:
        # Not only retrieve this package's installed PackageDescription, but
        # remove it from installed_config at the same time.
        package = installed_config.installables.pop(package_name)
    except KeyError:
        # If the package has never yet been installed, we're good.
        return

    if package.as_source:
        # Only delete files for a tarball install.
        return

    # The platforms attribute should contain exactly one PlatformDescription.
    # We don't especially care about its key name.
    _, platform = package.platforms.popitem()
    for f in platform.manifest:
        fn = os.path.join(install_dir, f)
        try:
            os.remove(fn)
        except OSError, err:
            if err.errno != errno.ENOENT:
                raise

def install_packages(options, args):
    # load the list of packages to install
    config_file = configfile.ConfigurationDescription(options.install_filename)

    # write packages into 'packages' subdir of build directory by default
    if not options.install_dir:
        options.install_dir = os.path.join(config_file.make_build_directory(), 'packages')

    # get the absolute paths to the install dir and installed-packages.xml file
    install_dir = os.path.realpath(options.install_dir)
    # If installed_filename is already an absolute pathname, join() is smart
    # enough to leave it alone. Therefore we can do this unconditionally.
    installed_filename = os.path.join(install_dir, options.installed_filename)

    # load the list of already installed packages
    installed_file = configfile.ConfigurationDescription(installed_filename)

    # get the list of packages to actually install
    packages = get_packages_to_install(args, config_file, installed_file, options.platform)

    # handle any arguments to query for information
    if handle_query_args(options, config_file, installed_file):
        return 0

    # check the license properties for the packages to install
    if options.check_license:
        pre_install_license_check(packages, config_file)

    # do the actual install of the new/updated packages
    do_install(packages, config_file, installed_file, options.platform, install_dir,
               options.dry_run, as_source=options.as_source)

    # check the license_file properties for the newly installed packages
    if options.check_license and not options.dry_run:
        post_install_license_check(packages, config_file, install_dir)

    # update the installed-packages.xml file
    installed_file.save()
    return 0

# define the entry point to this autobuild tool
class AutobuildTool(autobuild_base.AutobuildBase):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description='Fetch and install package archives.')

    def register(self, parser):
        add_arguments(parser)

    def run(self, args):
        install_packages(args, args.package)

if __name__ == '__main__':
    sys.exit("Please invoke this script using 'autobuild %s'" %
             AutobuildTool().get_details()["name"])
