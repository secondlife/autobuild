#!/usr/bin/env python
"""\
@file install.py
@author Martin Redd
@date 2010-04-19
@brief Install files into a repository

For reference, the old indra install specification at:
https://wiki.lindenlab.com/wiki/User:Phoenix/Library_Installation


$LicenseInfo:firstyear=2010&license=mit$

Copyright (c) 2010, Linden Research, Inc.

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
import optparse
import pprint
import common
import configfile
from llbase import llsd

# *HACK - make sure this gets passed in by calling code / command line -brad
__base_dir = os.getcwd()

# *TODO: update this to work for argparse
def parse_args(args):
    parser = optparse.OptionParser(
        usage="usage: %prog [options] [installable1 [installable2...]]",
        #formatter = helpformatter.Formatter(),
        description="""This script fetches and installs installable packages.
It also handles uninstalling those packages and manages the mapping between
packages and their license.

The process is to open and read an install manifest file which specifies
what files should be installed. For each installable to be installed.
 * make sure it has a license
 * check the installed version
 ** if not installed and needs to be, download and install
 ** if installed version differs, download & install

If no installables are specified on the command line, then the defaut
behavior is to install all known installables appropriate for the platform
specified or uninstall all installables if --uninstall is set. You can specify
more than one installable on the command line.

When specifying a platform, you can specify 'all' to install all
packages, or any platform of the form:

OS[/arch[/compiler[/compiler_version]]]

Where the supported values for each are:
OS: darwin, linux, windows, solaris
arch: i686, x86_64, ppc, universal
compiler: vs, gcc
compiler_version: 2003, 2005, 2008, 3.3, 3.4, 4.0, etc.

No checks are made to ensure a valid combination of platform
parts. Some exmples of valid platforms:

windows
windows/i686/vs/2005
linux/x86_64/gcc/3.3
linux/x86_64/gcc/4.0
darwin/universal/gcc/4.0
""")
    parser.add_option(
        '--dry-run', 
        action='store_true',
        default=False,
        dest='dryrun',
        help='Do not actually install files. Downloads will still happen.')
    parser.add_option(
        '--package-info',
        type='string',
        default=os.path.join(__base_dir, 'packages.xml'),
        dest='install_filename',
        help='The file used to describe what should be installed.')
    parser.add_option(
        '--installed-manifest', 
        type='string',
        default='installed-packages.xml',
        dest='installed_filename',
        help='The file used to record what is installed.')
    parser.add_option(
        '--export-manifest', 
        action='store_true',
        default=False,
        dest='export_manifest',
        help="Print the install manifest to stdout and exit.")
    parser.add_option(
        '-p', '--platform', 
        type='string',
        default=common.getCurrentPlatform(),
        dest='platform',
        help="""Override the automatically determined platform. \
You can specify 'all' to do a installation of installables for all platforms.""")
    parser.add_option(
        '--cache-dir', 
        type='string',
        default=common.Options().getInstallCacheDir(),
        dest='cache_dir',
        help='Where to download files. Default: %s'% \
             (common.Options().getInstallCacheDir()))
    parser.add_option(
        '--install-dir', 
        type='string',
        default=None,
        dest='install_dir',
        help='Where to unpack the installed files.')
    parser.add_option(
        '--list-installed', 
        action='store_true',
        default=False,
        dest='list_installed',
        help="List the installed package names and exit.")
    parser.add_option(
        '--skip-license-check', 
        action='store_false',
        default=True,
        dest='check_license',
        help="Do not perform the license check.")
    parser.add_option(
        '--list-licenses', 
        action='store_true',
        default=False,
        dest='list_licenses',
        help="List known licenses and exit.")
    parser.add_option(
        '--detail-license', 
        type='string',
        default=None,
        dest='detail_license',
        help="Get detailed information on specified license and exit.")
    parser.add_option(
        '--add-license', 
        type='string',
        default=None,
        dest='new_license',
        help="""Add a license to the install file. Argument is the name of \
license. Specify --license-url if the license is remote or specify \
--license-text, otherwse the license text will be read from standard \
input.""")
    parser.add_option(
        '--license-url', 
        type='string',
        default=None,
        dest='license_url',
        help="""Put the specified url into an added license. \
Ignored if --add-license is not specified.""")
    parser.add_option(
        '--license-text', 
        type='string',
        default=None,
        dest='license_text',
        help="""Put the text into an added license. \
Ignored if --add-license is not specified.""")
    parser.add_option(
        '--remove-license', 
        type='string',
        default=None,
        dest='remove_license',
        help="Remove a named license.")
    parser.add_option(
        '--remove-installable', 
        type='string',
        default=None,
        dest='remove_installable',
        help="Remove a installable from the install file.")
    parser.add_option(
        '--add-installable', 
        type='string',
        default=None,
        dest='add_installable',
        help="""Add a installable into the install file. Argument is \ 
