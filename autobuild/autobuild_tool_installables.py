#!/usr/bin/env python
# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
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


class InstallablesError(AutobuildError):
    pass


class AutobuildTool(autobuild_base.AutobuildBase):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
            description="Manipulate installable package entries in the autobuild configuration.")
     
    def register(self, parser):
        parser.add_argument('--config-file',
            dest='config_file',
            default=configfile.AUTOBUILD_CONFIG_FILE,
            help="")
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
        parser.add_argument('argument', nargs='*', help='a file pattern')

    def run(self, args):
        config = configfile.ConfigurationDescription(args.config_file)
        if args.interactive:
            print >> sys.stderr, "interactive mode not implemented"
            return
        if args.command == 'add':
            _do_add(config, args.argument, args.archive)
        elif args.command == 'edit':
            if args.archive:
                print >> sys.stderr, 'ignoring --archive option', args.archive
            _do_edit(config, args.argument)
        elif args.command == 'remove':
            for p in args.argument:
                remove(config, p) 
        elif args.command == 'print':
            pprint.pprint(configfile.compact_to_dict(config.installables), sys.stdout, 1, 80)
        else:
            raise InstallablesError('unknown command %s' % args.command)
        if not args.dry_run and args.command != 'print':
            config.save()


_PACKAGE_ATTRIBUTES =  ['descripition', 'copyright', 'license', 'license_file', 'source', \
            'source_type', 'source_directory']
_ARCHIVE_ATTRIBUTES = ['hash', 'hash_algorithm', 'url']


def add(config, installable_data):
    """
    Adds a package to the configuration's installable list.
    """
    if 'name' not in installable_data:
        raise InstallablesError('installable name not given')
    if [p for p in config.installables if p.name == installable_data['name']]:
        raise InstallablesError('package %s already exists, use edit instead' % 
            installable_data['name'])
    package_description = configfile.PackageDescription(installable_data['name'])
    if 'platform' in installable_data:
        platform_description = configfile.PlatformDescription()
        platform_description.name = installable_data['platform']
        package_description.platforms[platform_description.name] = platform_description
        for element in _PACKAGE_ATTRIBUTES:
            if element in installable_data:
                package_description[element] = installable_data[element]
        archive_description = configfile.ArchiveDescription()
        platform_description.archive = archive_description
        for element in _ARCHIVE_ATTRIBUTES:
            if element in installable_data:
                archive_description[element] = installable_data[element]
    config.installables.append(package_description)


def edit(config, installable_data):
    """
    Modifies an existing installable entry.
    """
    if 'name' not in installable_data:
        raise InstallablesError('installable name not given')
    package_list = [p for p in config.installables if p.name == installable_data['name']]
    if not package_list:
        raise InstallablesError('package %s already exists, use edit instead' % 
            installable_data['name'])
    if len(package_list) > 1:
        raise InstallablesError('multiple packages named %s exists, edit is ambiguous' % 
            installable_data['name'])
    package_description = package_list[0]
    for element in _PACKAGE_ATTRIBUTES:
        if element in installable_data:
            package_description[element] = installable_data[element]
    if 'platform' in installable_data:
        platform_name = installable_data['platform']
        if platform_name in package_description.platforms:
            platform_description = package_description.platforms[platform_name]
        else:
            platform_description = configfile.PlatformDescription()
            platform_description.name = installable_data['platform']
            package_description.platforms[platform_description.name] = platform_description
        if platform_description.archive is not None:
            archive_description = platform_description.archive
        else:
            archive_description = configfile.ArchiveDescription()
            platform_description.archive = archive_description
        for element in _ARCHIVE_ATTRIBUTES:
            if element in installable_data:
                archive_description[element] = installable_data[element]


def remove(config, installable_name):
    """
    Removes named installable from configuration installables.
    """
    package_list = [p for p in config.installables if p.name == installable_name]
    for package in package_list:
        config.installables.remove(package)


key_value_regexp = re.compile(r'(\w+)\s*=\s*(\S+)')
def _process_key_value_arguments(arguments):
    dictionary = {}
    for argument in arguments:
        match = key_value_regexp.match(argument.strip())
        if match:
            dictionary[match.group(1)] = match.group(2)
        else:
            print >> sys.stderr, 'ignoring malformed argument', argument
    return dictionary


def _do_add(config, arguments, archive_path):
    if archive_path:
        installable_data = _archive_information(archive_path.strip())
        absolute_path = config.absolute_path(archive_path)
        try:
            installable_data['hash'] = common.compute_md5(absolute_path)
            installable_data['hash_algorithm'] = 'md5'
        except:
            pass
    else:
        installable_data = {}
    installable_data.update(_process_key_value_arguments(arguments))
    add(config, installable_data)


def _do_edit(config, arguments):
    edit(config, _process_key_value_arguments(arguments))


uri_regex = re.compile(r'\w+://')
def _is_uri(path):
    return bool(uri_regex.match(path))


def _archive_information(archive_path):
    (directory, data, extension) = common.split_tarname(archive_path)
    archive_data = {'name':data[0], 'version':data[1], 'platform':data[2]}
    if _is_uri(archive_path):
        archive_data['url'] = archive_path
    return archive_data
    
