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
import shlex
from StringIO import StringIO
import argparse

import configfile
from autobuild_base import AutobuildBase
from common import AutobuildError, get_current_platform
from interactive import InteractiveCommand

CONFIG_NAME_DEFAULT='default'
DEFAULT_CONFIG_CMD=''
DEFAULT_BUILD_CMD=''

class AutobuildTool(AutobuildBase):

    def get_details(self):
        return dict(name=self.name_from_file(__file__),
            description="Manage build and package configuration.")
     
    def register(self, parser):
        parser.add_argument('--config-file',
            dest='config_file',
            default=configfile.AUTOBUILD_CONFIG_FILE,
            help="")
        parser.add_argument('--bootstrap',
            action='store_true')
        parser.add_argument('--delete',
            action='store_true')
        subparsers = parser.add_subparsers(title='subcommands', dest='subparser_name')
        
        for (cmd,callable) in self._get_command_callables().items():
            parser = subparsers.add_parser(cmd, help=callable.HELP, formatter_class=argparse.RawTextHelpFormatter)
            parser.add_argument('argument', nargs='*', 
                                help=_arg_help_str(callable.ARGUMENTS, callable.ARG_DICT))
            parser.set_defaults(func=callable.run_cmd)

    def run(self, args):
        config = configfile.ConfigurationDescription(args.config_file)
        if args.bootstrap:
            print "Entering interactive mode."
            Package(config).interactive_mode()
            Configure(config).interactive_mode()
            Build(config).interactive_mode()
        
        arg_dict = _process_key_value_arguments(args.argument)
        args.func(config, arg_dict)

        if not args.dry_run and args.subparser_name != 'print':
            config.save()

    def _get_command_callables(self):
        """
        Lazily create arguments dict.
        """
        try:
            self.arguments
        except AttributeError:
            self.arguments = {
                                'configure':    Configure,
                                'build':        Build,
                                'package':      Package,
                                'platform':     Platform,
                            }
        return self.arguments


def _arg_help_str(args, arg_dict):
    s = []
    for key in args: 
        s.append('%s%s' % (key.ljust(20), arg_dict[key]['help']))
    return '\n'.join(s)


class _config(InteractiveCommand):

    ARGUMENTS = ['name', 'platform', 'cmd', 'options', 'arguments',]

    ARG_DICT = {   'name':     {'help':'Name of config to create or edit'}, 
                    'platform': {'help':'Platform of config'},
                    'cmd':      {'help':'Command to execute'}, 
                    'options':  {'help':'Options for command'},
                    'arguments':{'help':'Arguments for command'},
                }

    def __init__(self, config):
        stream = StringIO()
        stream.write("Current configure and build settings:\n")
        configfile.pretty_print(config.get_all_platforms(), stream) 
        self.description = stream.getvalue()
        stream.close()
        stream = StringIO()
        stream.write("Enter name of existing configuration to modify, or new name to create a new configuration.")
        stream.write("\nUse commas to speparate independent options and arguments.")
        self.help = stream.getvalue()
        self.config = config

    def _create_build_config_desc(self, config, name, platform, build, configure):
        if not name:
            raise AutobuildError('build configuration name not given')
        
        init_dict = dict({'build': build, 'configure': configure, 'name': name})
        build_config_desc = configfile.BuildConfigurationDescription(init_dict)
        try:
            platform_description = config.get_platform(platform)
        except configfile.ConfigurationError:
            platform_description = configfile.PlatformDescription()
            platform_description.name = platform
        platform_description.configurations[name] = build_config_desc
        config.package_description.platforms[platform] = platform_description
        return build_config_desc

    def create_or_update_build_config_desc(self, name, platform, default=None, build=None, configure=None):
        # fetch existing value if there is one
        cmds = dict([tuple for tuple in [('build', build), ('configure', configure)] if tuple[1]])
        try:
            build_config_desc = self.config.get_build_configuration(name, platform)
            for name in build_config_desc.build_steps:
                build_config_desc.update(cmds)
        except configfile.ConfigurationError:
            build_config_desc = self._create_build_config_desc(self.config, name, platform, build, configure)
        if default is not None:
            build_config_desc.default = default
        return build_config_desc 


