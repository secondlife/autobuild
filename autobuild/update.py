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


from common import AutobuildError, get_version_tuple
# Please do NOT import configfile data classes! See comments for _register().
# or Executable either, which also changes with AUTOBUILD_CONFIG_VERSION
from configfile import AUTOBUILD_CONFIG_VERSION
import logging
import shlex

logger = logging.getLogger('autobuild.update')


class UpdateError(AutobuildError):
    pass

# ****************************************************************************
#   Updater management machinery
# ****************************************************************************
# A map of updaters keyed by 'from' version string, each with a list of ('to'
# version, conversion function) pairs.
_updaters = {}

# Do not directly manipulate _updaters. Register each converter using this
# _register() function.
#
# 'fromver' and 'tover' are string literals of the form '1.1' or '1.3'.
# Do NOT pass the variable AUTOBUILD_CONFIG_VERSION as 'tover'! Register each
# converter with string literals. AUTOBUILD_CONFIG_VERSION will change later,
# but your conversion function's target version will not!
#
# Each conversion function accepts a dict in the syntax appropriate to its
# 'from' version key and returns an updated dict in 'to' version format, as if
# the original LLSD file had been written that way. Or it may raise
# UpdateError if the conversion is not possible.
#
# It is explicitly okay to modify the passed dict data: your converter need
# not copy it. (Of course, you may need to copy anyway if you're modifying the
# dict or a subdict while iterating through it.)
#
# Each converter should manipulate incoming file data as LLSD (using dict
# access) rather than using configfile classes because the configfile class
# definitions will CHANGE! That is, if you write your '1.1' to '1.2' converter
# using the 1.2 configfile classes, your code will be wrong when you import
# the 1.3 version of configfile. But as long as you code your converter
# strictly in terms of dict manipulation, it will continue to properly convert
# 1.1 configfile data to 1.2 format -- at which point we can pass it through a
# '1.2' to '1.3' converter with similar constraints. Finally we can load the
# '1.3' dict data into our 1.3 configfile classes. configfile data classes
# should only ever have to deal with version-appropriate dict data.
def _register(fromver, tover, func):
    # Each fromver accesses a list of pairs. Create or extend that list with
    # this new pair.
    _updaters.setdefault(fromver, []).append((tover, func))

# Get a list of (fromver, tover, converter) triples to apply in succession to
# bring incoming LLSD in 'version' format up to AUTOBUILD_CONFIG_VERSION
# format. AUTOBUILD_CONFIG_VERSION is the format version compatible with the
# current configfile classes.
# May raise UpdateError if it cannot convert all the way.
def _get_applicable_updaters(configname, version):
    # You will be relieved that despite the titillating observation that in
    # general this suite of converters forms a DAG, I ruthlessly repressed the
    # temptation to implement a graph search to find the lowest-cost path from
    # the saved version to the current version. That would handle the case in
    # which, say, we start with a version 1.1 file but are currently at
    # version 1.4, with converters from 1.1 -> 1.2, 1.1 -> 1.3 and 1.2 -> 1.4.
    # Our current algorithm would seize the 1.1 -> 1.3 converter and then be
    # stumped (no backtracking). However, this situation is easily avoided by
    # a conscientious maintainer.
    # (But see http://www.inf.puc-rio.br/~roberto/docs/MCC15-04.pdf section
    # 5.3 "Goal-oriented programming" for how Python generators can solve that
    # general problem.)

    result = []
    seen = set()

    intermediate_version = version
    while intermediate_version != AUTOBUILD_CONFIG_VERSION:
        # remember each version from which we've already converted
        seen.add(intermediate_version)
        # Obtain all converters from intermediate_version to anything.
        try:
            pairs = _updaters[intermediate_version]
        except KeyError:
            raise UpdateError("Cannot convert config file %s "
                              "from version %s format to current version %s: "
                              "no converter for %s format" %
                              (configname, version, AUTOBUILD_CONFIG_VERSION,
                               intermediate_version))
        # pairs is now a list of (tover, converter) pairs. Sort them by
        # descending 'tover' -- remembering to compare version tuples rather
        # than raw version strings.
        # I see no downside to sorting the list in-place in its dict entry.
        pairs.sort(key=lambda p: get_version_tuple(p[0]), reverse=True)
        # At this point pairs[0] contains the highest tover for which we have
        # a converter.
        tover, func = pairs[0]
        # Defend against infinite loops. This is just an assert because the
        # presence of a loop in our suite of converters is an autobuild
        # maintenance error, not a user error.
        assert tover not in seen, "updater loop in update.py"
        # Build appropriate triple into output list and carry on.
        result.append((intermediate_version, tover, func))
        intermediate_version = tover

    # ta daa, we've reached AUTOBUILD_CONFIG_VERSION!
    return result

def convert_to_current(configname, config):
    """
    Pass the LLSD config data read from file configname.
    Returns (config data, None) if it's already at the current version -- or
    (modified config data, original version) if modified from its original
    format by whatever applicable converters we found -- or raises
    UpdateError.
    """
    try:
        version = config["version"]
    except KeyError:
        # There was an original autobuild.xml format that predated the
        # introduction of the version key. But that's so old that even as of
        # version 1.1 we refused to deal with it. (This weasels out of the
        # problem of what "original version" to return, since None is
        # obviously wrong here.)
        raise UpdateError("""incompatible configuration file %s
if this is a legacy format autobuild.xml file, please try the workaround found here:
https://wiki.lindenlab.com/wiki/Autobuild/Incompatible_Configuration_File_Error""" % configname)

    triples = _get_applicable_updaters(configname, version)
    if not triples:
        # no update needed
        return config, None

    # updates needed, apply them
    for fromver, tover, converter in triples:
        # info message clarifies the context in which a subsequent error might
        # appear
        logger.warn("Converting %s data from format version %s to version %s..." %
                    (configname, fromver, tover))
        config = converter(config)
        # update the version string in the config data; don't require every
        # converter to do that independently; easy to forget
        config["version"] = tover

    return config, version

