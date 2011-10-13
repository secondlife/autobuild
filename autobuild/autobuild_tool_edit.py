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
        parser.description = "edit the definition of the current package, for specifying the commands to run for the various build steps (configure and build subcommands), versioning and licensing information (package and source-info subcommands), etc."
        subparsers = parser.add_subparsers(title='subcommands', dest='subparser_name')

        for (cmd,callable) in self._get_command_callables().items():
            parser = subparsers.add_parser(cmd, help=callable.HELP, formatter_class=argparse.RawTextHelpFormatter)
            parser.add_argument('argument', 
                nargs='*', 
                help=_arg_help_str(callable.ARGUMENTS, callable.ARG_DICT))
            parser.add_argument('--delete', 
                action='store_true')
            parser.add_argument('--config-file',
                dest='config_file',
                default=configfile.AUTOBUILD_CONFIG_FILE,
                help='(defaults to $AUTOBUILD_CONFIG_FILE or "autobuild.xml")')
            parser.set_defaults(func=callable.run_cmd)

    def run(self, args):
        config = configfile.ConfigurationDescription(args.config_file)
        arg_dict = _process_key_value_arguments(args.argument)

        args.func(config, arg_dict, args.delete)

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
                                'archive':      Archive,
                                'configure':    Configure,
                                'build':        Build,
                                'package':      Package,
                                'platform':     Platform,
                                'source-info':  SourceInfo,
                            }
        return self.arguments


def _arg_help_str(args, arg_dict):
    s = []
    for key in args: 
        s.append('%s%s' % (key.ljust(20), arg_dict[key]['help']))
    return '\n'.join(s)


class _config(InteractiveCommand):

    ARGUMENTS = ['name', 'platform', 'command', 'options', 'arguments', 'filters', 'default']

    ARG_DICT = {    'name':     {'help':'Name of config'}, 
                    'platform': {'help':'Platform of config'},
                    'command':  {'help':'Command to execute'}, 
                    'options':  {'help':'Options for command'},
                    'arguments':{'help':'Arguments for command'},
                    'filters':  {'help':'Filter command output'},
                    'default':  {'help':'Run by default'},
                }

    def __init__(self, config):
        stream = StringIO()
        stream.write("Current configure and build settings:\n")
        configfile.pretty_print(config.get_all_platforms(), stream) 
        self.description = stream.getvalue()
        stream.close()
        stream = StringIO()
        stream.write("Use commas to separate items in options and arguments fields")
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

    def delete(self, name='', platform='', **kwargs):
        """
        Delete the named config value.
        """
        if not name:
            raise AutobuildError("Name argument must be provided with --delete option.")

    def _get_configuration(self, name='', platform=''):
        if not name or not platform:
            raise AutobuildError("'name' and 'platform' arguments must both be provided with --delete option.")
        platform_description = self.config.get_platform(platform)
        configuration = platform_description.configurations.get(name)
        return configuration

class Build(_config):

    HELP = "Configure 'autobuild build'"

    def run(self, platform=get_current_platform(), name=CONFIG_NAME_DEFAULT, 
              command=DEFAULT_BUILD_CMD, options='', arguments='', default=None):
        """
        Updates the build command.
        """
        new_command = { 'command':command, 
                        'options':listify_str(options), 
                        'arguments':listify_str(arguments)}
        build_config_desc = self.create_or_update_build_config_desc(name, platform, default=default, build=new_command) 

    def delete(self, name='', platform='', **kwargs):
        """
        Delete the named config value.
        """
        print "Deleting entry."
        configuration = self._get_configuration(name, platform)
        configuration.pop('build')


class Configure(_config):

    HELP = "Configure 'autobuild configure'"

    def run(self, platform=get_current_platform(), name=CONFIG_NAME_DEFAULT, 
                  command=DEFAULT_CONFIG_CMD, options='', arguments='', default=None):
        """
        Updates the configure command.
        """
        new_command = { 'command':command, 
                        'options':listify_str(options), 
                        'arguments':listify_str(arguments)}
        build_config_desc = self.create_or_update_build_config_desc(name, platform, default=default, configure=new_command)

    def delete(self, name='', platform='', **kwargs):
        """
        Delete the named config value.
        """
        print "Deleting entry."
        configuration = self._get_configuration(name, platform)
        configuration.pop('configure')


