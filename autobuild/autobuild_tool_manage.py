#!/usr/bin/env python
# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

"""
Provides tools for manipulating build and packaging configuration.

Build configuration includes:
    - set the configure command
    - set the build command
    - parameterize the package that is built
"""

import sys
import configfile
from autobuild_base import AutobuildBase
from common import AutobuildError, get_current_platform

CONFIG_NAME_DEFAULT='default'
DEFAULT_CONFIG_CMD='make configure'
DEFAULT_BUILD_CMD='make'

class AutobuildTool(AutobuildBase):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
            description="Manage build and package configuration.")
     
    def register(self, parser):
        parser.add_argument('--config-file',
            dest='config_file',
            default=configfile.AUTOBUILD_CONFIG_FILE,
            help="")
        parser.add_argument(
            '-i','--interactive', 
            action='store_true',
            default=False,
            dest='interactive',
            help="run as an interactive session")
        parser.add_argument('command', nargs='?', default='print',
            help="commands: build, configure, package, or print")
        parser.add_argument('argument', nargs='*', help=_arg_help_str(_ARGUMENTS))

    def run(self, args):
        config = configfile.ConfigurationDescription(args.config_file)
        arg_dict = _process_key_value_arguments(args.argument)
        if args.interactive:
            print >> sys.stderr, "interactive mode not implemented"
            return
        if args.command == 'build':
            build(config, **arg_dict)
        elif args.command == 'configure':
            configure(config, **arg_dict)
        elif args.command == 'package':
            package(config, **arg_dict)
        elif args.command == 'print':
            print config
        else:
            raise AutobuildError('unknown command %s' % args.command)
        if not args.dry_run and args.command != 'print':
            config.save()


_ARGUMENTS = {
    'configure':   ['name', 'platform', 'cmd'], 
    'build':   ['name', 'platform', 'cmd'], 
    'package': ['descripition', 'copyright', 'license', 'license_file', 'source', 
                'source_type', 'source_directory', 'version', 'patches', 'platforms'],
}

def _arg_help_str(arg_dict):
    s = []
    for (key, value) in arg_dict.items():
        s.append('%s: %s' % (key, value))
    return '\n'.join(s)


def build(config, platform=get_current_platform(), name=CONFIG_NAME_DEFAULT, 
          cmd=DEFAULT_BUILD_CMD):
    """
    Updates the build command.
    """
    build_config_desc = _create_build_config_desc(config, name, platform, cmd)
    build_config_desc.build = cmd

def configure(config, platform=get_current_platform(), name=CONFIG_NAME_DEFAULT, 
              cmd=DEFAULT_CONFIG_CMD):
    """
    Updates the configure command.
    """
    build_config_desc = _create_build_config_desc(config, name, platform, cmd)
    build_config_desc.configure = cmd

def _create_build_config_desc(config, name, platform, cmd):
    if not name:
        raise AutobuildError('build configuration name not given')
    
    build_config_desc = configfile.BuildConfigurationDescription()
    platform_description = configfile.PlatformDescription()
    platform_description.configurations[name] = build_config_desc
    config.platform_configurations[platform] = platform_description
    return build_config_desc

def package(config, **kwargs):
    """
    Configure packaging details as necessary to build a package.
    """
    pkg = configfile.PackageDescription(kwargs)
    config.package_description = pkg

def _process_key_value_arguments(arguments):
    dictionary = {}
    for argument in arguments:
        try:
            key, value = argument.split('=')
            dictionary[key] = value
        except ValueError:
            print >> sys.stderr, 'ignoring malformed argument', argument
    return dictionary



