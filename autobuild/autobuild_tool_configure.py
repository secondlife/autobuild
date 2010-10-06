#!/usr/bin/env python
# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$


import autobuild_base
import common
from common import AutobuildError
import configfile


class ConfigurationError(AutobuildError):
    pass


class autobuild_tool(autobuild_base.autobuild_base):
    def get_details(self):
        return dict(name='configure',
            description="Configures platform targets.")
     
    def register(self, parser):
        parser.add_argument('--config-file',
            dest='config_file',
            default=configfile.AUTOBUILD_CONFIG_FILE,
            help="")
        parser.add_argument('--configuration', '-c', nargs='?', action="append", dest='configurations', 
            help="build a specific build configuration", metavar='CONFIGURATION')
        parser.add_argument('additional_options', nargs="*", metavar='OPT',
            help="an option to pass to the configuration command" )
        parser.usage = "%(prog)s [-h] [--dry-run] [-c CONFIGURATION] [--config-file FILE] [-- OPT [OPT ...]]"

    def run(self, args):
        if args.dry_run:
            return
        config = configfile.ConfigurationDescription(args.config_file)
        if args.configurations is not None:
            for build_configuration_name in args.configurations:
                result = configure(config, build_configuration_name, args.additional_options)
                if result != 0:
                    raise ConfigurationError("building configuration '%s' returned '%d'" % 
                        (build_configuration_name, result))
        else:
            for build_configuration in config.get_default_build_configurations():
                result = _configure_a_configuration(build_configuration, args.additional_options)
                if result != 0:
                    raise ConfigurationError("default configuration returned '%d'" % (result))


def configure(config, build_configuration_name, extra_arguments=[]):
    """
    Execute the platform configure command for the named build configuration.
    """
    build_configuration = config.get_build_configuration(build_configuration_name)
    return _configure_a_configuration(build_configuration, extra_arguments)


def _configure_a_configuration(build_configuration, extra_arguments):
    if build_configuration.configure is not None:
        return build_configuration.configure(extra_arguments)
    else:
        return 0
