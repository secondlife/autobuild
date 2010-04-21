# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

"""
Create archives of build output, ready for upload to the server.
"""

import sys
import os
import tarfile
import time
import re
import common
import autobuild_base
from connection import SCPConnection, S3Connection

AutobuildError = common.AutobuildError

# better way to do this?
S3Conn = S3Connection()
SCPConn = SCPConnection()

class ConfigError(AutobuildError):
    pass

#
# Packaging library files
#

class Package(object):
    """Package metadata and methods.
    """
    def __init__(self, pkgs, platforms, config_dir, tarfiledir, dry_run=False):
        self.pkgs = pkgs
        self.platforms = platforms
        self.dry_run = dry_run

        # making assumption here about location of config dir
        self.root = os.path.dirname(os.path.dirname(config_dir))
        self._setDirs(config_dir, tarfiledir)

        self.confFiles = {}
        self.tarfiles = {}
        if self.pkgs:
            # if user lists libs at cmd line, require config files
            self.requireConfigFile = True
        else:
            self.pkgs = self.listAll()
            self.requireConfigFile = False

    def create(self):
        """Create tarfiles.
        """
        for platform in self.platforms:
            tfile = self.tarfiles[platform]
            if self.confFiles[platform]:
                filelist = self.confFiles[platform].filelist

                # move to tree root of config_dir location
                curr_dir = os.getcwd()
                os.chdir(self.root)
                # pack tarfile
                tfile.packTarfile(filelist)
                # move back
                os.chdir(curr_dir)

    def _getTarFiles(self, version=None):
        """Populate list of tarfile objects.
        """
        if version:
            self.version = version
        else:
            try:
                self._getVersion()
            except:
                self.version = ""
        for platform in self.platforms:
            tfile = _TarfileObj(self, platform, self.dry_run)
            self.tarfiles[platform] = tfile

    def _getConfFiles(self):
        """Populate list of _ConfigFile objects.
        """
        filename = self.pkgname + ".txt"
        for platform in self.platforms:
            # setting config filename - make more explicit?
            conf_filename = os.path.join(self.config_dir, platform, filename)
            if self.requireConfigFile and not os.path.exists(conf_filename):
                # Possible expected case.
                raise ValueError("Manifest for library '%s' on platform %s does not exist.  Please create manifest section in autobuild.xml." % (self.pkgname, platform))
            if os.path.exists(conf_filename):
                self.confFiles[platform] = _ConfigFile(conf_filename)

    def _getVersion(self):
        """Create version string for use in filename."""
        vfile = open(os.path.join(self.config_dir, "versions.txt"), 'rb')
        version_strs = vfile.readlines()
        vfile.close()
        version = ""
        for line in version_strs:
            line = line.rstrip(os.linesep)
            parts = line.split(':')
            if parts[0] == self.pkgname:
                version = parts[1]
                break
        self.version = version

    # *NOTE: Possibly the root dir of checkout tree should be specified
    # instead of config dir?
    def _setDirs(self, config_dir, tarfiledir):
        """Config directory must exist.  If no tarfiledir set, create default.
        """
        if not os.path.exists(config_dir):
             raise ConfigError("Error: Config directory '%s' does not exist." % config_dir)
        if not tarfiledir:
            tarfiledir = os.path.join(self.root, "tarfile_tmp")
        else:
            tarfiledir = realpath(tarfiledir)  # if relative, get full path
        if not os.path.exists(tarfiledir):
            os.makedirs(tarfiledir)
        self.config_dir = config_dir
        self.tarfiledir = tarfiledir

    def listAll(self):
        """Return list of all pkgs found in dirs listed in platforms"""
        pkgs = []
        for platform in self.platforms:
            platform_dir = os.path.join(self.config_dir, platform)
            if not os.path.isdir(platform_dir):
                continue
            for config_file in os.listdir(platform_dir):
                # skip svn files/dirs
                if re.compile('.*\.svn.*').match(config_file):
                    continue
                filename = config_file[:-4]   # chop off ".txt"
                pkgs.append(filename)
        return pkgs

    def createAll(self, version=None):
        for lib in self.pkgs:
            self.pkgname = lib
            self._getConfFiles()
            self._getTarFiles(version)
            self.create()
        print ("Tarfiles written to '%s'." % (self.tarfiledir))


class _ConfigFile(object):
    """Maintain config data for a specific package/platform combo."""

    def __init__(self, filename):
        self.filename = filename
        self.filelist = []
        self._getConfigData()
        self._cleanFileList()

    def _getConfigData(self):
        """Read config file contents."""
        fh = open(self.filename)
        self.filelist = fh.readlines()
        fh.close()

    def _cleanFileList(self):
        """Generate file list from config file contents."""
        for i,file in enumerate(self.filelist):
             self.filelist[i] = file.rstrip(os.linesep)


