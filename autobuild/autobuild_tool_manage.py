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
DEFAULT_CONFIG_CMD=''
DEFAULT_BUILD_CMD=''

class AutobuildTool(AutobuildBase):

    _ARGUMENTS = {
        'configure':   ['name', 'platform', 'cmd'], 
        'build':   ['name', 'platform', 'cmd'], 
        'package': ['descripition', 'copyright', 'license', 'license_file', 'source', 
                    'source_type', 'source_directory', 'version', 'patches', 'platforms'],
        }

    def get_details(self):
        return dict(name=self.name_from_file(__file__),
            description="Manage build and package configuration.")
     
    def register(self, parser):
        parser.add_argument('--config-file',
            dest='config_file',
            default=configfile.AUTOBUILD_CONFIG_FILE,
            help="")
        parser.add_argument('command', nargs='?', default='print',
            help="commands: bootstrap, build, configure, package, or print")
        parser.add_argument('argument', nargs='*', help=_arg_help_str(self._ARGUMENTS))

    def run(self, args):
        config = configfile.ConfigurationDescription(args.config_file)
        arg_dict = _process_key_value_arguments(args.argument)
        if not arg_dict:  # if no parameters provided, default to interactive
            interactive = True
            print "No arguments given. Entering interactive mode..."
        cmd_instance = None
        if args.command == 'bootstrap':
            print "Entering interactive mode."
            self.interactive_mode(Build(config))
            self.interactive_mode(Configure(config))
            self.interactive_mode(Package(config))
        elif args.command == 'build':
            cmd_instance = Build(config)
        elif args.command == 'configure':
            cmd_instance = Configure(config)
        elif args.command == 'package':
            cmd_instance = Package(config)
        elif args.command == 'print':
            print config
        elif not interactive:
            raise AutobuildError('unknown command %s' % args.command)

        if cmd_instance:
            if interactive:
                self.interactive_mode(cmd_instance)
            else:
                cmd_instance.run(**arg_dict)

        if not args.dry_run and args.command != 'print':
            config.save()


def _arg_help_str(arg_dict):
    s = []
    for (key, value) in arg_dict.items():
        s.append('%s: %s' % (key, value))
    return '\n'.join(s)


class InteractiveCommand(object):
    """
    Class describing characteristics of a particular command.

    Should contain:
        description  description for interactive mode
        help         additional help text for interactive mode
        run          method used to run this command
    """

    def __init__(self, config):
        _desc = ["Current settings:",] 
        _desc.append('%s' % config)
        self.description = '\n'.join(_desc)
        self.help = "Enter new or modified configuration values."
        self.config = config


class _config(InteractiveCommand):

    def __init__(self, config):
        _desc = ["Current configure and build settings:",] 
        _desc.append('%s' % config.platform_configurations)
        self.description = '\n'.join(_desc)
        self.help = "Enter name of existing configuration to modify, or new name to create a new configuration."
        self.config = config

    def _create_build_config_desc(self, config, name, platform, cmd):
        if not name:
            raise AutobuildError('build configuration name not given')
        
        build_config_desc = configfile.BuildConfigurationDescription()
        platform_description = configfile.PlatformDescription()
        platform_description.configurations[name] = build_config_desc
        config.platform_configurations[platform] = platform_description
        return build_config_desc


class Build(_config):

    def run(self, platform=get_current_platform(), name=CONFIG_NAME_DEFAULT, 
              cmd=DEFAULT_BUILD_CMD):
        """
        Updates the build command.
        """
        build_config_desc = self._create_build_config_desc(self.config, name, platform, cmd)
        build_config_desc.build = cmd


class Configure(_config):

    def run(self, platform=get_current_platform(), name=CONFIG_NAME_DEFAULT, 
                  cmd=DEFAULT_CONFIG_CMD):
        """
        Updates the configure command.
        """
        build_config_desc = self._create_build_config_desc(self.config, name, platform, cmd)
        build_config_desc.configure = cmd


class Package(InteractiveCommand):

    def __init__(self, config):
        _desc = ['Current package settings',]
        _desc.append('%s' % config.package_description)
        self.description = '\n'.join(_desc)
        self.config = config

    def run(self, **kwargs):
        """
        Configure packaging details as necessary to build a package.
        """
        pkg = configfile.PackageDescription(kwargs)
        self.config.package_description = pkg


def _process_key_value_arguments(arguments):
    dictionary = {}
    for argument in arguments:
        try:
            key, value = argument.split('=')
            dictionary[key] = value
        except ValueError:
            print >> sys.stderr, 'ignoring malformed argument', argument
    return dictionary



