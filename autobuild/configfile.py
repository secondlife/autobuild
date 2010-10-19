# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

"""
API to access the autobuild configuration file.

Author : Alain Linden
"""

import os
import pprint
import sys
import StringIO
import common
from executable import Executable
from common import AutobuildError
from common import get_current_platform
from llbase import llsd
import update


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
    An autobuild configuration.
    
    Attributes:
        package_description
        installables
    """
    
    path = None
    
    def __init__(self, path):
        self.version = AUTOBUILD_CONFIG_VERSION
        self.type = AUTOBUILD_CONFIG_TYPE
        self.installables = {}
        self.package_description = None
        self.__load(path)
 
    def absolute_path(self, path):
        """
        Returns an absolute path derived from the input path rooted at the configuration file's
        directory when the input is a relative path.
        """
        if os.path.isabs(path):
            return path
        else:
            return os.path.abspath(os.path.join(os.path.dirname(self.path), path))

    def get_all_build_configurations(self, platform_name=get_current_platform()):
        """
        Returns all build configurations for the platform.
        """
        return self.get_platform(platform_name).configurations.values()
    
    def get_really_all_build_configurations(self):
        """
        Returns all build configurations for all platforms.
        """
        # REVIEW: this returns a constructed object, for display purposes. 
        # However, it does not reflect the true datastructure. An issue?
        platform_dict = {}
        for platform_name in self.get_all_platforms():
            platform_dict[platform_name] =(self.get_platform(platform_name).configurations.values())
        return platform_dict
    
    def get_build_configuration(self, build_configuration_name, platform_name=get_current_platform()):
        """
        Returns the named build configuration for the platform. 
        """
        build_configuration = \
            self.get_platform(platform_name).configurations.get(build_configuration_name, None)
        if build_configuration is not None:
            return build_configuration
        else:
            raise ConfigurationError("no configuration for build configuration '%s'" % 
                build_configuration_name)
   
    def get_build_directory(self, platform_name=get_current_platform()):
        """
        Returns the absolute path to the build directory for the platform.
        """
        if self.package_description is None:
            raise ConfigurationError('no package configuration defined')
        platform_description = self.package_description.platforms.get(platform_name, None)
        if platform_description is None:
            raise ConfigurationError("no configuration for platform '%s'" % platform_name)
        config_directory = os.path.dirname(self.path)
        if platform_description.build_directory is not None:
            build_directory = platform_description.build_directory
            if not os.path.isabs(build_directory):
                build_directory = os.path.abspath(os.path.join(config_directory, build_directory))
        else:
            build_directory = config_directory
        return build_directory

    def get_default_build_configurations(self, platform_name=get_current_platform()):
        """
        Returns the platform specific build configurations which are marked as default.
        """
        default_build_configurations = []
        for (key, value) in self.get_platform(platform_name).configurations.iteritems():
            if value.default:
                default_build_configurations.append(value)
        return default_build_configurations
    
    def get_platform(self, platform_name):
        """
        Returns the named platform description. 
        """
        if self.package_description is None:
            raise ConfigurationError('no package configuration defined')
        platform_description = self.package_description.platforms.get(platform_name, None)
        if platform_description is None:
            raise ConfigurationError("no configuration for platform '%s'" % platform_name)
        else:
            return platform_description
    
    def get_all_platforms(self):
        try:
            return self.package_description.platforms
        except AttributeError:
            self.package_description = PackageDescription({})
        return self.package_description.platforms

    def get_working_platform(self):
        """
        Returns the working platform description.
        """
        return self.get_platform(get_current_platform())
    
    def make_build_directory(self):
        """
        Makes the working platform's build directory if it does not exist and returns a path to it.
        """
        build_directory = self.get_build_directory(common.get_current_platform())
        if not os.path.isdir(build_directory):
            os.makedirs(build_directory)
        return build_directory
            
    def save(self):
        """
        Save the configuration state to the input file.
        """
        file(self.path, 'wb').write(llsd.format_pretty_xml(_compact_to_dict(self)))
            
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
                raise AutobuildError("Config file %s is corrupt. Aborting..." % self.path)
            if not saved_data.has_key('version'):
                raise AutobuildError('incompatible configuration file ' + self.path)
            if saved_data['version'] == self.version:
                if (not saved_data.has_key('type')) or (saved_data['type'] != 'autobuild'):
                    raise AutobuildError(self.path + ' not an autobuild configuration file')
                package_description = saved_data.pop('package_description', None)
                if package_description is not None:
                    self.package_description = PackageDescription(package_description)
                installables = saved_data.pop('installables', {})
                for (name, package) in installables.iteritems():
                    self.installables[name] = PackageDescription(package)
                self.update(saved_data)
            else:
                if saved_data['version'] in update.updaters:
                    update.updaters[saved_data['version']](saved_data, self)
                else:
                    raise ConfigurationError("cannot update version %s file %s" %
                                             (saved_data.version, self.path))
        elif not os.path.exists(self.path):
            pass
        else:
            raise ConfigurationError("cannot create configuration file %s" % self.path)

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
        as_source
        source
        source_type
        source_directory
        version
        patches
        platforms

    As of 2010-10-18, the as_source attribute is only used in
    PackageDescription objects stored in INSTALLED_CONFIG_FILE. Certain
    packages can be installed either by checking out source or by extracting a
    tarball, so AUTOBUILD_CONFIG_FILE provides enough information for either.
    It's up to the user to decide which approach to use. autobuild must store
    that choice, though.

    Usage of PackageDescription.platforms is also a little different for a
    PackageDescription in INSTALLED_CONFIG_FILE's ConfigurationDescription
    .installables. When a package isn't installed at all, it should have no
    PackageDescription entry in INSTALLED_CONFIG_FILE. When it is installed:

    - If PackageDescription.as_source is true, we expect its platforms
      collection to be empty.

    - If as_source is false, there should be exactly one platforms entry whose
      key is the specific platform name (rather than 'common'). That
      PlatformDescription describes the package actually installed on THIS
      platform. For this use case, in effect a PackageDescription's lone
      PlatformDescription simply extends the PackageDescription.
    """
    
    def __init__(self, arg):
        self.platforms={}
        self.license = None
        self.license_file = None
        self.version = None
        self.as_source = False
        if isinstance(arg, dict):
            self.__init_from_dict(arg.copy())
        else:
            self.name = arg

    def get_platform(self, platform):
        """
        Find the child PlatformDescription either for the named platform or
        for 'common'. Return None if neither PlatformDescription exists.
        """
        try:
            return self.platforms[platform]
        except KeyError:
            return self.platforms.get("common")

    def __init_from_dict(self, dictionary):
        platforms = dictionary.pop('platforms',{})
        for (key, value) in platforms.items():
            self.platforms[key] = PlatformDescription(value)
        self.update(dictionary)


