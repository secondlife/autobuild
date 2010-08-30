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

import os
import sys
import optparse
import pprint
import common
import configfile
import autobuild_base
from llbase import llsd
import subprocess

AutobuildError = common.AutobuildError

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
        '--get-source',
        action='append',
        dest='get_source',
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
        return print_list("Installed", installed_file.packages)

    if options.list_archives:
        return print_list("Packages", config_file.packages)

    if options.list_licenses:
        licenses = []
        for pname in config_file.packages:
            package = config_file.package(pname)
            if package.license:
                licenses.append(package.license)
        return print_list("Licenses", licenses)

    if options.export_manifest:
        for name in installed_file.packages:
            package = installed_file.package(name)
            pprint.pprint(package)
        return True

    return False

def get_packages_to_install(packages, config_file, installed_config, platform, as_source=[]):
    """
    Given the (potentially empty) list of package archives on the command line, work out
    the set of packages that are out of date and require a new download/install. This will
    return [] if all packages are up to date.
    """

    # if no packages specified, consider all
    if packages is None or len(packages) == 0:
        packages = config_file.packages

    # compile a subset of packages we actually need to install
    to_install = []
    for pname in packages:
        
        toinstall = config_file.package(pname)
        installed = installed_config.package(pname)

        # raise error if named package doesn't exist in autobuild.xml
        if not toinstall:
            raise AutobuildError('Unknown package: %s' % pname)

        if pname in as_source:
            if not toinstall.source:
                raise AutobuildError("No source url specified for %" % pname)
            if not toinstall.sourcetype:
                raise AutobuildError("No source repository type specified for %" % pname)
        else:
            # check that we have a platform-specific or common url to use
            if not toinstall.archives_url(platform):
               raise AutobuildError("No url specified for this platform for %s" % pname)

        # install this package if it is new or out of date
        if installed == None or \
           toinstall.archives_url(platform) != installed.archives_url(platform) or \
           toinstall.archives_md5(platform) != installed.archives_md5(platform) or\
           pname in as_source:
            to_install.append(pname)

    return to_install

def pre_install_license_check(packages, config_file):
    """
    Raises a runtime exception if any of the specified packages do not have a
    license property set.
    """
    for pname in packages:
        package = config_file.package(pname)
        license = package.license
        if not license:
            raise AutobuildError("No license specified for %s. Aborting... (you can use --skip-license-check)" % pname)

def post_install_license_check(packages, config_file, install_dir):
    """
    Raises a runtime exception if the licensefile property for any of
    the specified packages does not refer to a valid file in the
    extracted archive, or does not specify an http:// URL to the
    license description.
    """
    for pname in packages:
        package = config_file.package(pname)
        licensefile = package.licensefile
        # if not specified, assume a default naming convention
        if not licensefile:
            licensefile = 'LICENSES/%s.txt' % pname
        # if a URL is given, assuming it's valid for now
        if licensefile.startswith('http://'):
            continue
        # otherwise, assert that the license file is in the archive
        if not os.path.exists(os.path.join(install_dir, licensefile)):
            raise AutobuildError("Invalid or undefined licensefile for %s. (you can use --skip-license-check)" % pname)

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

    # Filter for files which we actually requested to install.
    for pname in packages:
        package = config_file.package(pname)
        if pname in as_source:
            _install_source(pname, package.sourcetype,
                package.source, installed_file, config_file, dry_run)
        else:
            _install_binary(package, platform, config_file, install_dir, installed_file, dry_run)