the name of the installable to add.""")
    parser.add_option(
        '--add-installable-metadata', 
        type='string',
        default=None,
        dest='add_installable_metadata',
        help="""Add package for library into the install file. Argument is \
the name of the library to add.""")
    parser.add_option(
        '--installable-copyright', 
        type='string',
        default=None,
        dest='installable_copyright',
        help="""Copyright for specified new package. Ignored if \
--add-installable is not specified.""")
    parser.add_option(
        '--installable-license', 
        type='string',
        default=None,
        dest='installable_license',
        help="""Name of license for specified new package. Ignored if \
--add-installable is not specified.""")
    parser.add_option(
        '--installable-description', 
        type='string',
        default=None,
        dest='installable_description',
        help="""Description for specified new package. Ignored if \
--add-installable is not specified.""")
    parser.add_option(
        '--add-installable-package', 
        type='string',
        default=None,
        dest='add_installable_package',
        help="""Add package for library into the install file. Argument is \
the name of the library to add.""")
    parser.add_option(
        '--package-platform', 
        type='string',
        default=None,
        dest='package_platform',
        help="""Platform for specified new package. \
Ignored if --add-installable or --add-installable-package is not specified.""")
    parser.add_option(
        '--package-url', 
        type='string',
        default=None,
        dest='package_url',
        help="""URL for specified package. \
Ignored if --add-installable or --add-installable-package is not specified.""")
    parser.add_option(
        '--package-md5', 
        type='string',
        default=None,
        dest='package_md5',
        help="""md5sum for new package. \
Ignored if --add-installable or --add-installable-package is not specified.""")
    parser.add_option(
        '--list', 
        action='store_true',
        default=False,
        dest='list_installables',
        help="List the installables in the install manifest and exit.")
    parser.add_option(
        '--detail', 
        type='string',
        default=None,
        dest='detail_installable',
        help="Get detailed information on specified installable and exit.")
    parser.add_option(
        '--detail-installed', 
        type='string',
        default=None,
        dest='detail_installed',
        help="Get list of files for specified installed installable and exit.")
    parser.add_option(
        '--uninstall', 
        action='store_true',
        default=False,
        dest='uninstall',
        help="""Remove the installables specified in the arguments. Just like \