class Build(_config):

    HELP = "The build command 'autobuild build'"

    def run(self, platform=get_current_platform(), name=CONFIG_NAME_DEFAULT, 
              cmd=DEFAULT_BUILD_CMD, options='', arguments='', default=None):
        """
        Updates the build command.
        """
        command = { 'command':cmd, 
                    'options':listify_str(options), 
                    'arguments':listify_str(arguments)}
        build_config_desc = self.create_or_update_build_config_desc(name, platform, default=default, build=command) 


class Configure(_config):

    HELP = "The configure command 'autobuild configure'"

    def run(self, platform=get_current_platform(), name=CONFIG_NAME_DEFAULT, 
                  cmd=DEFAULT_CONFIG_CMD, options='', arguments='', default=None):
        """
        Updates the configure command.
        """
        command = { 'command':cmd, 
                    'options':listify_str(options), 
                    'arguments':listify_str(arguments)}
        build_config_desc = self.create_or_update_build_config_desc(name, platform, default=default, configure=command)


class Platform(InteractiveCommand):

    ARGUMENTS = ['name', 'build_directory',]

    ARG_DICT = {   'name':             {'help':'Name of platform to edit'}, 
                    'build_directory':  {'help':'Build directory'},
                }

    HELP = "Platform-specific configuration"

    def __init__(self, config):
        stream = StringIO()
        stream.write("Current platform settings:\n")
        configfile.pretty_print(config.get_all_platforms(), stream)
        self.description = stream.getvalue()
        stream.close()
        self.config = config
        
    def _create_or_update_platform(self, name, build_directory):
        try:
            platform_description = self.config.get_platform(name)
        except configfile.ConfigurationError:
            platform_description = configfile.PlatformDescription({'name': name})
            self.config.package_description.platforms[name] = platform_description
        if build_directory is not None:
            platform_description.build_directory = build_directory

    def run(self, name, build_directory=None):
        """
        Configure basic platform details.
        """
        self._create_or_update_platform(name, build_directory)
        

class Package(InteractiveCommand):

    ARGUMENTS = ['name', 'description', 'copyright', 'license', 'license_file', 
                 'source', 'source_type', 'source_directory', 'version',]

    ARG_DICT = {    'name':             {'help':'Name of package'}, 
                    'description':      {'help':'Package description'},
                    'copyright':        {'help':'Copyright string'}, 
                    'license':          {'help':'Type of license'},
                    'license_file':     {'help':'Full path to license file'},
                    'source':           {'help':'Source'},
                    'source_type':      {'help':'Source type'},
                    'source_directory': {'help':'Location of source directory'},
                    'version':          {'help':'Version'},
                }

    HELP = "Information about the package"

    def __init__(self, config):
        stream = StringIO()
        stream.write("Current package settings:\n")
        configfile.pretty_print(config.package_description, stream)
        self.description = stream.getvalue()
        stream.close()

        self.config = config

    def create_or_update_package_desc(self, kwargs):
        # fetch existing value if there is one
        try:
            package_desc = self.config.package_description
            package_desc.update(kwargs)
        except AttributeError:
            package_desc = configfile.PackageDescription(kwargs)
        return package_desc 

    def run(self, **kwargs):
        """
        Configure packaging details as necessary to build a package.
        """
        pkg = self.create_or_update_package_desc(kwargs)
        self.config.package_description = pkg


def _process_key_value_arguments(arguments):
    dictionary = {}
    for argument in arguments:
        try:
            key, value = argument.split('=', 1)
            dictionary[key] = value
        except ValueError:
            print >> sys.stderr, 'ignoring malformed argument', argument
    return dictionary


def listify_str(str):
    list = str.split(',')
    list = [p.strip() for p in list if p.strip()]
    return list
