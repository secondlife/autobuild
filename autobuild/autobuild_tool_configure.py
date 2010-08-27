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


class autobuild_tool(autobuild_base.autobuild_base):
    def get_details(self):
        return dict(name='configure',
            description="Run the configuration script.")
     
    def register(self, parser):
        parser.add_argument('file', default=configfile.AUTOBUILD_CONFIG_FILE, nargs='?',
            help='The configuration file to use')

    def run(self, args):
        config = configfile.ConfigFile()
        if config.load(args.file) is False:
            raise ConfigurationFileNotFoundError("configuration file '%s' not found" % args.file)
        packageInfo = config.package_definition
        if packageInfo is None:
            raise PlatformNotConfiguredError("no configuration is defined")
        configureCommand = packageInfo.configure_command(common.get_current_platform())
        if configureCommand is None:
            raise NoConfigurationCommandError("no configure command specified")
        os.system(configureCommand)


class NoConfigurationCommandError(AutobuildError):
    pass


class ConfigurationFileNotFoundError(AutobuildError):
    pass


class PlatformNotConfiguredError(AutobuildError):
    pass