during installation, if no installables are listed then all installed \
installables are removed.""")
    parser.add_option(
        '--scp', 
        type='string',
        default='scp',
        dest='scp',
        help="Specify the path to your scp program.")

    return parser.parse_args(args)

def handle_query_args(options, config_file, installed_file):
    """
    Handle any arguments to query for information.
    Returns True if an argument was handled.
    """
    # disabled until the new argparse code is added
    return False

    # *TODO: support dryrun argument
    if options.list_installed:
        print "installed list:", installer.list_installed()
        return True

    if options.list_installables:
        print "installable list:", installer.list_installables()
        return 0
    if options.detail_installable:
        try:
            detail = installer.detail_installable(options.detail_installable)
            print "Detail on installable",options.detail_installable+":"
            pprint.pprint(detail)
        except KeyError:
            print "Installable '"+options.detail_installable+"' not found in",
            print "install file."
        return 0
    if options.detail_installed:
        try:
            detail = installer.detail_installed(options.detail_installed)
            #print "Detail on installed",options.detail_installed+":"
            for line in detail:
                print line
        except:
            raise
            print "Installable '"+options.detail_installed+"' not found in ",
            print "install file."
        return 0
    if options.list_licenses:
        print "license list:", installer.list_licenses()
        return 0
    if options.detail_license:
        try:
            detail = installer.detail_license(options.detail_license)
            print "Detail on license",options.detail_license+":"
            pprint.pprint(detail)
        except KeyError:
            print "License '"+options.detail_license+"' not defined in",
            print "install file."
        return 0
    if options.export_manifest:
        # *HACK: just re-parse the install manifest and pretty print
        # it. easier than looking at the datastructure designed for
        # actually determining what to install
        install = llsd.parse(file(options.install_filename, 'rb').read())
        pprint.pprint(install)
        return 0

def handle_edit_args(options, config_file):
    """
    Handle any arguments to update the config file contents
    Returns True if an argument was handled.
    """
    # disabled until the new argparse code is added
    return False

    if options.new_license:
        if not installer.add_license(
            options.new_license,
            text=options.license_text,
            url=options.license_url):
            return 1
    elif options.remove_license:
        installer.remove_license(options.remove_license)
    elif options.remove_installable:
        installer.remove_installable(options.remove_installable)
    elif options.add_installable:
        if not installer.add_installable(
            options.add_installable,
            copyright=options.installable_copyright,
            license=options.installable_license,
            description=options.installable_description,
            platform=options.package_platform,
            url=options.package_url,
            md5sum=options.package_md5):
            return 1
    elif options.add_installable_metadata:
        if not installer.add_installable_metadata(
            options.add_installable_metadata,
            copyright=options.installable_copyright,
            license=options.installable_license,
            description=options.installable_description):
            return 1
    elif options.add_installable_package:
        if not installer.add_installable_package(
            options.add_installable_package,
            platform=options.package_platform,
            url=options.package_url,
            md5sum=options.package_md5):
            return 1

def get_packages_to_install(installables, packages_config, installed_config, preferred_platform):

    # if no installables specified, consider all
    if not len(installables):
        installables = packages_config.packages

    # compile a subset of packages we actually need to install
    to_install = []
    for ifile in installables:
        
        toinstall_package = packages_config.package(ifile)
        installed_package = installed_config.package(ifile)

        # raise error if named package doesn't exist in packages.xml
        if not toinstall_package:
            raise RuntimeError('Unknown installable: %s' % installable)

        # work out the platform-specific or common url to use
        platform = preferred_platform
        if not toinstall_package.packagesUrl(platform):
            platform = 'common'
        if not toinstall_package.packagesUrl(platform):
           raise RuntimeError("No url specified for this platform for %s" % ifile)

        # install this package if it is new or out of date
        if installed_package == None or \
           toinstall_package.packagesUrl(platform) != installed_package.packagesUrl(platform) or \
           toinstall_package.packagesMD5(platform) != installed_package.packagesMD5(platform):
            to_install.append(ifile)

    return to_install

def check_licenses(installables, packages_config):
    """
    Return true if we have valid license info for the list of
    installables.
    """
    for ifile in installables:
        installable = packages_config.package(ifile)
        license = installable.license
        if not license:
            print >>sys.stderr, "No license info found for", ifile
            print >>sys.stderr, 'Please add the license with the',
            print >>sys.stderr, '--add-installable option. See', \
                                 sys.argv[0], '--help'
            return False
        if license not in packages_config.licenses:
            print >>sys.stderr, "Missing license info for '" + license + "'.",
            print >>sys.stderr, 'Please add the license with the',
            print >>sys.stderr, '--add-license option. See', sys.argv[0],
            print >>sys.stderr, '--help'
            return False
    return True

def do_install(installables, config_file, installed_file, preferred_platform, install_dir):
    """
    Install the specified list of installables. This will download the
    packages to the local cache, extract the contents of those
    archives to the install dir, and update the installed_file config.
    """

    # check that the install dir exists...
    if not os.path.exists(install_dir):
        os.makedirs(install_dir)

    # Filter for files which we actually requested to install.
    for ifile in installables:

        # find the url/md5 for the platform, or fallback to 'common'
        package = config_file.package(ifile)
        platform = preferred_platform
        if not package.packagesUrl(platform):
            platform = 'common'

        url = package.packagesUrl(platform)
        md5 = package.packagesMD5(platform)
        cachefile = common.getPackageInCache(url)

        # download the package, if it's not already in our cache
        if not common.isPackageInCache(url):

            # download the package to the cache
            if not common.downloadPackage(url):
                raise RuntimeError("Failed to download %s" % url)

            # error out if MD5 doesn't matches
            if not common.doesPackageMatchMD5(url, md5):
                common.removePackage(url)
                raise RuntimeError("md5 mismatch for %s" % cachefile)

        # extract the files from the package
        files = common.extractPackage(url, install_dir)

        # update the installed-packages.xml file
        package = installed_file.package(ifile)
        if not package:
            package = configfile.PackageInfo()
        package.setPackagesUrl(platform, url)
        package.setPackagesMD5(platform, md5)
        package.setPackagesFiles(platform, files)
        installed_file.setPackage(ifile, package)


def main(args):
    # parse command line options
    options, args = parse_args(args)

    # write packages into 'packages' subdir of build directory by default
    if not options.install_dir:
        import configure
        options.install_dir = configure.get_package_dir()

    # get the absolute paths to the install dir and installed-packages.xml file
    install_dir = os.path.realpath(options.install_dir)
    installed_filename = os.path.join(install_dir, options.installed_filename)

    # load the list of already installed packages
    installed = configfile.ConfigFile()
    installed.load(os.path.join(options.install_dir, installed_filename))

    # load the list of packages to install
    config = configfile.ConfigFile()
    config.load(options.install_filename)
    if config.empty:
        print "No package information to load from", options.install_filename
        return 0

    # get the list of packages to actually installed
    packages = get_packages_to_install(args, config, installed, options.platform)

    # handle any arguments to query for information
    if handle_query_args(options, config, installed):
        return 0

    # handle any arguments to query for information
    if handle_edit_args(options, config):
        return 0

    # check the licenses for the packages to install
    if not check_licenses(packages, config):
        return 1

    # do the actual install of the new/updated packages
    do_install(packages, config, installed, options.platform, install_dir)

    # *TODO: support uninstalling unused packages too?
    
    # update the installed-packages.xml file, if it was changed
    if installed.changed:
        installed.save()
    return 0
