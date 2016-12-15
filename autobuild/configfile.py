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
API to access the autobuild configuration file.

Author : Alain Linden
"""

import os
import itertools
import pprint
import re
import string
import sys
from cStringIO import StringIO
try:
    from llbase import llsd
except ImportError:
    sys.exit("Failed to import llsd via the llbase module; to install, use:\n"
             "  pip install llbase")

import common
from executable import Executable
import logging

logger = logging.getLogger('autobuild.configfile')

AUTOBUILD_CONFIG_FILE = os.environ.get("AUTOBUILD_CONFIG_FILE", "autobuild.xml")
AUTOBUILD_CONFIG_VERSION = "1.3"        # introduced version_file requirement
AUTOBUILD_CONFIG_TYPE = "autobuild"

AUTOBUILD_INSTALLED_VERSION = "1"
AUTOBUILD_INSTALLED_TYPE = "installed"
INSTALLED_CONFIG_FILE = "installed-packages.xml"

AUTOBUILD_METADATA_VERSION = "1"
AUTOBUILD_METADATA_TYPE = "metadata"
PACKAGE_METADATA_FILE = "autobuild-package.xml"


class ConfigurationError(common.AutobuildError):
    pass


class ConfigurationDescription(common.Serialized):
    """
    An autobuild configuration.

    Attributes:
        package_description
        installables
    """

    # Setting 'path' as a class attribute tells Serialized not to save this
    # attribute to file: it should remain an ordinary Python attribute rather
    # than a dict key.
    path = None

    def __init__(self, path, copyfrom=None):
        self.version = AUTOBUILD_CONFIG_VERSION
        self.type = AUTOBUILD_CONFIG_TYPE
        self.installables = {}
        self.package_description = None
        # SL-525: Track whether this ConfigurationDescription has, or has not,
        # had $variables expanded. We defer such expansion because it's VERY
        # IMPORTANT to avoid resaving any _expanded ConfigurationDescription!
        # That would replace the user's parameterization with ONE SPECIFIC
        # expansion.
        self._expanded = False
        if path is not None:
            self.__load(path)
            os.environ['AUTOBUILD_CONFIG_FILE'] = os.path.basename(self.path)
        elif copyfrom is not None:
            self.__init_from_dict(dict(copyfrom))
            self.path = getattr(copyfrom, "path", None)

    def copy(self):
        # Serialized.copy() only passes 'self' to our constructor -- which
        # doesn't work, since our constructor treats it as a path. Do the
        # right thing here.
        return ConfigurationDescription(path=None, copyfrom=self)

    def absolute_path(self, path):
        """
        Returns an absolute path derived from the input path rooted at the configuration file's
        directory when the input is a relative path.
        """
        if os.path.isabs(path):
            return path
        else:
            return os.path.abspath(os.path.join(os.path.dirname(self.path), path))

    def get_all_build_configurations(self, platform_name=None):
        """
        Returns all build configurations for the platform.
        """
        if platform_name is None:
            platform_name = common.get_current_platform()
        return self.get_platform(platform_name).configurations.values()

    def get_build_configuration(self, build_configuration_name, platform_name=None):
        """
        Returns the named build configuration for the platform.
        """
        if platform_name is None:
            platform_name = common.get_current_platform()
        try:
            return self.get_platform(platform_name).configurations[build_configuration_name]
        except KeyError:
            raise ConfigurationError("no configuration for build configuration '%s' found; "
                                     "one may be created using 'autobuild edit build'" %
                                     build_configuration_name)

    def get_default_build_configurations(self, platform_name=None):
        """
        Returns the platform specific build configurations which are marked as default.
        """
        if platform_name is None:
            common.get_current_platform()
        return [value
                for (key, value) in self.get_platform(platform_name).configurations.iteritems()
                if value.default]

    def get_build_directory(self, configuration, platform_name=None):
        """
        Returns the absolute path to the build directory for the platform.
        """
        build_directory=None
        if platform_name is None:
            platform_name = common.get_current_platform()
        platform_description = self.get_platform(platform_name)
        common_platform_description = self.package_description.platforms.get(common.PLATFORM_COMMON, None)
        config_directory = os.path.dirname(self.path)
        # Try specific configuration build_directory first.
        if hasattr(configuration, 'build_directory') and configuration.build_directory is not None:
            build_directory = configuration.build_directory
            if not os.path.isabs(build_directory):
                build_directory = os.path.abspath(os.path.join(config_directory, build_directory))
        elif platform_description.build_directory is not None:
             build_directory = platform_description.build_directory
             if not os.path.isabs(build_directory):
                 build_directory = os.path.abspath(os.path.join(config_directory, build_directory))
        elif common_platform_description is not None and common_platform_description.build_directory is not None:
            build_directory = common_platform_description.build_directory
            if not os.path.isabs(build_directory):
                build_directory = os.path.abspath(os.path.join(config_directory, build_directory))
        else:
            build_directory = config_directory

        common.establish_build_dir(build_directory) # save global state
        return build_directory

    def get_platform(self, platform_name):
        """
        Returns the named platform description.
        """
        if self.package_description is None:
            raise ConfigurationError("no package configuration defined; one may be created using 'autobuild edit package'")
        platform_description = self.package_description.get_platform(platform_name)
        if platform_description is None:
            raise ConfigurationError("no configuration for platform '%s' found; one may be created using 'autobuild edit platform'" % platform_name)
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
        return self.get_platform(common.get_current_platform())

    def make_build_directory(self, configuration, platform=common.get_current_platform(), dry_run=False):
        """
        Makes the working platform's build directory if it does not exist and returns a path to it.
        """
        logger.debug("make_build_directory platform %s" % platform)
        build_directory = self.get_build_directory(configuration, platform_name=platform)
        if not os.path.isdir(build_directory):
            if not dry_run:
                logger.info("Creating build directory %s"
                            % build_directory)
                os.makedirs(build_directory)
            else:
                logger.warn("Dry run mode: not creating build directory %s"
                            % build_directory)
        return build_directory

    def save(self):
        """
        Save the configuration state to the input file.
        """
        if self._expanded:
            # SL-525: Do NOT save if variables have been expanded!
            raise ConfigurationError("Aborting attempt to save %s with variable expansions" %
                                     self.path)
        logger.debug("Writing configuration file %s" % self.path)
        file(self.path, 'wb').write(llsd.format_pretty_xml(_compact_to_dict(self)))

    def __load(self, path):
        # circular imports, sorry, must import update locally
        import update

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
            autobuild_xml = file(self.path, 'rb').read()
            if not autobuild_xml:
                logger.warn("Configuration file '%s' is empty" % self.path)
                return
            try:
                saved_data = llsd.parse(autobuild_xml)
            except llsd.LLSDParseError:
                raise common.AutobuildError("Configuration file %s is corrupt. Aborting..." % self.path)
            saved_data, orig_ver = update.convert_to_current(self.path, saved_data)
            # Presumably this check comes after format-version updates because
            # at some point in paleontological history the file format did not
            # include "type".
            if saved_data.get("type", None) != 'autobuild':
                raise common.AutobuildError(self.path + ' not an autobuild configuration file')
            self.__init_from_dict(saved_data)
            logger.debug("Configuration file '%s'" % self.path)
            if orig_ver:
                logger.warn("Saving configuration file %s in format %s" %
                            (self.path, AUTOBUILD_CONFIG_VERSION))
                self.save()
                # We don't want orig_ver to appear in the saved file: that's
                # for internal use only. But we do want to track it because
                # there are those who care what kind of file we originally
                # read.
                self["orig_ver"] = orig_ver
        elif not os.path.exists(self.path):
            logger.warn("Configuration file '%s' not found" % self.path)
        else:
            raise ConfigurationError("cannot create configuration file %s" % self.path)

    def __init_from_dict(self, dictionary):
        package_description = dictionary.pop('package_description', None)
        if package_description is not None:
            self.package_description = PackageDescription(package_description)
        installables = dictionary.pop('installables', {})
        for (name, package) in installables.iteritems():
            self.installables[name] = PackageDescription(package)
            if name != self.installables[name].name:
                raise ConfigurationError("installable key '%s' does not match package name '%s'"
                                         % (name, self.installables[name].name))
        self.update(dictionary)

    def expand_platform_vars(self, vars=os.environ):
        try:
            package_description = self.package_description
        except AttributeError:
            logger.debug("ConfigurationDescription.expand_platform_vars(): "
                         "%s has no package_description" % self.name)
            return

        package_description.expand_platform_vars(vars)
        self._expanded = True

class AttrErrorString(str):
    """
    check_package_attributes wants to return a string containing collected
    errors. When that string is non-empty, the caller can raise an exception,
    produce a warning, concatenate additional information, etc.

    But some callers care specifically about which attributes are missing. We
    want to attach additional information to the error return. Hence this
    class.

    In Python 2.x, the distinction between 'str' and 'unicode' still matters.
    We derive from str rather than unicode because check_package_attributes()
    actually controls the entire content of the string: it does not embed
    arbitrary caller data.
    """
    # To intercept str construction, have to override __new__() as well as
    # __init__().
    def __new__(cls, attrs, message):
        # Merely returning the new instance allows Python to proceed to call
        # __init__() with the new instance and the same other args.
        return super(AttrErrorString, cls).__new__(cls, message)

    def __init__(self, attrs, message):
        # Since we've already passed 'message' to super().__new__(), it's
        # ignored by this super().__init__() call -- and in fact it produces
        # DeprecationWarnings -- so avoid the clutter by not even passing it.
        super(AttrErrorString, self).__init__()
        self.attrs = attrs

def check_package_attributes(container, additional_requirements=[]):
    """
    container may be a ConfigurationDescription or MetadataDescription
    additional_requirements are context-specific attributes to be required
    Returns an AttrErrorString of problems found. Caller can treat this like a
    str, or query its attrs attribute to discover the specific attributes with
    problems.
    """
    attrs  = []
    errors = []
    required_attributes = ['license', 'license_file', 'copyright', 'name']
    try:
        package = container.package_description
    except AttributeError:
        attrs.append("package_description")
        errors.append("no package_description found")
    else:
        for attribute in itertools.chain(required_attributes, additional_requirements):
            # this test intentionally conflates missing, None, empty string
            if not getattr(package, attribute, None):
                attrs.append(attribute)
                errors.append("'%s' not specified in the package_description" % attribute)
    return AttrErrorString(attrs, '\n'.join(errors))

class Dependencies(common.Serialized):
    """
    The record of packages installed in a build tree.

    Attributes:
        dependencies - a map of MetadataDescriptions, indexed by package name
    """

    def __init__(self, path):
        self.version = AUTOBUILD_INSTALLED_VERSION
        self.type = AUTOBUILD_INSTALLED_TYPE
        self.dependencies = {}
        self.__load(path=path)

    def save(self):
        """
        Save the configuration state to the input file.
        """
        dict_representation=_compact_to_dict(self)
        del dict_representation['path'] # there's no need for the file to include its own name
        file(self.path, 'wb').write(llsd.format_pretty_xml(dict_representation))

    def __load(self, path=None):
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
            installed_xml = file(self.path, 'rb').read()
            if not installed_xml:
                logger.warn("Installed file '%s' is empty" % self.path)
                return
            logger.debug("Installed file '%s'" % self.path)
            try:
                saved_data = llsd.parse(installed_xml)
            except llsd.LLSDParseError:
                raise common.AutobuildError("Installed file %s is not valid. Aborting..." % self.path)
            if not (('version' in saved_data and saved_data['version'] == self.version)
                    and ('type' in saved_data) and (saved_data['type'] == AUTOBUILD_INSTALLED_TYPE)):
                raise common.AutobuildError(self.path + ' is not compatible with this version of autobuild.'
                                     + '\nClearing your build directory and rebuilding should correct it.')

            dependencies = saved_data.pop('dependencies', {})
            for (name, package) in dependencies.iteritems():
                self.dependencies[name] = package
            self.update(saved_data)
        elif not os.path.exists(self.path):
            logger.info("Installed packages file '%s' not found; creating." % self.path)
        else:
            raise ConfigurationError("cannot create installed packages file %s" % self.path)


class MetadataDescription(common.Serialized):
    """
    The autobuild-package-<platform>.xml metadata file,
    which has a subset of the same data as the configuration, but specific to what is actually in the package
    (as opposed to what might be in all versions of the package)

    Attributes:
        package_description
        dependencies
        build_id
        platform
        configuration
        manifest
        dirty*
        install_type*
        install_dir*
        type
        version

    * not used except when the MetadataDescription is in the Dependencies
    """
    path = None

    def __init__(self, path=None, stream=None, parsed_llsd=None, convert_platform=None, create_quietly=False):
        self.version = AUTOBUILD_METADATA_VERSION
        self.type = AUTOBUILD_METADATA_TYPE
        self.build_id = None
        self.platform = None
        self.configuration = None
        self.package_description = None
        self.manifest = []
        self.dependencies = {}
        self.archive = None
        self.install_type = None
        self.install_dir = None
        self.dirty = False

        metadata_xml = None
        if path:
            self.path = path
            if os.path.isfile(self.path):
                metadata_xml = file(self.path, 'rb').read()
                if not metadata_xml:
                    logger.warn("Metadata file '%s' is empty" % self.path)
                    self.dirty=False
                    return
            elif not os.path.exists(self.path):
                if not create_quietly:
                    logger.warn("Configuration file '%s' not found" % self.path)
        elif stream:
            metadata_xml = stream.read()
        if metadata_xml:
            try:
                parsed_llsd = llsd.parse(metadata_xml)
            except llsd.LLSDParseError:
                raise common.AutobuildError("Metadata file %s is corrupt. Aborting..." % self.path)

        if parsed_llsd:
            self.__load(parsed_llsd)
            self.update(parsed_llsd)


    def __load(self, parsed_llsd):
        if (not 'version' in parsed_llsd) or (parsed_llsd['version'] != self.version) \
                or (not 'type' in parsed_llsd) or (parsed_llsd['type'] != 'metadata'):
            raise ConfigurationError("missing or incompatible metadata %s" %
                                     pprint.pformat(parsed_llsd))
        else:
            package_description = parsed_llsd.pop('package_description', None)
            if package_description:
                self.package_description = PackageDescription(package_description)
            else:
                raise ConfigurationError("metadata is missing package_description")
            dependencies = parsed_llsd.pop('dependencies', {})
            for (name, package) in dependencies.iteritems():
                self.dependencies[name] = MetadataDescription(parsed_llsd=package)
            self.manifest = parsed_llsd.pop('manifest', [])

    def add_dependencies(self, installed_pathname):
        logger.debug("loading " + installed_pathname)
        dependencies = Dependencies(installed_pathname)
        for (name, package) in dependencies.dependencies.iteritems():
            del package['install_dir']
            del package['manifest']
            if 'dirty' in package and package['dirty']:
                self.dirty=True
            logger.debug("adding '%s':\n%s"%(name, pprint.pformat(package)))
            self.dependencies[name] = package

    def save(self):
        """
        Save the metadata.
        """
        if self.path:
            file(self.path, 'wb').write(llsd.format_pretty_xml(_compact_to_dict(self)))

package_selected_platform = None

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
        version~
        version_file~
        patches
        platforms**
        install_dir*

    *The install_dir attribute is only used in PackageDescription objects
    stored in INSTALLED_CONFIG_FILE.

    ~The version and version_file attributes are used differently in
    AUTOBUILD_CONFIG_FILE and INSTALLED_CONFIG_FILE. In AUTOBUILD_CONFIG_FILE,
    we require version_file and ignore version with a deprecation warning.
    When we write metadata to INSTALLED_CONFIG_FILE, we read the version_file
    and store a version attribute instead of the version_file attribute.
    """

    def __init__(self, arg):
        self.platforms = {}
        self.license = None
        self.license_file = None
        self.copyright = None
        self.version = None
        self.version_file = None
        self.name = None
        self.install_dir = None
        if isinstance(arg, dict):
            self.__init_from_dict(dict(arg))
        else:
            self.name = arg

    def get_platform(self, platform):
        """
        Find the first child PlatformDescription for:
        1. the named platform,
        2. the base platform (the 64 bit version of each will default to the 32 bit version)
        3. the 'common' platform.
        Return None if no one of those PlatformDescriptions exists.
        """
        global package_selected_platform
        target_platform = None
        if platform in self.platforms:
            target_platform = self.platforms[platform]
        elif platform.endswith('64'):
            base_platform = platform[0:len(platform)-2]
            if base_platform in self.platforms:
                target_platform = self.platforms[base_platform]
                if package_selected_platform != base_platform:
                    logger.info("No %s configuration found; inheriting %s" % (platform, base_platform))
                    package_selected_platform = base_platform
        if target_platform is None:
            target_platform = self.platforms.get(common.PLATFORM_COMMON)
            logger.info("get_platform No %s configuration found; inheriting common" % (platform))
        return target_platform

    def read_version_file(self, build_directory):
        """
        Validate that this PackageDescription from AUTOBUILD_CONFIG_FILE has a
        version_file attribute referencing a readable file. Read it and return
        the contained version, else raise AutobuildError.

        If a legacy AUTOBUILD_CONFIG_FILE contains a version attribute,
        produce a deprecation warning.
        """
        if self.version:
            logger.warn("package_description.version ignored in %s; use version_file instead" %
                        AUTOBUILD_CONFIG_FILE)

        if not self.version_file:
            # should never hit this because caller should have already called
            # check_package_attributes(), but suspenders and belt
            raise common.AutobuildError("Missing version_file key")

        version_file = os.path.join(build_directory, self.version_file)
        try:
            with open(version_file) as vf:
                version = vf.read().strip()
        except IOError, err:
            raise common.AutobuildError("Can't read version_file '%s': %s" %
                                        (self.version_file, err))

        if not version:
            raise common.AutobuildError("version_file '%s' contains no version info" %
                                        self.version_file)
        return version

    def __init_from_dict(self, dictionary):
        platforms = dictionary.pop('platforms', {})
        for (key, value) in platforms.items():
            self.platforms[key] = PlatformDescription(value)
        self.update(dictionary)

    def expand_platform_vars(self, vars=os.environ):
        try:
            platforms = self.platforms
        except AttributeError:
            logger.debug("PackageDescription.expand_platform_vars(): "
                         "%s has no platforms" % self.name)
            return

        # Iterate through items() -- a copy -- so we can update in place
        for key, platform in platforms.items():
            # expand_vars() returns a copy of the original dict rather than
            # modifying it in place, so make a new PlatformDescription
            platforms[key] = PlatformDescription(expand_vars(platform, vars))


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

    def __init__(self, dictionary=None):
        self.configurations = {}
        self.manifest = []
        self.build_directory = None
        self.archive = None
        if dictionary is not None:
            self.__init_from_dict(dict(dictionary))

    def __init_from_dict(self, dictionary):
        configurations = dictionary.pop('configurations', {})
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

    def __init__(self, dictionary=None):
        self.configure = None
        self.build = None
        self.default = False
        if dictionary is not None:
            self.__init_from_dict(dict(dictionary))

    def __init_from_dict(self, dictionary):
        [self.__extract_command(name, dictionary) for name in self.build_steps]
        self.update(dictionary)

    def __extract_command(self, name, dictionary):
        command = dictionary.pop(name, None)
        if command is not None:
            self[name] = Executable(
                command=command.get('command'),
                options=command.get('options', []),
                arguments=command.get('arguments'),
                filters=command.get('filters'))


