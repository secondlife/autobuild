#!/usr/bin/env python
"""\
@file package.py
@date 2008-05-08
@brief package up binaries from repository for removal to external source

$LicenseInfo:firstyear=2008&license=internal$

Copyright (c) 2008-2009, Linden Research, Inc.

The following source code is PROPRIETARY AND CONFIDENTIAL. Use of
this source code is governed by the Linden Lab Source Code Disclosure
Agreement ("Agreement") previously entered between you and Linden
Lab. By accessing, using, copying, modifying or distributing this
software, you acknowledge that you have been informed of your
obligations under the Agreement and agree to abide by those obligations.

ALL LINDEN LAB SOURCE CODE IS PROVIDED "AS IS." LINDEN LAB MAKES NO
WARRANTIES, EXPRESS, IMPLIED OR OTHERWISE, REGARDING ITS ACCURACY,
COMPLETENESS OR PERFORMANCE.
$/LicenseInfo$
"""

import sys
import os.path

# canonical path of parent directory, avoiding symlinks
script_path = os.path.dirname(os.path.realpath(__file__))
base_path = os.path.dirname(script_path)


import os
import popen2
import tarfile
import md5
import optparse
import time
import glob
import re
import shutil
import urllib2
import install

#
# Talking to remote servers
#

class Connection(object):
    """Shared methods for managing connections.
    """
    def fileExists(self, url):
        """Test to see if file rxists on server.  Returns boolean.
        """
        try:
            response = urllib2.urlopen(url)
        except urllib2.HTTPError, e:
            if e.code == 404:
                return False
            raise
        else:
            return True


class SCPConnection(Connection):
    """Manage uploading files.  Never overwrite existing files.
    """
    def __init__(self, server="install-packages.lindenlab.com", 
                 dest_dir="/local/www/install-packages/doc"): 
        self.setDestination(server, dest_dir)
        self.findSCPExecutable()

    # *TODO: make this method 'static'?
    # *TODO: fix docstring -- current docsctring should be comment in Pkg class
    def upload(self, files, server=None, dest_dir=None, dry_run=False):  
        """Do this for all packages all the time!  
        This is how we maintain backups of tarfiles(!!!).  Very important.
        @param filename Fully-qualified name of file to be uploaded
        """
        uploadables = []
        for file in files:
            if self.SCPFileExists(file, server, dest_dir):
                print ("Info: A file with name '%s' in dir '%s' already exists on %s. Not uploading." % (self.basename, self.dest_dir, self.server))
            else:
                uploadables.append(file)
        if uploadables:
            scp_list = " ".join(uploadables)
            print "Uploading to: %s" % self.scp_dest
            if not self.scp_executable:
                self.findSCPExecutable()
            scp_str = " ".join((self.scp_executable, scp_list, 
                                self.scp_dest))
            if dry_run:
                print scp_str
            else:
                os.system(scp_str)  # interactive -- possible password req'd

    def SCPFileExists(self, filename, server=None, dest_dir=None):
        """Set member vars and check if file already exists on dest server.
        @param filename Full path to file to be uploaded.
        @param server If provided, specifies server to upload to.
        @param dest_dir If provided, specifies destination directory on server.
        @return Returns boolean indicating whether file exists on server.
        """
        self.setDestination(server, dest_dir)
        self.loadFile(filename)
        return self.fileExists(self.url)

    def setDestination(self, server, dest_dir):
        """Set destination to dest_dir on server."""
        if server:
            self.server = server
        if dest_dir != None:  # allow: == ""  
            self.dest_dir = dest_dir
        if not self.server or self.dest_dir == None:
            raise SCPConnectionError("Both server and dest_dir must be set.")
        self.scp_dest = ':'.join([self.server, self.dest_dir]) 

    def getSCPUrl(self, filename):
        """Return the url the pkg would be at if on the server."""
        self.loadFile(filename)
        return self.SCPurl

    def loadFile(self, filename):
        """Set member vars based on filename."""
        self.filename = filename
        self.basename = os.path.basename(filename)
        # at final location, should be in root dir of served dir
        self.url = "http://" + self.server + "/" + self.basename
        self.SCPurl = "scp:" + self.scp_dest + "/" + self.basename

    def findSCPExecutable(self):
        """Cross-platform way to find exisiting scp executable."""
        pathsep = os.pathsep
        path = os.environ.get('PATH')
        # try taking advantage of possible existing tunnel using putty first
        executables = ['pscp', 'pscp.exe', 'scp', 'scp.exe']
        for p in path.split(pathsep):
            for e in executables:
                found = glob.glob(os.path.join(p, e))
                if found:
                    break
            if found:
                break
        if not found:
            # Possible expected condition.  Exit gracefully.
            print "scp or pscp executable not found.  Verify that an scp executable is in your path. Quitting."
            sys.exit(0)
        self.scp_executable = e


