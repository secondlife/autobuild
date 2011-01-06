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
Includes tools for updating older versions of autobuild configurations to the the current format.
"""


from common import AutobuildError
import configfile
from executable import Executable
import shlex


# A map of updators taking the version as a key and returning an appropriate conversion function. 
updaters = {}


class UpdateError(AutobuildError):
    pass


class _Update_1_1(object):
    """
    Converts a 1.1 version configuration to the latest version.
    """
    package_properties = { \
        'name':'name',
        'copyright':'copyright', \
        'description':'description', \
        'license':'license', \
        'licensefile':'license_file', \
        'homepage':'homepage', \
        'source':'source', \
        'sourcetype':'source_type', \
        'sourcedir':'source_directory', \
        'version':'version', \
    }
    
    archive_properties = {
        'md5sum':'hash', \
        'url':'url', \
    }
    
    def __call__(self, old_config, config):
        assert old_config['version'] == '1.1'
        self.old_config = old_config
        self.config = config
        if 'package_definition' in old_config:
            old_package = old_config['package_definition']
            package_description = configfile.PackageDescription('unnamed')
            self.config.package_description = package_description
            self._insert_package_properties(old_package, package_description)
            self._insert_command('configure', old_package.get('configure', {}), package_description)
            self._insert_command('build', old_package.get('build', {}), package_description)
            for (platform_name, manifest) in old_package.get('manifest', {}).items():
                self._get_platform(platform_name, package_description).manifest = \
                    manifest.get('files', [])
        else:
            raise UpdateError('no package description')
        if 'installables' in old_config:
            for (old_package_name, old_package) in old_config['installables'].iteritems():
                package = configfile.PackageDescription(old_package_name)
                self._insert_package_properties(old_package, package)
                self._insert_archives(old_package['archives'], package)
                self.config.installables[old_package_name] = package

    def _insert_package_properties(self, old_package, package):
        for (key, value) in self.package_properties.iteritems():
            if key in old_package:
                package[value] = old_package[key]
    
    def _insert_archives(self, old_archives, package):
        for (platform_name, old_archive) in  old_archives.iteritems():
            platform = self._get_platform(platform_name, package)
            archive = configfile.ArchiveDescription()
            platform.archive = archive
            for (key, value) in self.archive_properties.iteritems():
                archive[value] = old_archive[key]
   
    def _insert_command(self, type, old_commands, package):
        for (platform_name, old_command) in old_commands.iteritems():
            platform = self._get_platform(platform_name, package)
            #FIXME: find a better way to choose the default configuration.
            default_configuration = 'RelWithDebInfo'
            if default_configuration in platform.configurations:
                build_configuration = platform.configurations[default_configuration]
            else:
                build_configuration = configfile.BuildConfigurationDescription()
                build_configuration.name = default_configuration
                platform.configurations[default_configuration] = build_configuration
            if 'command' in old_command:
                tokens = shlex.split(old_command['command']);
                command = tokens.pop(0)
                # It is pretty much impossible to infer where the options end and the arguments 
                # begin since we don't know which options take values, so make everyting an
                # argument. Parent options will come before arguments so things should probably work
                # as expected.
                build_configuration[type] = Executable(command=command, arguments=tokens)
                build_configuration.default = True
            if 'directory' in old_command:
                platform.build_directory = old_command['directory']
    
    def _get_platform(self, platform_name, package):
        if platform_name in package.platforms:
            return package.platforms[platform_name]
        else:
            platform = configfile.PlatformDescription()
            platform.name = platform_name
            package.platforms[platform_name] = platform
            return platform


updaters['1.1'] = _Update_1_1()
