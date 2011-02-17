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
import common
import pprint
import argparse
import configfile
import autobuild_base
import re
from common import AutobuildError
import logging


logger = logging.getLogger('autobuild.installables')


# Match key=value arguments.
_key_value_regexp = re.compile(r'(\w+)\s*=\s*(\S+)')


class InstallablesError(AutobuildError):
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
        parser.add_argument('-a','--archive',
            dest='archive',
            default=None,
            help="infer installable attributes from the given archive")
        parser.add_argument(
            '-i','--interactive', 
            action='store_true',
            default=False,
            dest='interactive',
            help="run as an interactive session")
        parser.add_argument('command', nargs='?', default='print',
            help="installable command: add, remove, edit, or print")
        parser.add_argument('name', nargs='?', default=None,
            help="the name of the installable")
        parser.add_argument('argument', nargs='*', help='a key=value pair specifying an attribute')

        parser.epilog = "EXAMPLE: autobuild edit indra_common platform=linux hash=<md5 hash> url=<url>"

    def run(self, args):
        config = configfile.ConfigurationDescription(args.config_file)
        if args.interactive:
            logger.error("interactive mode not implemented")
            return
        if args.command == 'add':
            _do_add(config, args.name, args.argument, args.archive)
        elif args.command == 'edit':
            if args.archive:
                logger.warning('ignoring --archive option ' + args.archive)
            _do_edit(config, args.name, args.argument)
        elif args.command == 'remove':
            remove(config, args.name)
        elif args.command == 'print':
            print_installable(config, args.name)
        else:
            raise InstallablesError('unknown command %s' % args.command)
        if not args.dry_run and args.command != 'print':
            config.save()


_PACKAGE_ATTRIBUTES =  ['descripition', 'copyright', 'license', 'license_file', 'source', \
            'source_type', 'source_directory', 'version']
_ARCHIVE_ATTRIBUTES = ['hash', 'hash_algorithm', 'url']


def add(config, installable_name, installable_data):
    """
    Adds a package to the configuration's installable list.
    """
    _check_name(installable_name)
    installable_data = installable_data.copy()
    if installable_name in config.installables:
        raise InstallablesError('package %s already exists, use edit instead' %  installable_name)
    package_description = configfile.PackageDescription(installable_name)
    if 'platform' in installable_data:
        platform_description = configfile.PlatformDescription()
        platform_description.name = installable_data.pop('platform')
        package_description.platforms[platform_description.name] = platform_description
        for element in _PACKAGE_ATTRIBUTES:
            if element in installable_data:
                package_description[element] = installable_data.pop(element)
        archive_description = configfile.ArchiveDescription()
        platform_description.archive = archive_description
        for element in _ARCHIVE_ATTRIBUTES:
            if element in installable_data:
                archive_description[element] = installable_data.pop(element)
    config.installables[installable_name] = package_description
    _warn_unused(installable_data)


def edit(config, installable_name, installable_data):
    """
    Modifies an existing installable entry.
    """
    _check_name(installable_name)
    installable_data = installable_data.copy()
    if installable_name not in config.installables:
        raise InstallablesError('package %s does not exist, use add instead' % installable_name)
    package_description = config.installables[installable_name]
    for element in _PACKAGE_ATTRIBUTES:
        if element in installable_data:
            package_description[element] = installable_data.pop(element)
    if 'platform' in installable_data:
        platform_name = installable_data.pop('platform')
        if platform_name in package_description.platforms:
            platform_description = package_description.platforms[platform_name]
        else:
            platform_description = configfile.PlatformDescription()
            platform_description.name = platform_name
            package_description.platforms[platform_description.name] = platform_description
        if platform_description.archive is not None:
            archive_description = platform_description.archive
        else:
            archive_description = configfile.ArchiveDescription()
            platform_description.archive = archive_description
        for element in _ARCHIVE_ATTRIBUTES:
            if element in installable_data:
                archive_description[element] = installable_data.pop(element)
    _warn_unused(installable_data)
    

def print_installable(config, installable_name):
    """
    Print the named installable (or all if name is None)
    """
    pretty_print = lambda p: pprint.pprint(configfile.compact_to_dict(p), sys.stdout, 1, 80)
    if installable_name is None:
        pretty_print(config.installables)
    else:
        pretty_print(config.installables.get(installable_name))


def remove(config, installable_name):
    """
    Removes named installable from configuration installables.
    """
    config.installables.pop(installable_name)


def _process_key_value_arguments(arguments):
    dictionary = {}
    for argument in arguments:
        match = _key_value_regexp.match(argument.strip())
        if match:
            dictionary[match.group(1)] = match.group(2)
        else:
            logger.warning('ignoring malformed argument ' + argument)
    return dictionary


def _do_add(config, installable_name, arguments, archive_path):
    if archive_path:
        installable_data = _archive_information(archive_path.strip())
        archive_installable_name = installable_data.pop('name')
        if installable_name:
            if(_key_value_regexp.match(installable_name)):
                arguments.append(installable_name)
                installable_name = archive_installable_name
            elif archive_installable_name != installable_name:
                raise InstallablesError('archive name %s does not match provided name %s' %
                    (archive_installable_name, installable_name))
            else:
                pass
        else:
            installable_name = archive_installable_name
        absolute_path = config.absolute_path(archive_path)
        try:
            installable_data['hash'] = common.compute_md5(absolute_path)
            installable_data['hash_algorithm'] = 'md5'
        except:
            pass
    else:
        installable_data = {}
    installable_data.update(_process_key_value_arguments(arguments))
    add(config, installable_name, installable_data)


def _do_edit(config, installable_name, arguments):
    edit(config, installable_name, _process_key_value_arguments(arguments))


uri_regex = re.compile(r'\w+://')
def _is_uri(path):
    return bool(uri_regex.match(path))


def _archive_information(archive_path):
    try:
        (directory, data, extension) = common.split_tarname(archive_path)
        archive_data = {'name':data[0], 'version':data[1], 'platform':data[2]}
    except:
        raise InstallablesError('archive path %s is not cannonical' % archive_path)
    if _is_uri(archive_path):
        archive_data['url'] = archive_path
    return archive_data


def _check_name(name):
    if name is None:
        raise InstallablesError('installable name not given')
    elif _key_value_regexp.match(name):
        raise InstallablesError('missing name argument')


def _warn_unused(data):
    for (key, value) in data.iteritems():
        logger.warning('ignoring unused argument %s=%s' % (key, value))
