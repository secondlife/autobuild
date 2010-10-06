# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

"""
API to access the autobuild configuration file.

Author : Alain Linden
"""

import os
import common
from executable import Executable
from common import AutobuildError
from llbase import llsd


AUTOBUILD_CONFIG_FILE="autobuild.xml"
AUTOBUILD_CONFIG_VERSION="1.2"
AUTOBUILD_CONFIG_TYPE="autobuild"
INSTALLED_CONFIG_FILE="installed-packages.xml"


# FIXME: remove when refactor is complete
class ConfigFile:
    pass

class ConfigurationError(AutobuildError):
    pass


class ConfigurationDescription(common.Serialized):
    """
    An autoubuild configuration.
    
    Attributes:
        package_description
        installables
    """
    
    path = None
    
    def __init__(self, path):
        self.version = AUTOBUILD_CONFIG_VERSION
        self.type = AUTOBUILD_CONFIG_TYPE
        self.__load(path)
            
    def save(self):
        """
        Save the configuration state to the input file.
        """
        file(self.path, 'wb').write(llsd.format_pretty_xml(_flatten_to_dict(self)))
    
    def get_build_configuration(self, build_configuration_name):
        """
        Returns the named platform specific build configuration. 
        """
        if self.package_description is None:
            raise ConfigurationError('no package configuration defined')
        current_platform = common.get_current_platform()
        platform_description = self.package_description.platforms.get(current_platform, None)
        if platform_description is None:
            raise ConfigurationError("no configuration for platform '%s'" % current_platform)
        build_configuration = \
            platform_description.configurations.get(build_configuration_name, None)
        if build_configuration is not None:
            return build_configuration
        else:
            raise ConfigurationError("no configuration for build configuration '%s'" % 
                build_configuration)

    def get_default_build_configurations(self):
        """
        Returns the platform specific build configurations which are marked as default.
        """
        if self.package_description is None:
            raise ConfigurationError('no package configuration defined')
        platform_description = self.package_description.platforms.get(
            common.get_current_platform(), None)
        if platform_description is None:
            raise ConfigurationError("no configuration for platform '%s'" % current_platform)
        default_build_configurations = []
        for (key, value) in platform_description.configurations.items():
            if value.default:
                default_build_configurations.append(value)
        return default_build_configurations
    
    def __load(self, path):
        if os.path.isabs(path):
            self.path = path
        else:
            abs_path = os.path.abspath(path)
            found_path = common.search_up_for_file(abs_path)
            if found_path is not None:
                self.path = found_path
            else:
                self.path = abs_path
        if os.path.isfile(self.path):
            try:
                saved_data = llsd.parse(file(self.path, 'rb').read())
            except llsd.LLSDParseError:
                raise AutobuildError("Config file is corrupt: %s. Aborting..." % self.filename)
            if (not saved_data.has_key('type')) or (saved_data['type'] != 'autobuild'):
                raise AutobuildError('not an autoubuild configuration file')
            if (not saved_data.has_key('version')) or (saved_data['version'] != self.version):
                raise AutobuildError('incompatible configuration file')
            package_description = saved_data.pop('package_description', None)
            if package_description is not None:
                self.package_description = PackageDescription(package_description)
            installables = saved_data.pop('installables', [])
            self.installables = []
            for package in installables:
                self.installables.append(PackageDescription(package))
            self.update(saved_data)
        else:
            self.package_description = None
            self.installables = []


class PackageDescription(common.Serialized):
    """
    Contains the metadata for a single package.
    
    Attributes:
        name
        copyright
        description
        license
        license_file
        homepage
        source
        source_type
        source_directory
        version
        patches
        platforms
    """
    
    def __init__(self, arg):
        self.platforms={}
        if isinstance(arg, dict):
            self.__init_from_dict(arg.copy())
        else:
            self.name = arg
            
    def __init_from_dict(self, dictionary):
        platforms = dictionary.pop('platforms',{})
        for (key, value) in platforms.iteritems():
            self.platforms[key] = PlatformDescription(value)
        self.update(dictionary)


class PlatformDescription(common.Serialized):
    """
    Contains the platform specific metadata for a package.
    
    Attributes:
        archives
        dependencies
        build_directory
        manifest
        configurations
    """
    
    def __init__(self, dictionary = None):
        self.configurations = {}
        if dictionary is not None:
            self.__init_from_dict(dictionary.copy())
   
    def __init_from_dict(self, dictionary):
        configurations = dictionary.pop('configurations',{})
        for (key, value) in configurations.iteritems():
            self.configurations[key] = BuildConfigurationDescription(value)
        self.update(dictionary)
        

class BuildConfigurationDescription(common.Serialized):
    """
    Contains the build configuration specific metadata and executables for a platform.
    
    Attributes:
        default
        configure
        build
    """
    
    build_steps = ['configure', 'build']
    
    def __init__(self, dictionary = None):
        self.configure = None
        self.build = None
        self.default = False
        if dictionary is not None:
            self.__init_from_dict(dictionary.copy())
   
    def __init_from_dict(self, dictionary):
        [self.__extract_command(name, dictionary) for name in self.build_steps]
        self.update(dictionary)

    def __extract_command(self, name, dictionary):
        command = dictionary.pop(name, None)
        if command is not None:
            self[name] = Executable(
                command=command.get('command'), options=command.get('options', []), 
                arguments=command.get('arguments'))


def _flatten_to_dict(obj):
    if isinstance(obj,dict):
        result = {}
        for (key,value) in obj.items():
            result[key] = _flatten_to_dict(value)
        return result
    else:
        return obj