# *TODO make this use boto.s3 or something
class S3Connection(Connection):
    """Twiddly bits of talking to S3.  Hi S3!
    """
    exec_location = script_path      # offer option to specify this?
    exec_name = "s3curl.pl"
    S3executable = os.path.join(exec_location, exec_name)

    # keep S3 url http instead of https 
    amazonS3_server = "http://s3.amazonaws.com/"
    S3_upload_params = {
            "S3_id": "--id=1E4G7QTW0VT7Z3KJSJ02",
            "S3_key": "--key=GuchuxQF1ADPCz3568ADS/Vc5bds807e7pj1ybU+",
            "perms": "--acl=public-read",
                        }
                    
    def __init__(self, S3_dest_dir):
        """Set server dir for all transactions.  
        Alternately, use member methods directly, supplying S3_dest_dir.
        """
        # here by design -- server dir should be specified explicitly 
        self.S3_dest_dir = S3_dest_dir
        self._server_dir = self.amazonS3_server + self.S3_dest_dir  

    def upload(self, filename, S3_dest_dir=None, dry_run=False):
        """Upload file specified by filename to S3.  
        If file already exists at specified destination, raises exception.
        NOTE:  Knowest whither thou uploadest! Ill fortune will befall 
        those who upload blindly.
        """
        if sys.platform == 'win32':
            print ("\nError: Cannot upload to S3.  Helper script 's3curl.pl' is not Windows-compatible. Try uploading from a unix environment, or see the wiki for uploading to S3 from Windows.")
            sys.exit(0)
        if self.S3FileExists(filename, S3_dest_dir):
            print ("Info: A file with name '%s' in dir '%s' already exists on S3. Not uploading." % (self.basename, self.S3_dest_dir))
        else:  # elsing explicitly just because it makes me feel better. crazy?
            print "Uploading to: %s" % self.url
            # use os.system for command-line visibility
            params = ["perl", self.S3executable]  # windows users may not have file association 
            params.extend(self.S3_upload_params.values())
            params.append(self.last_S3_param)
            exec_str = " ".join(params)
            #print "Executing: %s" % exec_str
            if dry_run:
                print exec_str 
            else:
                os.system(exec_str)
        
    def S3FileExists(self, filename, S3_dest_dir=None):
        """Set class vars and check if url for file exists on S3.
        @param filename Filename (incl. path) of file to be uploaded.
        @param S3_dest_dir If provided, (re-)sets destination dir on S3.
        @return Returns boolean indicating whether file already exists on S3.
        """
        self.setS3DestDir(S3_dest_dir)
        self.setS3FileParams(filename)
        return self.fileExists(self.url)

    def setS3DestDir(self, S3_dest_dir):
        """Set class vars for the destination dir on S3."""
        if S3_dest_dir != None:  # allow: == "" 
            self.S3_dest_dir = S3_dest_dir
        if self.S3_dest_dir == None:  
            raise S3ConnectionError("Error: S3 destination directory must be set.")
        self._server_dir = self.amazonS3_server + self.S3_dest_dir  
        
    def getUrl(self, filename):
        """Return the url the pkg would be at if on the server."""
        self.setS3FileParams(filename)
        return self.url

    def setS3FileParams(self, filename):
        """Set parameters for upload that are file specific."""
        self.basename = os.path.basename(filename)
        self.url = self._server_dir + "/" + self.basename
        # yes, the " " really belongs after the "--".  Strange.
        self.last_S3_param = "-- " + self.url
        self.S3_upload_params['putstr'] = "--put="+filename
        

class ConnectionError(Exception):
    def __init__(self,msg):
        self.msg = msg
        
    def __str__(self):
        return repr(self.msg)

class S3ConnectionError(ConnectionError):
    pass

class SCPConnectionError(ConnectionError):
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
        """Populate list of ConfigFile objects.
        """
        filename = self.pkgname + ".txt"
        for platform in self.platforms:
            # setting config filename - make more explicit?
            conf_filename = os.path.join(self.config_dir, platform, filename)
            if self.requireConfigFile and not os.path.exists(conf_filename):
                # Possible expected case.  Exit gracefully
                print ValueError("Config file '%s' for library '%s' does not exist.  Please create config file.%s(Use -h for help)" % (conf_filename, self.pkgname, os.linesep))
                sys.exit(0)
            if os.path.exists(conf_filename):
                self.confFiles[platform] = ConfigFile(conf_filename)

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
             print ("\nError: Config directory '%s' does not exist. %s(Use -h for help)" % (config_dir, os.linesep))
             sys.exit(0)
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


