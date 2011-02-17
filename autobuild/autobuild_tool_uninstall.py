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
    parser.description = "uninstall artifacts installed by the 'autobuild install' command."
    parser.add_argument(
        'package',
        nargs='*',
        help='List of packages to uninstall.')
    # Sigh, the ONLY reason we need to read the autobuild.xml file is to
    # find the default --install-dir.
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
    # The only reason we need to know --install-dir is because the default
    # --installed-manifest is relative.
    parser.add_argument(
        '--install-dir',
        default=None,
        dest='install_dir',
        help='Where to find the default --installed-manifest file.')

def uninstall_packages(options, args):
    installed_filename = options.installed_filename
    if not os.path.isabs(installed_filename):
        # Give user the opportunity to avoid reading AUTOBUILD_CONFIG_FILE by
        # specifying a full pathname for --installed-manifest. This logic
        # handles the (usual) case when installed_filename is relative to
        # install_dir. Therefore we must figure out install_dir.
        install_dir = options.install_dir
        if install_dir:
            logger.info("specified install directory: " + install_dir)
        else:
            # load config file to get default install_dir
            logger.debug("loading " + options.install_filename)
            config_file = configfile.ConfigurationDescription(options.install_filename)
            install_dir = os.path.join(config_file.make_build_directory(), 'packages')
            logger.info("default install directory: " + install_dir)

        # get the absolute path to the installed-packages.xml file
        installed_filename = os.path.realpath(os.path.join(install_dir, installed_filename))

    # load the list of already installed packages
    logger.debug("loading " + installed_filename)
    installed_file = configfile.ConfigurationDescription(installed_filename)

    for package in args:
        uninstall(package, installed_file)

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
