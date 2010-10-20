# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

"""
Uninstall binary packages.

This autobuild sub-command will read an installed-packages.xml file and
uninstall the packages specified on the command line from the install
directory.

Author : Nat Goodspeed
Date   : 2010-10-19
"""

import os
import sys
import errno
import common
import logging
import configfile
import autobuild_base
from autobuild_tool_install import uninstall

logger = logging.getLogger('autobuild.uninstall')

class UninstallError(common.AutobuildError):
    pass

__help = """\
This autobuild command uninstalls package files.

The command will remove the packages specified on the command line from the
installed-packages.xml file. For each package installed from an archive (vs.
an --as_source package), it will additionally delete every file originally
installed by that archive.

Uninstalling a package installed --as_source only forgets the package's entry
in installed-packages.xml; it doesn't delete the package's source repository.
This is because there may be local source changes in that repository.
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
        '--install-dir',
        default=None,
        dest='install_dir',
        help='Where to find the previously-installed files.')

def uninstall_packages(options, args):
    # write packages into 'packages' subdir of build directory by default
    if options.install_dir:
        logger.info("specified install directory: " + options.install_dir)
    else:
        # load config file to get default install_dir
        logger.debug("loading " + options.install_filename)
        config_file = configfile.ConfigurationDescription(options.install_filename)
        options.install_dir = os.path.join(config_file.make_build_directory(), 'packages')
        logger.info("default install directory: " + options.install_dir)

    # get the absolute paths to the install dir and installed-packages.xml file
    install_dir = os.path.realpath(options.install_dir)
    # If installed_filename is already an absolute pathname, join() is smart
    # enough to leave it alone. Therefore we can do this unconditionally.
    installed_filename = os.path.join(install_dir, options.installed_filename)

    # load the list of already installed packages
    logger.debug("loading " + installed_filename)
    installed_file = configfile.ConfigurationDescription(installed_filename)

    for package in args:
        uninstall(package, installed_file, install_dir)

    # update the installed-packages.xml file
    installed_file.save()
    return 0

# define the entry point to this autobuild tool
class AutobuildTool(autobuild_base.AutobuildBase):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description='Uninstall package archives.')

    def register(self, parser):
        add_arguments(parser)

    def run(self, args):
        uninstall_packages(args, args.package)

if __name__ == '__main__':
    sys.exit("Please invoke this script using 'autobuild %s'" %
             AutobuildTool().get_details()["name"])