class Platform(InteractiveCommand):

    ARGUMENTS = ['name', 'build_directory',]

    ARG_DICT = {    'name':             {'help':'Name of platform'}, 
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

    def run(self, name='', build_directory=None):
        """
        Configure basic platform details.
        """
        self._create_or_update_platform(name, build_directory)
        
    def delete(self, name='', **kwargs):
        """
        Delete the named config value.
        """
        if not name:
            raise AutobuildError("'name' argument must be provided with --delete option.")
        print "Deleting entry."
        self.config.package_description.platforms.pop(name)


class Archive(InteractiveCommand):

    ARGUMENTS = ['format', 'hash_algorithm', 'platform']

    ARG_DICT = {    'format':             {'help':'Archive format (e.g zip or tbz2)'}, 
                    'hash_algorithm':  {'help':'The algorithm for computing the archive hash (e.g. md5)'},
                    'platform': {'help':'The name of the platform archive to be configured'}
                }

    HELP = "Platform-specific archive configuration"

    def __init__(self, config):
        stream = StringIO()
        stream.write("Current platform archive settings:\n")
        archives = {}
        for platform, description in config.get_all_platforms().iteritems():
            if description.archive is not None:
                archives[platform] = description.archive
        configfile.pretty_print(archives, stream)
        self.description = stream.getvalue()
        stream.close()
        self.config = config

    def _create_or_update_platform_archive(self, platform, format, hash_algorithm):
        try:
            platform_description = self.config.get_platform(platform)
        except configfile.ConfigurationError:
            platform_description = configfile.PlatformDescription({'name': platform})
            self.config.package_description.platforms[platform] = platform_description
        if platform_description.archive is None:
            platform_description.archive = configfile.ArchiveDescription()
        platform_description.archive.format = format
        platform_description.archive.hash_algorithm = hash_algorithm

    def run(self, platform=get_current_platform(), format=None, hash_algorithm=None):
        """
        Configure platform archive details.
        """
        self._create_or_update_platform_archive(platform, format, hash_algorithm)
        
    def delete(self, platform=get_current_platform(), **kwargs):
        """
        Delete the named config value.
        """
        print "Deleting %s archive entry." % platform
        platform_description = self.config.get_platform(platform)
        if platform_description is not None:
            platform_description.archive = None


class _package(InteractiveCommand):

    def __init__(self, config):
        stream = StringIO()
        stream.write("Current package settings:\n")
        configfile.pretty_print(config.package_description, stream)
        self.description = stream.getvalue()
        stream.close()

        self.config = config

        self.interactive_delete = False

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

    def non_interactive_delete(self, **kwargs):
        self.delete(**kwargs)


class Package(_package):

    ARGUMENTS = ['name', 'description', 'copyright', 'license', 'license_file',
                 'version',]

    ARG_DICT = {    'name':             {'help':'Name of package'},
                    'description':      {'help':'Package description'},
                    'copyright':        {'help':'Copyright string (as appropriate for your package)'},
                    'license':          {'help':'Type of license (as appropriate for your package)'},
                    'license_file':     {'help':'Path to license file relative to package root, if known'},
                    'version':          {'help':'Version'},
                }

    HELP = "Information about the package"

    def delete(self, name='', platform='', **kwargs):
        """
        Delete the named config value.
        """
        if self._confirm_delete():
            really_really_delete = raw_input("Do you really really want to delete this entry?\nThis will delete everything in the config file except the installables. (y/[n])> ")
            if really_really_delete in ['y', 'Y', 'yes', 'Yes', 'YES']:
                print "Deleting entry."
                self.config.package_description = None
                return
        print "Cancelling delete."


class SourceInfo(_package):

    ARGUMENTS = ['source', 'source_type', 'source_directory',]

    ARG_DICT = {    
                    'source':           {'help':'Source URL for code repository'},
                    'source_type':      {'help':'Repository type (hg, svn, etc.)'},
                    'source_directory': {'help':'Location to which source should be installed, relative to autobuild.xml'},
                }

    HELP = "Information about the package source, for installation as source by other packages."


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
