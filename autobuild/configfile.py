"""\
@file configfile.py
@author Martin Reddy
@date 2010-04-13
@brief API to access the autobuild package description config file.

$LicenseInfo:firstyear=2007&license=mit$

Copyright (c) 2007-2009, Linden Research, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
$/LicenseInfo$
"""

import sys
import os
import common

class PackageInfo(dict):
    """
    The PackageInfo class describes all the metadata for a single
    package in a ConfigFile. This is essentially a dictionary, so
    you can always access fields directly. Additionally, a number
    of accessors are provide for common metadata entries, such as
    copyright, description, and the various platform urls etc.

    The following code shows how to output the package description
    in a human-readable form, where pi is of type PackageInfo.

    print "Copyright:", pi.copyright()
    print "Description:", pi.description()
    print "Defined Platforms:", pi.packagePlatforms()
    for platform in pi.packagePlatforms():
        print platform,":",
        print pi.packageUrl(platform)

    You can also add new fields to a PackageInfo structure as
    follows:

    pi.setKey('mynewfiled', "The field's value")

    Setting a key's value to None with any of the provided setter
    methods will remove that key from the PackageInfo structure. For
    example:
    
    pi.setCopyright(None)

    Will cause the copyright field to be removed from the package
    description.
    """
    def copyright(self):
        return self.getKey('copyright')
    def setCopyright(self, value):
        self.setKey('copyright', value)

    def description(self):
        return self.getKey('description')
    def setDescription(self, value):
        self.setKey('description', value)

    def licenseName(self):
        return self.getKey('license')
    def setLicenseName(self, value):
        self.setKey('license', value)

    def packagePlatforms(self):
        if self.has_key('packages'):
            return self['packages'].keys()
        return []
    def packageUrl(self, platform):
        return self.__platformKey('packages', platform, 'url')
    def setPackageUrl(self, platform, value):
        return self.__setPlatformKey('packages', platform, 'url', value)
    def packageMD5(self, platform):
        return self.__platformKey('packages', platform, 'md5sum')
    def setPackageMD5(self, platform, value):
        return self.__setPlatformKey('packages', platform, 'md5sum', value)

    def getKey(self, key):
        return self.get(key)
    def setKey(self, key, value):
        if value is None:
            if self.has_key(key):
                del self[key]
        else:
            self[key] = value

    def __platformKey(self, container, platform, key):
        if self.has_key(container) and self[container].has_key(platform):
            return self[container][platform][key]
        return None
    def __setPlatformKey(self, container, platform, key, value):
        if not self.has_key(container):
            self[container] = {}
        if not self[container].has_key(platform):
            self[container][platform] = {}
        if value is None:
            if self[container][platform].has_key(key):
                del self[container][platform][key]
        else:
            self[container][platform][key] = value
        

class ConfigFile:
    """
    An autobuild configuration file contains all the package and
    license definitions for a build. Using the ConfigFile class, you
    can read, manipulate, and save autobuild configuration files.

    Conceptually, a ConfigFile contains a set of named PackageInfo 
    objects that describe each package, and a set of named software
    license strings.

    Here's an example of reading a configuration file and printing
    some interesting information from it:

    c = ConfigFile()
    c.load()
    print "No. of packages =", c.packageCount()
    print "No. of licenses =", c.licenseCount()
    for name in c.packageNames():
        package = c.package(name)
        print "Package '%s'" % name
        print "  Description: %s" % package.description()
        print "  Copyright: %s" % package.copyright()

    And here's an example of modifying some data in the config file
    and writing the file back to disk. In this case, changing the
    description field for every package in the config file.

    c = ConfigFile()
    c.load()
    for name in c.packageNames():
        package = c.package(name)
        package.setDescription("Lynx woz here")
        c.setPackage(name, package)
    c.save()

    """
    def __init__(self):
        self.filename = None
        self.packages = {}
        self.licenses = {}
        self.__bootstrap()

    def load(self, config_filename=None):
        """
        Load an autobuild configuration file. If no filename is
        specified, then the default of "autobuild.xml" will be used.
        """
        if not config_filename:
            config_filename = "autobuild.xml"

        self.filename = config_filename
        self.packages = {}
        self.licenses = {}

        if not os.path.exists(self.filename):
            return False

        print "loading %s" % self.filename
        keys = llsd.parse(file(self.filename, 'rb').read())

        if keys.has_key('installables'):
            for name in keys['installables']:
                self.packages[name] = PackageInfo(keys['installables'][name])

        if keys.has_key('licenses'):
            for name in keys['licenses']:
                self.licenses[name] = keys['licenses'][name]


    def save(self, config_filename=None):
        """
        Save the current configuration file state to disk. If no
        filename is specified, the name of the file will default
        to the same file that the config data was loaded from
        (or the explicit filename specified in a previous call to
        this save method).
        """
        if config_filename:
            self.filename = config_filename

        state = {}
        state['installables'] = {}
        for name in self.packages:
            state['installables'][name] = dict(self.packages[name])

        state['licenses'] = {}
        for name in self.licenses:
            state['licenses'][name] = self.licenses[name]

        file(self.filename, 'wb').write(llsd.format_pretty_xml(state))

    def packageCount(self):
        """
        Return the number of packages described in this config file.
        """
        return len(self.packages)

    def licenseCount(self):
        """
        Return the number of licenses described in this config file.
        """
        return len(self.packages)

    def packageNames(self):
        """
        Return an array with the names of all packages in this file.
        """
        return self.packages.keys()

    def licenseNames(self):
        """
        Return an array with the names of all licenses in this file.
        """
        return self.licenses.keys()

    def package(self, name):
        """
        Return a PackageInfo object for the named package in this
        config file.  None will be returned if no such named package
        exists.
        """
        if not self.packages.has_key(name):
            return None
        return self.packages[name]

    def license(self, name):
        """
        Return the named license in this config file as a string.
        None will be returned if no such named license exists.
        """
        if not self.licenses.has_key(name):
            return None
        return self.licenses[name]

    def setPackage(self, name, value):
        """
        Add/Update the PackageInfo object for a named package to this
        config file. This will overwrite any existing package
        description with the same name.
        """
        self.packages[name] = value

    def setLicense(self, name, value):
        """
        Add/Update the string for a named license to this config
        file. This will overwrite any existing license string with the
        same name.
        """
        self.licenses[name] = value

    def __bootstrap(self):
        """
        We use llsd to parse the config file, which lives in the
        llbase package. This method deals with downloading and
        installing llbase locally to make this possible.
        """
        global llsd

        # get the directory where we keep autobuild's llbase package
        install_dir = common.getTempDir("autobuild")
        llbase_dir = os.path.join(install_dir, "lib", "python2.5")
        if llbase_dir not in sys.path:
            sys.path.append(llbase_dir)

        # define the version of llbase that we want to use
        llbase_ver = "0.2.0"
        llbase_date = "20100225"
        url = "%s/llbase-%s-%s-%s.tar.bz2" % (common.Options().getS3Url(),
                                              llbase_ver,
                                              common.getCurrentPlatform(),
                                              llbase_date)

        # download & extract the llbase package, if not done already
        if not common.isPackageInCache(url):
            print "Installing llbase %s package..." % llbase_ver
            common.downloadPackage(url)
            common.extractPackage(url, install_dir)

        # try to import the llbase package...
        try:
            from llbase import llsd
        except ImportError:
            sys.exit("Fatal Error: Could not install llbase package!")