class ArchiveDescription(common.Serialized):
    """
    Describes a downloadable archive of artifacts for this package.

    Attributes:
        format
        hash
        hash_algorithm
        url
    """
    # Implementations for various values of hash_algorithm should be found in
    # hash_algorithms.py.
    def __init__(self, dictionary=None):
        self.format = None
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
        if 'url' not in other or 'hash' not in other:
            return False
        # If there's no hash_algorithm, assume "md5". That works for either
        # side: an ArchiveDescription with hash_algorithm None matches an
        # ArchiveDescription with hash_algorithm explicitly set to "md5".
        if (self.hash_algorithm or "md5") != (('hash_algorithm' in other and other['hash_algorithm']) or "md5"):
            return False
        # It's only reasonable to compare hash values if the hash_algorithm
        # matches.
        return self.hash == other['hash'] and self.url == other['url']

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
        for (key, value) in obj.items():
            if value:
                result[key] = _compact_to_dict(value)
        return result
    elif isinstance(obj, list):
        return [_compact_to_dict(o) for o in obj if o]
    elif isinstance(obj, set):
        return [_compact_to_dict(o) for o in obj if o]
    else:
        return obj

def expand_vars(data, vars=os.environ):
    """
    In the dict passed as data, recursively visit each leaf string value,
    replacing variable references. Keys at any level remain untouched.
    Variables are found in the dict passed as vars.

    The following substitution syntax is recognized:

    $var
    ${var}
    ${var|fallback}

    In the first two cases, if the variable 'var' is undefined, expand_vars()
    raises ConfigurationError. In the third case, if 'var' is undefined, the
    construct is replaced by 'fallback'. In all three cases, of course, if
    'var' is defined, the construct is replaced by the value of 'var'.

    Return a copy of data with variable references expanded. The original data
    dict is unchanged.
    """
    if isinstance(data, basestring):
        # str or unicode: expand
        return _expand_vars_string(data, vars)

    if hasattr(data, 'items'):
        # dict: copy it
        newdata = data.copy()
        # and update the new copy
        for key, value in data.iteritems():
            newdata[key] = expand_vars(value, vars)
        return newdata

    try:
        iter(data)
    except TypeError:
        # non-string scalar: just return
        return data

    # data is a list or tuple
    # make another such whose entries are expanded
    return data.__class__(expand_vars(value, vars) for value in data)