def _install_source(pname, repotype, url, installed_config, config_file, dry_run):
    if dry_run:
        print "Dry run mode: not installing source for %s" % pname
        return
    installed_package = installed_config.package(pname)
    if installed_package:
        if installed_package.source != url:
            raise AutobuildError("Source repository %s does not match installed %s" %
                (url, installed_package.source))
        if installed_package.sourcetype != repotype:
            raise AutobuildError("Source repository type %s does not match installed type %s" %
                (repotype, installed_package.sourcetype))
    else:
        installed_package = configfile.PackageInfo()
    
    # By convention source is downloaded into the parent directory containing this project.
    sourcepath = os.path.normpath(
        os.path.join(os.path.dirname(config_file.filename), os.pardir, pname))
    if repotype == 'svn':
        if os.path.isdir(sourcepath):
            if subprocess.call(['svn', 'update', sourcepath]) != 0:
                raise AutobuildError("Error updating %s" % pname)
        else:
            if subprocess.call(['svn', 'checkout', url, sourcepath]) != 0:
                raise AutobuildError("Error checking out %s" % pname)
    elif repotype == 'hg':
        if os.path.isdir(sourcepath):
            cwd = os.getcwd()
            os.chdir(sourcepath)
            try:
                if subprocess.call(['hg', 'pull']) != 0:
                    raise AutobuildError("Error pulling %s" % pname)
                if subprocess.call(['hg', 'update']) != 0:
                    raise AutobuildError("Error updating %s" % pname)
            finally:
                os.chdir(cwd)
        else:
            if subprocess.call(['hg', 'clone', url, sourcepath]) != 0:
                raise AutobuildError("Error cloning %s" % pname)
    else:
        raise AutobuildError("Unsupported repository type %s" % repotype)
    
    installed_package.source = url
    installed_package.sourcetype = repotype
    installed_config.set_package(pname, installed_package)
    
def _install_binary(package, platform, config_file, install_dir, installed_file, dry_run):
    # find the url/md5 for the platform, or fallback to 'common'
    url = package.archives_url(platform)
    md5 = package.archives_md5(platform)
    cachefile = common.get_package_in_cache(url)

    # download the package, if it's not already in our cache
    if not common.is_package_in_cache(url):

        # download the package to the cache
        if not common.download_package(url):
            raise AutobuildError("Failed to download %s" % url)

        # error out if MD5 doesn't matches
        if not common.does_package_match_md5(url, md5):
            common.remove_package(url)
            raise AutobuildError("md5 mismatch for %s" % cachefile)

    # dry run mode = download but don't install packages
    if dry_run:
        print "Dry run mode: not installing %s" % pname
        return

    # extract the files from the package
    files = common.extract_package(url, install_dir)

    # update the installed-packages.xml file
    pname = package.name
    package = installed_file.package(pname)
    if not package:
        package = configfile.PackageInfo()
    package.set_archives_url(platform, url)
    package.set_archives_md5(platform, md5)
    package.set_archives_files(platform, files)
    installed_file.set_package(pname, package)

def install_packages(options, args):
    # write packages into 'packages' subdir of build directory by default
    if not options.install_dir:
        import configure
        options.install_dir = configure.get_package_dir()

    # get the absolute paths to the install dir and installed-packages.xml file
    install_dir = os.path.realpath(options.install_dir)
    installed_filename = options.installed_filename
    if not os.path.isabs(installed_filename):
        installed_filename = os.path.join(install_dir, installed_filename)

    # load the list of already installed packages
    installed_file = configfile.ConfigFile()
    installed_file.load(os.path.join(options.install_dir, installed_filename))

    # load the list of packages to install
    config_file = configfile.ConfigFile()
    config_file.load(options.install_filename)
    if config_file.empty:
        print "No package information to load from", options.install_filename
        return 0

    # get the list of packages to actually installed
    if not options.get_source:
        options.get_source = []
    packages = get_packages_to_install(args, config_file, installed_file, 
        options.platform, as_source=options.get_source)

    # handle any arguments to query for information
    if handle_query_args(options, config_file, installed_file):
        return 0

    # check the license properties for the packages to install
    if options.check_license:
        pre_install_license_check(packages, config_file)

    # do the actual install of the new/updated packages
    do_install(packages, config_file, installed_file, options.platform, install_dir,
               options.dry_run, as_source=options.get_source)

    # check the licensefile properties for the newly installed packages
    if options.check_license and not options.dry_run:
        post_install_license_check(packages, config_file, install_dir)

    # update the installed-packages.xml file, if it was changed
    if installed_file.changed:
        installed_file.save()
    else:
        print "All packages are up to date."
    return 0

# define the entry point to this autobuild tool
class autobuild_tool(autobuild_base.autobuild_base):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description='Fetch and install package archives.')

    def register(self, parser):
        add_arguments(parser)

    def run(self, args):
        install_packages(args, args.package)

if __name__ == '__main__':
    sys.exit("Please invoke this script using 'autobuild %s'" %
             autobuild_tool().get_details()["name"])