class ConfigFile(object):
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


# The following two functions are used directly by main.
def dissectTarfileName(tarfilename, possible_platforms):
    """Try to get important parts from tarfile.
    @param tarfilename Fully-qualified path to tarfile to upload.
    """
    basename = os.path.basename(tarfilename)
    # filename example:
    # expat-1.95.8-darwin-20080810.tar.bz2
    # tear apart filename to get pkg info
    platform_string = None
    for p in possible_platforms:
        platform_string = getPlatformString(p)
        if re.compile('.*'+platform_string+'.*').match(basename):
            break
    if not platform_string:
        print ("Error: tarfilename must be canonical.  Does not contain platform string. Quitting.")
        sys.exit(0)
    # split on platform str in filename (returns before and after this str)
    parts = re.split(platform_string, basename)
    pkgname = re.split('[\.0-9]+[a-z]*-*', parts[0])[0]  # remove version
    pkgname = pkgname.rstrip('-')  # strip remaining '-' 
    return (pkgname, platform_string)

def checkTarfileForUpload(tarfilename, possible_platforms, S3ables, check=False):
    """Get status on S3ability of a tarfile.  Returns boolean."""
    pkgname, platform = dissectTarfileName(tarfilename, possible_platforms)
    up = False
    if S3ables:
        if pkgname in S3ables:
            up = True
    elif check:
        print ("%s not yet confirmed uploadable to S3." % tarfilename)
        go = raw_input("Is this package cleared for open-source distribution? (Answer no if not sure) (y/N) ")
        if go == 'y':
            up = True
    return up


#
# Running install.py
#

class Installer(object):
    """Manage data maintained in install.xml using install.py. 
    - what if package has not yet been added? (FAIL)
    """
    exec_location = script_path
    exec_name = "install.py"
    executable = os.path.join(exec_location, exec_name)
    
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        pass
    
    def quick_add(self, tarfilename, url, possible_platforms):
        """Parsing simplified input to make user's interface simpler.
        @param tarfilename Fully-qualified path to tarfile to upload.
        """
        pkgname, platform_string = dissectTarfileName(tarfilename, possible_platforms)
        platform = platform_string.strip('-').replace('-', '/')
        md5sum = self.getMd5Sum(tarfilename)
        print tarfilename + ':'
        self.add_installable(pkgname, platform, url, md5sum)
        
    def getMd5Sum(self, tarfilename):
        md5hash = md5.new(file(tarfilename, 'rb').read())
        md5sum = md5hash.hexdigest()
        return md5sum
                              
    def add_installable(self, pkgname, platform, url, md5sum):
        """Updates install.xml with new tarfile via install.py"""
        # This simply fails if the installable is not yet added to install.xml
        kwargs = {
            'pkgname':      "--add-installable-package=" + pkgname,
            'platform':     "--package-platform=" + platform,
            'url':          "--package-url=" + url,
            'md5sum':       "--package-md5=" + md5sum,
                 }
        cmd = [self.executable]
        cmd.extend(kwargs.values())
        p_cmd = " ".join(cmd)
        print "Running install.py: " + p_cmd
        if not self.dry_run:
            # use os.system for possible command-line interaction
            os.system(p_cmd)


#
# Command-line interface.
#

