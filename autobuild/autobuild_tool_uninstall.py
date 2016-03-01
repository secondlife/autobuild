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
installed-packages.xml file, and delete every file originally
installed by that archive.
"""


def uninstall_packages(options, installed_filename, args, dry_run):
    # load the list of already installed packages
    logger.debug("loading " + installed_filename)
    installed_file = configfile.Dependencies(installed_filename)

    for package in args:
        if not dry_run:
            uninstall(package, installed_file)
        else:
            logger.info("would have uninstalled %s" % package)

    # update the installed-packages.xml file
    if not dry_run:
        installed_file.save()
    return 0


# define the entry point to this autobuild tool
class AutobuildTool(autobuild_base.AutobuildBase):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description='Uninstall package archives.')

    def register(self, parser):
        parser.description = "uninstall artifacts installed by the 'autobuild install' command."
        parser.add_argument('package',
                            nargs='*',
                            help='List of packages to uninstall.')
        # Sigh, the ONLY reason we need to read the autobuild.xml file is to
        # find the default --install-dir.
        parser.add_argument('--config-file',
                            default=configfile.AUTOBUILD_CONFIG_FILE,
                            dest='install_filename',
                            help="The file used to describe what should be installed\n  (defaults to $AUTOBUILD_CONFIG_FILE or \"autobuild.xml\").")
        parser.add_argument('--installed-manifest',
                            default=configfile.INSTALLED_CONFIG_FILE,
                            dest='installed_filename',
                            help='The file used to record what is installed.')
        # The only reason we need to know --install-dir is because the default
        # --installed-manifest is relative.
        parser.add_argument('--install-dir',
                            default=None,
                            dest='select_dir',          # see common.select_directories()
                            help='Where to find the default --installed-manifest file.')
        parser.add_argument('--all', '-a',
                            dest='all',
                            default=False,
                            action="store_true",
                            help="uninstall packages for all configurations")
        parser.add_argument('--configuration', '-c',
                            nargs='?',
                            action="append",
                            dest='configurations',
                            help="uninstall packages for a specific build configuration\n(may be specified as comma separated values in $AUTOBUILD_CONFIGURATION)",
                            metavar='CONFIGURATION',
                            default=self.configurations_from_environment())

    def run(self, args):
        installed_filename = args.installed_filename
        if os.path.isabs(installed_filename):
            installed_filenames = [installed_filename]
        else:
            # Give user the opportunity to avoid reading AUTOBUILD_CONFIG_FILE by
            # specifying a full pathname for --installed-manifest. Make a
            # 'config' object that only actually loads the config file if we
            # try to use it by accessing an attribute.
            class LazyConfig(object):
                def __init__(self, filename):
                    self.filename = filename
                    self.config = None

                def __getattr__(self, attr):
                    if self.config is None:
                        logger.debug("loading " + self.filename)
                        self.config = configfile.ConfigurationDescription(self.filename)
                    return getattr(self.config, attr)

            # This logic handles the (usual) case when installed_filename is
            # relative to install_dir. Therefore we must figure out install_dir.

            # write packages into 'packages' subdir of build directory by default
            config = LazyConfig(args.install_filename)
            installed_filenames = \
                [os.path.realpath(os.path.join(install_dir, installed_filename))
                 for install_dir in
                 common.select_directories(args, config,
                                           "install", "uninstalling",
                                           lambda cnf:
                                           os.path.join(config.make_build_directory(cnf, dry_run=args.dry_run),
                                                        "packages"))]

        logger.debug("installed filenames: %s" % installed_filenames)
        for installed_filename in installed_filenames:
            uninstall_packages(args, installed_filename, args.package, args.dry_run)

if __name__ == '__main__':
    sys.exit("Please invoke this script using 'autobuild %s'" %
             AutobuildTool().get_details()["name"])