# ****************************************************************************
#   Updaters
# ****************************************************************************
# -------------------------------- 1.1 -> 1.2 --------------------------------
class _Update_1_1(object):
    """
    Converts a 1.1 version configuration to 1.2.
    """
    package_properties = {
        'name': 'name',
        'copyright': 'copyright',
        'description': 'description',
        'license': 'license',
        'licensefile': 'license_file',
        'homepage': 'homepage',
        'version': 'version',
    }

    archive_properties = {
        'md5sum': 'hash',
        'url': 'url',
    }

    # The functions below snapshot the format version 1.2 configfile data
    # class definitions. (In fact I coded them by interactively importing the
    # version 1.2 configfile and typing e.g.:
    # pprint(PackageDescription("unnamed")).) They're capitalized like the
    # corresponding class names so it's obvious what's being produced; like
    # the class constructors, each of these functions returns an
    # appropriately-filled dict instance.
    @staticmethod
    def PackageDescription(name):
        return {'copyright': None,
                'install_dir': None,
                'license': None,
                'license_file': None,
                'name': name,
                'platforms': {},
                'version': None}

    @staticmethod
    def ArchiveDescription():
        return {'format': None, 'hash': None, 'hash_algorithm': None, 'url': None}

    @staticmethod
    def BuildConfigurationDescription():
        return {'build': None, 'configure': None, 'default': False}

    @staticmethod
    def PlatformDescription():
        return {'archive': None,
                'build_directory': None,
                'configurations': {},
                'manifest': []}

    @staticmethod
    def Executable(command, arguments):
        return {'arguments': arguments,
                'command': command,
                'filters': None,
                'options': []}


    def __call__(self, old_config):
        assert old_config['version'] == '1.1'
        config = old_config.copy()
        if 'package_definition' in old_config:
            old_package = old_config['package_definition']
            package_description = self.PackageDescription('unnamed')
            config["package_description"] = package_description
            self._insert_package_properties(old_package, package_description)
            self._insert_command('configure', old_package.get('configure', {}), package_description)
            self._insert_command('build', old_package.get('build', {}), package_description)
            for (platform_name, manifest) in old_package.get('manifest', {}).iteritems():
                self._get_platform(platform_name, package_description)["manifest"] = \
                    manifest.get('files', [])
        else:
            raise UpdateError('no package description')
        if 'installables' in old_config:
            for (old_package_name, old_package) in old_config['installables'].iteritems():
                package = self.PackageDescription(old_package_name)
                self._insert_package_properties(old_package, package)
                self._insert_archives(old_package['archives'], package)
                config["installables"][old_package_name] = package
        return config

    def _insert_package_properties(self, old_package, package):
        for (key, value) in self.package_properties.iteritems():
            if key in old_package:
                package[value] = old_package[key]
    
    def _insert_archives(self, old_archives, package):
        for (platform_name, old_archive) in old_archives.iteritems():
            platform = self._get_platform(platform_name, package)
            archive = self.ArchiveDescription()
            platform["archive"] = archive
            for (key, value) in self.archive_properties.iteritems():
                archive[value] = old_archive[key]
   
    def _insert_command(self, type, old_commands, package):
        for (platform_name, old_command) in old_commands.iteritems():
            platform = self._get_platform(platform_name, package)
            #FIXME: find a better way to choose the default configuration.
            default_configuration = 'RelWithDebInfo'
            if default_configuration in platform["configurations"]:
                build_configuration = platform["configurations"][default_configuration]
            else:
                build_configuration = self.BuildConfigurationDescription()
                build_configuration["name"] = default_configuration
                platform["configurations"][default_configuration] = build_configuration
            if 'command' in old_command:
                tokens = shlex.split(old_command['command'])
                command = tokens.pop(0)
                # It is pretty much impossible to infer where the options end and the arguments 
                # begin since we don't know which options take values, so make everything an
                # argument. Parent options will come before arguments so things should probably work
                # as expected.
                build_configuration[type] = self.Executable(command=command, arguments=tokens)
                build_configuration["default"] = True
            if 'directory' in old_command:
                platform["build_directory"] = old_command['directory']
    
    def _get_platform(self, platform_name, package):
        if platform_name in package["platforms"]:
            return package["platforms"][platform_name]
        else:
            platform = self.PlatformDescription()
            platform["name"] = platform_name
            package["platforms"][platform_name] = platform
            return platform

_register('1.1', '1.2', _Update_1_1())

# -------------------------------- 1.2 -> 1.3 --------------------------------
# We don't actually convert from 1.2: 1.3 introduces a new requirement, but we
# can't implicitly derive the new version_file attribute from 1.2 data. This
# change is handled elsewhere: autobuild_tool_build.py. Nonetheless we need a
# no-op converter, else we blow up with inability to convert the file forward.
_register('1.2', '1.3', lambda config: config)