def parse_args():
    parser = optparse.OptionParser(
        usage="\n    %prog -t expat GL\n    %prog -u ../tarfile_tmp/expat-1.2.5-darwin-20080810.tar.bz2\n    %prog -i ./tmp/zlib*.tar.bz2 ../glh_lin*.bz2", 
        description="""Create tar archives from library files, and upload as appropriate.  Tarfiles will be formed from paths as specified in config files found in assemblies/3rd_party_libs from same tree as execution location of this script, or alternately 'configdir', if supplied as a command-line argument.""")
    parser.add_option(
        '-t', 
        action='store_true',
        default=False,
        dest='make_tarfile',
        help='Make tar archive(s).  List names of specific libraries, or leave unspecified to package all known libraries.  Use with --version and --platform.')
    parser.add_option(
        '--version', 
        type='string',
        default="",
        dest='version',
        help='Overrides the version number for the specified library(ies).  If unspecified, the version number in "versions.txt" (in configdir) will be used, if present.  Can be left blank.')
    parser.add_option(
        '--platform', 
        type='string',
        default=None,
        dest='platform',
        help="Specify platform to use: linux, linux64, darwin, or windows.  Left unspecified, all three platforms will be used.")
    parser.add_option(
        '-u', '--upload', 
        action='store_true',
        default=False,
        dest='upload',
        help='Upload tarfile(s). List paths to tarfiles to be uploaded (supports glob expressions).  Use with --s3 option if appropriate (read about --s3 option).')
    parser.add_option(
        '-i', '--install', 
        action='store_true',
        default=False,
        dest='install',
        help='Update install.xml with the data for the specified tarfile(s). List paths to tarfiles to update (supports glob expressions).  Use --s3 option if appropriate (read about --s3 option).')
    group = optparse.OptionGroup(parser, "S3 Uploading", "*NOTE*: S3 upload does not work on Windows, since command-line tool (s3curl.pl) is not supported there.  Either perform S3 uploads from a unix machine, or see wiki for uploading to S3 from Windows.")
    
    group.add_option(
        '-s', '--s3', 
        action='store_true',
        default=False,
        dest='s3',
        help='Indicates tarfile(s) belong on S3.  If unspecified, "S3ables.txt" (in configdir) will be used to determine which libraries are stored on S3.  Please verify clearance for public distribution prior to uploading any new libraries to S3.')
    parser.add_option(
        '--configdir', 
        type='string',
        default=os.path.join(base_path, "assemblies/3rd_party_libs"),
        dest='configdir',
        help='Specify the config directory to use.  Defaults to "assemblies/3rd_party_libs" in same tree as script execution.  If configdir specified, tarfiles will be assembled relative to root of tree containing configdir.')
    parser.add_option(
        '--tarfiledir', 
        type='string',
        default="",
        dest='tarfiledir',
        help='Specify the directory in which to store new tarfiles.  Defaults to "tarfile_tmp".')
    parser.add_option(
        '--dry-run', 
        action='store_true',
        default=False,
        dest='dry_run',
        help='Show what would be done, but don\'t actually do anything.')
    parser.add_option_group(group)
    return parser.parse_args()


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


def getPlatform(platform_string):
    return platform_string.strip('-').replace('-', '/')

# better way to do this?
S3server_dir = "viewer-source-downloads/install_pkgs"
S3Conn = S3Connection(S3server_dir)

SCPConn = SCPConnection()

def main():
    options, args = parse_args()
    config_dir = os.path.realpath(options.configdir)
    tarfiledir = options.tarfiledir

    S3ables = []
    try:  # building list of libraries uploadable to S3
        S3ables_file = os.path.join(config_dir, 'S3ables.txt')
        S3ables = ConfigFile(S3ables_file).filelist
    except:
        pass
    
    platforms = ['windows', 'linux', 'linux64', 'darwin']
    if options.platform:
        platforms = [options.platform]

    # make tarfiles 
    if options.make_tarfile:   
        pkg = Package(args, platforms, config_dir, tarfiledir, options.dry_run)
        pkg.createAll(options.version)
    # upload to servers
    if options.upload:   
        if not args:
            print ("Error: no tarfiles specified to upload. %s(Use -h for help)" % os.linesep)
            sys.exit(0)
        # mmm, globs...
        tarfiles = []
        for a in args:
            tarfiles.extend(glob.glob(a))
        if not tarfiles:
            print ("No files found matching '%s'. Quitting (nothing to upload).%s(Use -h for help)" % (" ".join(args), os.linesep))
            sys.exit(0)
        SCPConn.upload(tarfiles, None, None, options.dry_run)
        for tarfilename in tarfiles:
            up = checkTarfileForUpload(tarfilename, platforms, S3ables, check=options.s3)
            if up:
                if not SCPConn.SCPFileExists(tarfilename):
                    raise SCPConnectionError("Error: File must exist on internal server before uploading to S3")
                S3Conn.upload(tarfilename, None, options.dry_run)
    # add to install.xml via install.py
    if options.install:
        if not args:
            print ("Error: no tarfiles specified to install. %s(Use -h for help)" % os.linesep)
            sys.exit(0)
        # mmm, globs...
        tarfiles = []
        for a in args:
            tarfiles.extend(glob.glob(a))
        if not tarfiles:
            print ("No files found matching '%s'. Quitting (nothing to process).%s(Use -h for help)" % (" ".join(args), os.linesep))
            sys.exit(0)
        for tarfilename in tarfiles:
            # NOTE: this will add entry to install.xml regardless of whether
            # file exists on server
            tarfilename = os.path.realpath(tarfilename)
            basename = os.path.basename(tarfilename)
            S3able = checkTarfileForUpload(tarfilename, platforms, S3ables, check=options.s3)
            if S3able:  
                url = S3Conn.getUrl(basename)
            else:
                url = SCPConn.getSCPUrl(basename)
            installer = Installer(options.dry_run)
            installer.quick_add(tarfilename, url, platforms)
    if not options.upload and not options.make_tarfile and not options.install:
        print "(Use -h for help)"
        sys.exit(0)

    if options.dry_run:
        print "This was only a dry-run."

if __name__ == '__main__':
    sys.exit(main())