# *TODO: rename class?  could be clearer. Note possible namespace collision
# with 'tarfile' module.
class _TarfileObj(object):
    """Tarfile operations, including creating valid name and creating new
    tarfile from filelist.
    """
    def __init__(self, pkg_obj, platform, dry_run=False):
        # fully-qualified filename
        self.pkg_obj = pkg_obj
        self.platform = platform
        self.dry_run = dry_run
        self._setTarfileName(self.pkg_obj, self.platform)

    def getTarfileName(self):
        return self.tarfilename

    def _setTarfileName(self, pkg_obj, platform):
        """Make a name that does not collide with existing tarfiles on servers.
        """
        fname_valid = False
        l_incr = (ord('a') - 1)  # accommodate first iteration
        # first name to try has no letter extension
        ch = ""
        while not fname_valid:
            tarfilename = self._makeTarfileName(pkg_obj, platform, ch)
            if SCPConn.SCPFileExists(tarfilename) == False and \
               S3Conn.S3FileExists(tarfilename) == False:
                fname_valid = True
            else:
                l_incr = l_incr + 1
                ch = chr(l_incr)
        self.tarfilename = tarfilename

    def _makeTarfileName(self, pkg_obj, platform, ch):
        """Generate tarfile name from parameters."""
        # filename example:
        # expat-1.95.8-darwin-20080810.tar.bz2
        todays_date = self._getDate()
        platform_string = getPlatformString(platform)
        parts = (pkg_obj.pkgname, pkg_obj.version, platform_string, todays_date + ch)
        filename = '-'.join([p for p in parts if p])
        filename = filename + ".tar.bz2"
        # Setting tarfilename -- make more explicit?
        tarfilename = os.path.join(pkg_obj.tarfiledir, filename)
        return tarfilename

    def packTarfile(self, filelist):
        """Pack tarfile from files in filelist."""
        print("Making tarfile: %s" % self.tarfilename)
        if not self.dry_run:
            if not os.path.exists(self.platform):
                os.makedirs(self.platform)
            tfile = tarfile.open(self.tarfilename, 'w:bz2')
            for file in filelist:
                print file
                try:
                    tfile.add(file)
                except:
                    print ("Error: unable to add %s" % file)
                    raise
            tfile.close()

    def _getDate(self):
        """Create date string for use in filename."""
        todays_date = time.strftime("%Y%m%d")
        return todays_date



def dissectPlatform(platform):
    """Try to get important parts from platform.
    @param platform can have the form: operating_system[/arch[/compiler[/compiler_version]]]
    """
    operating_system = ''
    arch = ''
    compiler = ''
    compiler_version = ''
    # extract the arch/compiler/compiler_version info, if any
    # platform can have the form: os[/arch[/compiler[/compiler_version]]]
    [dir, base] = os.path.split(platform)
    if dir != '':
        while dir != '':
            if arch != '':
                if compiler != '':
                    compiler_version = compiler
            compiler = arch
            arch = base
            new_dir = dir
            [dir, base] = os.path.split(new_dir)
        operating_system = base
    else:
        operating_system = platform
    return [operating_system, arch, compiler, compiler_version]


def getPlatformString(platform):
    """Return the filename string tha corresponds to a platform path
    @param platform can have the form: operating_system[/arch[/compiler[/compiler_version]]]
    """
    [operating_system, arch, compiler, compiler_version] = dissectPlatform(platform)
    platform_string = operating_system
    if arch != '':
        platform_string += '-' + arch
        if compiler != '':
            platform_string += '-' + compiler
            if compiler_version != '':
                platform_string += '-' + compiler_version
    return platform_string

# This function is intended for use by another Python script. It takes a
# specific argument list.
def make_tarfile(files, platforms, config_dir, tarfiledir, version, dry_run=False):
    pkg = Package(files, platforms, config_dir, tarfiledir, dry_run)
    pkg.createAll(version)

def create_package(options, args):
    make_tarfile(args,
                 [options.platform] if options.platform else common.PLATFORMS,
                 os.path.realpath(options.configdir),
                 options.tarfiledir,
                 options.version,
                 options.dry_run)

    if options.dry_run:
        print "This was only a dry-run."

def add_arguments(parser):
    pass

# define the entry point to this autobuild tool
class autobuild_tool(autobuild_base.autobuild_base):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description='Creates archives of build output, ready for upload to the server.')

    def register(self, parser):
        add_arguments(parser)

    def run(self, args):
        create_package(args, args.package)

if __name__ == '__main__':
    sys.exit("Please invoke this script using 'autobuild %s'" %
             autobuild_tool().get_details()["name"])
