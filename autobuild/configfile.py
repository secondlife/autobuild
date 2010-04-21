# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

"""
API to access the autobuild package description config file.

This includes the ConfigFile class which is used to load, save,
and manipulate autobuild XML configuration files. Also the
PackageInfo class that encapsulates all the metadata for a 
single package description.

Author : Martin Reddy
Date   : 2010-04-13
"""

import os
import common
from llbase import llsd

BUILD_CONFIG_FILE="autobuild.xml"
PACKAGES_CONFIG_FILE="packages.xml"
INSTALLED_CONFIG_FILE="installed-packages.xml"

class PackageInfo(dict):
    """
    The PackageInfo class describes all the metadata for a single
    package in a ConfigFile. This is essentially a dictionary, so
    you can always access fields directly. Additionally, a number
    of accessors are provide for common metadata entries, such as
    copyright, description, and the various platform urls etc.

    The following code shows how to output the package description
    in a human-readable form, where pi is of type PackageInfo.

    print "Copyright:", pi.copyright
    print "Description:", pi.description

    Setting a key's value to None will remove that key from the
    PackageInfo structure. For example, the following will cause the
    copyright field to be removed from the package description.
    
    pi.copyright = None

    See the supported_properties dict for the set of currently
    supported properties. These map to fields of the same name in the
    config file.

    Also, see the supported_platform_properties dict for the set of
    platform-specific fields. These support a property that returns the
    list of platforms that have a definitions for that field. There are
    also explicit getter/setter methods to support these. The getter 
    will return the definition for the platform 'common' if the specified
    platform is not defined (or None if neither are defined). E.g.,

    for platform in pi.packages:
        print platform
        print pi.archives_url(platform)
        print pi.archives_md5(platform)

    for platform in pi.manifest:
        print platform
        print pi.manifest_files(platform)

    """

    # basic read-write properties that describe the package
    supported_properties = {
        'copyright' :   'The copyright statement for the source code',
        'summary' :     'A one-line overview of the package',
        'description':  'A longer description of the package',
        'license':      'The name of the software license (not the full text)',
        'licensefile':  'The relative path to the license file in the archive',
        'homepage':     'The home page URL for the source code being built',
        'uploadtos3':   'Whether the package should also be uploaded to Amazon S3',
        'source':       'URL where source for package lives',
        'sourcetype':   'The form of the source, e.g., archive, svn, hg, pypi',
        'sourcedir':    'The directory where sources extract/checkout to',
        'builddir':     'The directory where the build command installs into',
        'version':      'The current version of the source package',
        'patches':      'A list of patch(1) files to apply to the sources',
        'obsoletes':    'List of packages to uninstalled when this one is installed',
        }

    # platform-specific read-only properties that list the defined platforms
    supported_platform_properties = {
        'archives':     'List of platform-specific archives for the install command',
        'dependencies': 'List of packages that this package depends upon to build',
        'configure':    'List of platform-specific commands to configure the build',
        'build':        'List of platform-specific commands to build the software',
        'postbuild':    'Post build commands to relocate files in the builddir',
        'manifest':     'List of platform-specific commands to build the software',
        }

    def __getattr__(self, name):
        if self.supported_properties.has_key(name):
            return self.get_key(name)
        if self.supported_platform_properties.has_key(name):
            return self.__platform_list(name.replace("Platforms", ""))
        raise RuntimeError('%s is not a supported property' % name)

    def __setattr__(self, name, value):
        if self.supported_properties.has_key(name):
            return self.set_key(name, value)
        if self.supported_platform_properties.has_key(name):
            raise RuntimeError("%s is a read-only property" % name)
        raise RuntimeError('%s is not a supported property' % name)

    def archives_url(self, platform):
        # *TODO: remove legacy support for 'packages'
        url = self.__platform_key('archives', platform, 'url')
        if not url:
            url = self.__platform_key('packages', platform, 'url')
        return url
    def set_archives_url(self, platform, value):
        return self.__set_platform_key('archives', platform, 'url', value)
    def archives_files(self, platform):
        return self.__platform_key('archives', platform, 'files')
    def set_archives_files(self, platform, value):
        return self.__set_platform_key('archives', platform, 'files', value)
    def archives_md5(self, platform):
        # *TODO: remove legacy support for 'packages'
        md5sum = self.__platform_key('archives', platform, 'md5sum')
        if not md5sum:
            md5sum = self.__platform_key('packages', platform, 'md5sum')
        return md5sum
    def set_archives_md5(self, platform, value):
        return self.__set_platform_key('archives', platform, 'md5sum', value)

    def dependencies_url(self, platform):
        return self.__platform_key('dependencies', platform, 'url')
    def set_dependencies_url(self, platform, value):
        return self.__set_platform_key('dependencies', platform, 'url', value)
    def dependencies_md5(self, platform):
        return self.__platform_key('dependencies', platform, 'md5sum')
    def set_dependencies_md5(self, platform, value):
        return self.__set_platform_key('dependencies', platform, 'md5sum', value)

    def configure_command(self, platform):
        return self.__platform_key('configure', platform, 'command')
    def set_configure_command(self, platform, value):
        return self.__set_platform_key('configure', platform, 'command', value)

    def build_command(self, platform):
        return self.__platform_key('build', platform, 'command')
    def set_build_command(self, platform, value):
        return self.__set_platform_key('build', platform, 'command', value)

    def post_build_command(self, platform):
        return self.__platform_key('postbuild', platform, 'command')
    def set_post_build_command(self, platform, value):
        return self.__set_platform_key('postbuild', platform, 'command', value)

    def manifest_files(self, platform):
        return self.__platform_key('manifest', platform, 'files')
    def set_manifest_files(self, platform, value):
        return self.__set_platform_key('manifest', platform, 'files', value)

    def get_key(self, key):
        return self.get(key)
    def set_key(self, key, value):
        if value is None:
            if self.has_key(key):
                del self[key]
        else:
            self[key] = value

    def __platform_list(self, container):
        if self.has_key(container):
            return self[container].keys()
        return []
    def __platform_key(self, container, platform, key):
        try:
            return self[container][platform][key]
        except KeyError:
            try:
                return self[container]['common'][key]
            except KeyError:
                return None
    def __set_platform_key(self, container, platform, key, value):
        if not self.has_key(container):
            self[container] = {}
        if not self[container].has_key(platform):
            self[container][platform] = {}
        if value is None:
            if self[container][platform].has_key(key):
                del self[container][platform][key]
        else:
            self[container][platform][key] = value
        