class PlatformDescription(common.Serialized):
    """
    Contains the platform specific metadata for a package.
    
    Attributes:
        archive
        dependencies
        build_directory
        manifest
        configurations
    """
    
    def __init__(self, dictionary = None):
        self.configurations = {}
        self.manifest = []
        self.build_directory = None
        self.archive = None
        if dictionary is not None:
            self.__init_from_dict(dictionary.copy())
   
    def __init_from_dict(self, dictionary):
        configurations = dictionary.pop('configurations',{})
        for (key, value) in configurations.iteritems():
            self.configurations[key] = BuildConfigurationDescription(value)
        archive = dictionary.pop('archive', None)
        if archive is not None:
            self.archive = ArchiveDescription(archive)
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


class ArchiveDescription(common.Serialized):
    """
    Describes a dowloadable archive of artifacts for this package.
    
    Attributes:
        hash
        hash_algorithm
        url
    """
    # Implementations for various values of hash_algorithm should be found in
    # hash_algorithms.py.
    def __init__(self, dictionary = None):
        self.hash = None
        self.hash_algorithm = None
        self.url = None
        if dictionary is not None:
            self.update(dictionary)

    def __eq__(self, other):
        """
        Return True if the other ArchiveDescription matches this one: if the
        other one describes what's installed, and this one describes what's
        supposed to be installed, is the install up-to-date?
        """
        # If we're comparing to something that's not even an
        # ArchiveDescription, no way is it equal.
        if not isinstance(other, ArchiveDescription):
            return False
##         # Disabled because, if the hash_algorithm is as good as (say) MD5, we
##         # can safely say that if the hash matches, we have the right tarball
##         # -- even if we downloaded it from a different URL. That would be a
##         # dubious assumption if we were using a weaker hash such as a 16-bit
##         # checksum.
##         # Whoops, the archive is found at a different URL now, have to re-download.
##         if self.url != other.url:
##             return False
        # If there's no hash_algorithm, assume "md5". That works for either
        # side: an ArchiveDescription with hash_algorithm None matches an
        # ArchiveDescription with hash_algorithm explicitly set to "md5".
        if (self.hash_algorithm or "md5") != (other.hash_algorithm or "md5"):
            return False
        # It's only reasonable to compare hash values if the hash_algorithm
        # matches.
        return self.hash == other.hash

    def __ne__(self, other):
        # Use the same logic for both == and != operators.
        return not self.__eq__(other)


def compact_to_dict(description):
    """
    Creates a dict from the provided description recursively copying member descriptions to dicts  
    and removing and elements which are None or evaluate to False (e.g. empty strings and 
    containers)
    """
    return _compact_to_dict(description)


def pretty_print(description, stream=sys.stdout):
    """
    Pretty prints a compact version of any description to a stream. 
    """
    pprint.pprint(compact_to_dict(description), stream, 1, 80)


def pretty_print_string(description):
    """
    Generates a pretty print string for a description.
    """
    stream = StringIO()
    pretty_print(description, stream)
    return stream.getvalue()


# LLSD will only export dict objects, not objects which inherit from dict.  This function will 
# recursively copy dict like objects into dict's in preparation for export.
def _compact_to_dict(obj):
    if isinstance(obj, dict):
        result = {}
        for (key,value) in obj.items():
            if value:
                result[key] = _compact_to_dict(value)
        return result
    elif isinstance(obj, list):
        return [_compact_to_dict(o) for o in obj if o]
    else:
        return obj
