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
Provides tools for manipulating package installables.

Installables are package descriptions which describe dowloadable archives
that may installed by autobuild.
"""

import sys
import os
import pprint
import re
import logging

import common
import configfile
import autobuild_base
from autobuild_tool_install import get_package_file, get_metadata_from_package

logger = logging.getLogger('autobuild.installables')


# Match key=value arguments.
_key_value_regexp = re.compile(r'(\w+)\s*=\s*(\S+)')


class InstallablesError(common.AutobuildError):
    pass


class AutobuildTool(autobuild_base.AutobuildBase):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description="Manipulate installable package entries in the autobuild configuration.")
     
    def register(self, parser):
        parser.description = "specify installables as dependencies of the current pacakge for use by the 'autobuild install' command."
        parser.add_argument('--config-file',
                            dest='config_file',
                            default=configfile.AUTOBUILD_CONFIG_FILE,
                            help='(defaults to $AUTOBUILD_CONFIG_FILE or "autobuild.xml")')
        parser.add_argument('-a', '--archive',
                            dest='archive',
                            default=None,
                            help="infer installable attributes from the given archive")
        parser.add_argument('command', nargs='?', default='print',
                            help="installable command: add, remove, edit, or print")
        parser.add_argument('name', nargs='?', default=None,
                            help="the name of the installable")
        parser.add_argument('argument', nargs='*', help='a key=value pair specifying an attribute')

        parser.epilog = """EXAMPLES:\n
  autobuild edit --archive http://downloads.example.com/packages/foo-2.3.4-darwin-12345.zip
     Modifies the current configuration to replace package 'foo' for platform 'darwin'.
     This method is the most reliable iff the specified package contains metadata.

  autobuild add foo platform=linux hash=d3b07384d113edec49eaa6238ad5ff00 \
            url=http://downloads.example.com/packages/foo-2.3.4-linux-12345.zip
     Adds the specified package url using explicit package name, platform, and hash values.
     The specified values must agree with the metadata in the package if it is present, 
     and with the construction of the package file name."""


    def run(self, args):
        config = configfile.ConfigurationDescription(args.config_file)
        if args.command == 'add':
            add(config, args.name, args.archive, args.argument)
        elif args.command == 'edit':
            edit(config, args.name, args.archive, args.argument)
        elif args.command == 'remove':
            remove(config, args.name)
        elif args.command == 'print':
            print_installable(config, args.name)
        else:
            raise InstallablesError('unknown command %s' % args.command)
        if not args.dry_run and args.command != 'print':
            config.save()


_PACKAGE_ATTRIBUTES = ['description', 'copyright', 'license', 'license_file', 'version']
_ARCHIVE_ATTRIBUTES = ['hash', 'hash_algorithm', 'url']


def _dict_from_key_value_arguments(arguments):
    dictionary = {}
    for argument in arguments:
        match = _key_value_regexp.match(argument.strip())
        if match:
            dictionary[match.group(1)] = match.group(2)
        else:
            logger.warning('ignoring malformed argument ' + argument)
    return dictionary

def _get_new_metadata(config, args_name, args_archive, arguments):
    # Get any name/value pairs from the command line
    key_values=_dict_from_key_value_arguments(arguments)
    
    if args_archive and 'url' in key_values:
      raise InstallablesError("--archive (%s) and url (%s) may not both be specified" \
                              % (args_archive, key_values['url']))
    if args_archive:
        archive_path = args_archive.strip()
    elif 'url' in key_values:
        archive_path = key_values.pop('url')
    else:
        archive_path = None
    archive_file = None
    if archive_path:
        if _is_uri(archive_path):
            archive_url = archive_path
        else:
            archive_url = 'file://'+config.absolute_path(archive_path)
        archive_file = get_package_file(args_name, archive_url, 
                                        hash_algorithm=key_values.get('hash_algorithm','md5'),
                                        expected_hash=key_values.get('hash',None))
        if archive_file:
            metadata = get_metadata_from_package(archive_file)
            metadata.archive = configfile.ArchiveDescription()
            metadata.archive.url = archive_url
            if 'hash' not in key_values:
                logger.warning("No hash specified, computing from %s" % archive_file)
                metadata.archive['hash'] = common.compute_md5(archive_file)
                metadata.archive['hash_algorithm'] = 'md5'

    if archive_file is None:
        logger.warning("Archive not downloaded; some integrity checks may not work")
        metadata = configfile.MetadataDescription(create_quietly=True)
        metadata.package_description = configfile.PackageDescription(dict(name=args_name))
        metadata.archive = configfile.ArchiveDescription()
        metadata.archive.url = archive_path

    package_name = _check_name(args_name, key_values, metadata)
    if metadata.package_description['name'] is None:
          metadata.package_description['name'] = package_name

    for description_key in _PACKAGE_ATTRIBUTES:
        if description_key in key_values:
            logger.warning("specifying '%s' in the installable is no longer required\n  if it is in the package metadata"
                           % description_key)
            if description_key in metadata.package_description \
              and metadata.package_description[description_key] is not None \
              and key_values[description_key] != metadata.package_description[description_key]:
                raise InstallablesError("command line %s (%s) does not match archive %s (%s)" \
                                        % (description_key, key_values[description_key], 
                                           description_key, metadata.package_description[description_key]))
            else:
                metadata.package_description[description_key] = key_values.pop(description_key)
        
    for archive_key in _ARCHIVE_ATTRIBUTES:
        if archive_key in key_values:
            if archive_key in metadata.archive \
              and metadata.archive[archive_key] \
              and key_values[archive_key] != metadata.archive[archive_key]:
                raise InstallablesError("command line %s (%s) does not match archive %s (%s)" \
                                        % (archive_key, key_values[archive_key],
                                           archive_key, metadata.archive[archive_key]))
            else:
                metadata.archive[archive_key] = key_values.pop(archive_key)

    if 'platform' in key_values:
        if 'platform' in metadata \
          and metadata['platform'] is not None \
          and key_values['platform'] != metadata['platform'] \
          and metadata['platform'] != common.PLATFORM_COMMON:
          raise InstallablesError("specified platform '%s' does not match archive platform '%s'" \
                                  % ( key_values['platform'], metadata['platform']))
        else:
            platform = key_values.pop('platform')
    else:
        if 'platform' in metadata \
          and metadata['platform'] is not None:
            platform = metadata['platform']
        else:
          raise InstallablesError("Unspecified platform")

    platform_description = configfile.PlatformDescription()
    platform_description.name = platform
    platform_description.archive = metadata.archive.copy()

    _warn_unused(key_values)
    return (metadata, platform_description)


def add(config, args_name, args_archive, arguments):
    """
    Adds a package to the configuration's installable list.
    """
    (metadata, platform_description)  = _get_new_metadata(config, args_name, args_archive, arguments)
    package_name = metadata.package_description.name
    if package_name in config.installables:
        raise InstallablesError('package %s already exists, use edit instead' % package_name)
    package_description = metadata.package_description.copy()
    package_description.platforms[platform_description.name] = platform_description

    config.installables[package_name] = package_description


def edit(config, args_name, args_archive, arguments):
    """
    Modifies an existing installable entry.
    """
    (metadata, platform_description)  = _get_new_metadata(config, args_name, args_archive, arguments)
    package_name = metadata.package_description.name

    if package_name not in config.installables:
        raise InstallablesError('package %s does not exist, use add instead' % package_name)
    if args_name and args_name != package_name:
        raise InstallablesError('name argument (%s) does not match package name (%s)' % (args_name, package_name))
        
    installed_package_description = config.installables[package_name]
    for element in _PACKAGE_ATTRIBUTES:
        if element in metadata.package_description \
          and  metadata.package_description[element] is not None:
          installed_package_description[element] = metadata.package_description[element]

    platform_name = platform_description.name
    if platform_name in installed_package_description.platforms:
        installed_platform_description = installed_package_description.platforms[platform_name]
    else:
        installed_platform_description = configfile.PlatformDescription()
        installed_platform_description.name = platform_name
        installed_package_description.platforms[platform_name] = platform_description.copy()

    for element in _ARCHIVE_ATTRIBUTES:
        if element in metadata.archive \
          and metadata.archive[element] is not None:
            installed_package_description.platforms[platform_name].archive[element] = metadata.archive[element]

    

def remove(config, installable_name):
    """
    Removes named installable from configuration installables.
    """
    config.installables.pop(installable_name)


def print_installable(config, installable_name):
    """
    Print the named installable (or all if name is None)
    """
    pretty_print = lambda p: pprint.pprint(configfile.compact_to_dict(p), sys.stdout, 1, 80)
    if installable_name is None:
        pretty_print(config.installables)
    else:
        pretty_print(config.installables.get(installable_name))


uri_regex = re.compile(r'\w+://')
def _is_uri(path):
    return path and bool(uri_regex.match(path))

def _check_name(arg_name, key_values, metadata):
    package_name = None
    if arg_name is not None:
        if 'name' in key_values and arg_name != key_values['name']:
            raise InstallablesError("name argument and name key/value do not match")
        if 'name' in metadata.package_description \
          and metadata.package_description['name'] is not None \
          and arg_name != metadata.package_description['name']:
            raise InstallablesError("command line name (%s) does not match archive name (%s)" \
                                    % (arg_name, metadata.package_description['name']))
        package_name = arg_name
    elif 'name' in key_values and key_values['name'] is not None:
        if 'name' in metadata.package_description \
          and metadata.package_description['name'] is not None \
          and key_values['name'] != metadata.package_description['name']:
            raise InstallablesError("key/value name (%s) does not match archive name (%s)" \
                                    % (key_values['name'], metadata.package_description['name']))
        package_name = key_values['name']
    elif 'name' in metadata.package_description \
      and metadata.package_description['name'] is not None:
        package_name = metadata.package_description['name']
    else:
        raise InstallablesError('installable package name not specified or found in archive')
    return package_name

def _warn_unused(data):
    for (key, value) in data.iteritems():
        logger.warning('ignoring unused argument %s=%s' % (key, value))