class ConfigFile(object):
    """
    An autobuild configuration file contains all the package and
    for a build or an install. Using the ConfigFile class, you
    can read, manipulate, and save autobuild configuration files.

    Conceptually, a ConfigFile contains a set of named PackageInfo 
    objects that describe each package. This generic format is used
    by several autobuild files, such as packages.xml, autobuild.xml,
    and installed-packages.xml.

    Here's an example of reading a configuration file and printing
    some interesting information from it:

    c = ConfigFile()
    c.load()
    print "No. of packages =", c.package_count
    for name in c.package_names:
        package = c.package(name)
        print "Package '%s'" % name
        print "  Description: %s" % package.description
        print "  Copyright: %s" % package.copyright

    And here's an example of modifying some data in the config file
    and writing the file back to disk. In this case, changing the
    description field for every package in the config file.

    c = ConfigFile()
    c.load()
    for name in c.package_names:
        package = c.package(name)
        package.description = "Lynx woz here"
        c.set_package(name, package)
    c.save()

    """
    def __init__(self):
        self.filename = None
        self.packages = {}
        self.changed = False

    def load(self, config_filename=BUILD_CONFIG_FILE):
        """
        Load an autobuild configuration file. If no filename is
        specified, then the default of "autobuild.xml" will be used.
        Returns False if the file could not be loaded successfully.
        """

        # initialize the object state
        self.filename = config_filename
        self.packages = {}
        self.changed = False

        # try to find the config file in the current, or any parent, dir
        if not os.path.isabs(config_filename):
            dir = os.getcwd()
            while not os.path.exists(os.path.join(dir, config_filename)) and len(dir) > 3:
                dir = os.path.dirname(dir)
            self.filename = os.path.join(dir, config_filename)

        if not os.path.exists(self.filename):
            return False

        # load the file as a serialized LLSD
        print "Loading %s" % self.filename
        keys = llsd.parse(file(self.filename, 'rb').read())

        if keys.has_key('installables'):
            # support the old 'installables' format for a short while...
            # *TODO: remove this legacy support
            for name in keys['installables']:
                self.packages[name] = PackageInfo(keys['installables'][name])

        elif keys.has_key('package_name'):
            # support the old 'package_name' format for a short while...
            # *TODO: remove this legacy support
            self.packages[keys['package_name']] = PackageInfo(keys)

        else:
            # pull out the packages dicts from the LLSD
            for name in keys.keys():
                self.packages[name] = PackageInfo(keys[name])

    def save(self, config_filename=None):
        """
        Save the current configuration file state to disk. If no
        filename is specified, the name of the file will default
        to the same file that the config data was loaded from
        (or the explicit filename specified in a previous call to
        this save method).
        Returns False if the file could not be saved successfully.
        """
        # use the name of file we loaded from, if no filename given
        if config_filename:
            self.filename = config_filename

        # create an appropriate dict structure to write to the file
        state = {}
        for name in self.packages:
            state[name] = dict(self.packages[name])

        # try to write out to the file
        try:
            file(self.filename, 'wb').write(llsd.format_pretty_xml(state))
        except IOError:
            print "Could not save to file: %s" % self.filename
            return False

        return True

    # return the number of packages in this file and their names
    package_count = property(lambda x: len(x.packages))
    package_names = property(lambda x: x.packages.keys())

    # test whether the file is empty, i.e., contains no packages
    empty = property(lambda x: len(x.packages) == 0)

    # check that a file contains only 1 package, and return it (or None)
    package_definition = property(lambda x: len(x.packages) == 1 and \
                                  x.packages[x.packages.keys()[0]] or None)

    def package(self, name):
        """
        Return a PackageInfo object for the named package in this
        config file.  None will be returned if no such named package
        exists.
        """
        if not self.packages.has_key(name):
            return None
        return self.packages[name]

    def set_package(self, name, value):
        """
        Add/Update the PackageInfo object for a named package to this
        config file. This will overwrite any existing package
        description with the same name.
        """
        self.packages[name] = value
        self.changed = True
