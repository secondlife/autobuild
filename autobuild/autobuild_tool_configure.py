#!/usr/bin/env python
# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$


import argparse
import os
import sys

import autobuild_base
import common
from common import AutobuildError
import configfile
import re


class autobuild_tool(autobuild_base.autobuild_base):
    def get_details(self):
        return dict(name='configure',
            description="Run the configuration script.")
     
    def register(self, parser):
        parser.add_argument('file', default=configfile.AUTOBUILD_CONFIG_FILE, nargs='?',
            help='The configuration file to use')
        parser.add_argument('additional_options', nargs="*", metavar='OPT',
            help="an option to pass to the configuration command" )
        parser.usage = "%(prog)s [-h] [--dry-run] [file] [-- OPT [OPT ...]]"

    def run(self, args):
        config = configfile.ConfigFile()
        if args.file[0] == '-':
            cfile = configfile.AUTOBUILD_CONFIG_FILE
            if args.additional_options:
                args.additional_options.insert(args.file, 0)
            else:
                args.additional_options = [args.file]
        else:
            cfile = args.file
        if config.load(cfile) is False:
            raise ConfigurationFileNotFoundError("configuration file '%s' not found" % args.file)
        packageInfo = config.package_definition
        if packageInfo is None:
            raise PlatformNotConfiguredError("no configuration is defined")
        configureCommand = packageInfo.configure_command(common.get_current_platform())
        if configureCommand is None:
            raise NoConfigurationCommandError("no configure command specified")
        command = configureCommand + ' ' + ' '.join(args.additional_options)
        os.environ['AUTOBUILD_CONFIG_DIR'] = os.path.dirname(config.filename)
        os.environ['AUTOBUILD_CONFIG_FILE'] = os.path.basename(config.filename)
        os.system(command)


class NoConfigurationCommandError(AutobuildError):
    pass


class ConfigurationFileNotFoundError(AutobuildError):
    pass


class PlatformNotConfiguredError(AutobuildError):
    pass