# It Would Be Nice if we could cheaply support nested expansions:
# ${first|${second}} Unfortunately that would require actual parsing rather
# than a simple regexp -- regexps don't handle nesting. If we just went for
# the maximum match between | and }, rather than the minimum, then something
# like ${a|fallback} and ${c} would break: the fallback string for missing 'a'
# would be "fallback} and ${c". So nested variable expansions will be a future
# enhancement, if ever.
_placeholder = re.compile(r"\$\{(.*?)\|(.*?)\}")

def _expand_vars_string(value, vars):
    """
    value is a string.

    Return a corresponding string in which any variable references (as
    described in the docstring for expand_vars()) found in that string have
    been expanded.
    """
    # First check for fallback syntax: the extended syntax NOT already
    # supported by string.Template.

    # sub()'s first argument can be a function taking a match object:
    # https://docs.python.org/2/library/re.html#re.sub
    # sub() calls the passed function for every match within the second
    # argument 'value'.
    # That function returns the string you want to substitute.
    # Since we know the _placeholder regexp matched, we know it has both group
    # 1 (the variable name) and 2 (the fallback value). group(1, 2) returns
    # both. Call vars.get(variable, fallback).
    nvalue = _placeholder.sub(lambda match: vars.get(*match.group(1, 2)),
                              value)

    # But wait, we're not done yet! Let string.Template do the rest.
    try:
        return string.Template(nvalue).substitute(vars)
    except ValueError as err:
        # invalid substitution syntax
        raise ConfigurationError("in configuration string %r: %s" % (value, err))
    except KeyError as err:
        # undefined required variable
        raise ConfigurationError("configuration string %r references "
                                 "undefined variable $%s" % (value, str(err).strip("'")))
