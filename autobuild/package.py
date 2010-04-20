# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

"""
Create archives of build output, ready for upload to the server.
"""

import sys
import os

# canonical path of parent directory, avoiding symlinks
script_path = os.path.dirname(os.path.realpath(__file__))

import tarfile
import time
import glob
import re
import urllib2
import subprocess
import common
from configfile import ConfigFile

try:
    from hashlib import md5
except ImportError:
    # for older (pre-2.5) versions of python...
    import md5 as oldmd5
    md5 = oldmd5.new

class UploadError(Exception):
    pass

class ConfigError(Exception):
    pass

#
# Talking to remote servers
#

class Connection(object):
    """Shared methods for managing connections.
    """
    def fileExists(self, url):
        """Test to see if file exists on server.  Returns boolean.
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
            print "Uploading to: %s" % self.scp_dest
            command = [get_default_scp_command()] + uploadables + [self.scp_dest]
            if dry_run:
                print " ".join(command)
            else:
                subprocess.call(command) # interactive -- possible password req'd

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
            raise UploadError("Error: Cannot upload to S3.  Helper script 's3curl.pl' is not Windows-compatible. Try uploading from a unix environment, or see the wiki for uploading to S3 from Windows.")
        if self.S3FileExists(filename, S3_dest_dir):
            print ("Info: A file with name '%s' in dir '%s' already exists on S3. Not uploading." % (self.basename, self.S3_dest_dir))
        else:  # elsing explicitly just because it makes me feel better. crazy?
            print "Uploading to: %s" % self.url
            params = ["perl", self.S3executable]  # windows users may not have file association
            params.extend(self.S3_upload_params.values())
            params.append(self.last_S3_param)
            #print "Executing: %s" % exec_str
            if dry_run:
                print " ".join(params)
            else:
                subprocess.call(params)

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


# The following two functions are used directly by main.
def dissectTarfileName(tarfilename):
    """Try to get important parts from tarfile.
    @param tarfilename Fully-qualified path to tarfile to upload.
    """
    # split_tarname() returns:
    # (path, [package, version, platform, timestamp], extension)
    # e.g. for:
    # /path/to/expat-1.95.8-darwin-20080810.tar.bz2
    # it returns:
    # ("/path/to", ["expat", "1.95.8", "darwin", "20080810"], ".tar.bz2")
    # We just want the middle list.
    tarparts = common.split_tarname(tarfilename)[1]
    try:
        # return package, platform
        return tarparts[0], tarparts[2]
    except IndexError:
        raise UploadError("Error: tarfilename %r must be canonical. Does not contain platform string." %
                          tarfilename)

def checkTarfileForUpload(config, tarfilename, check=False):
    """Get status on S3ability of a tarfile.  Returns boolean."""
    pkgname, platform = dissectTarfileName(tarfilename)

    info = config.package(pkgname)      # from tarfile name
    # TODO: Review this logic. The former S3ables machinery simply said that
    # if a package was named in S3ables, then it should be uploaded to S3. Its
    # absence from S3ables could mean either that it was unknown, or that it
    # was known and should not be uploaded to S3. Now we can distinguish
    # between an unknown package (info is None) and a known package that
    # should not be uploaded to S3 (not info.uploadtos3).
    if info is None:
        # We've never heard of this package; did user say it's okay to ask?
        if check:
            print ("%s not yet confirmed uploadable to S3." % tarfilename)
            sys.stdout.flush()
            go = raw_input("Is this package cleared for open-source distribution? (Answer no if not sure) (y/N) ")
            return go == 'y'
        # If we have no clue, and it's not okay to ask, then we don't know how
        # to proceed. A safe guess would be to skip uploading to S3 -- but
        # that presents the likelihood of nasty surprises later. Inform the
        # user.
        raise UploadError("Unknown package %s (tarfile %s) -- can't decide whether to upload to S3"
                          % (pkgname, tarfilename))
    # Here info is definitely not None.
    return info.uploadtos3



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

# This function is intended for use by another Python script. It takes a
# specific argument list.
def make_tarfile(files, platforms, config_dir, tarfiledir, version, dry_run=False):
    pkg = Package(files, platforms, config_dir, tarfiledir, dry_run)
    pkg.createAll(version)

# This function is intended for use by another Python script. It takes a
# specific argument list and indicates error by raising an exception.
def upload(wildfiles, s3check=False, dry_run=False):
    if not wildfiles:
        raise UploadError("Error: no tarfiles specified to upload.")
    # mmm, globs...
    # Cute Python trick: to "flatten" a list of lists to a single
    # concatenated list, use sum(list_of_lists, []).
    tarfiles = sum((glob.glob(a) for a in wildfiles), [])
    if not tarfiles:
        raise UploadError("No files found matching %s. Nothing to upload." %
                          " or ".join(repr(w) for w in wildfiles))

    SCPConn.upload(tarfiles, None, None, dry_run)
    # Note, this is configfile.ConfigFile rather than our own _ConfigFile
    config = ConfigFile()
    config.load()
    for tarfilename in tarfiles:
        up = checkTarfileForUpload(config, tarfilename, check=s3check)
        if up:
            # Normally, check that we've successfully uploaded the tarfile to
            # our scp repository before uploading to S3. (But why? We've just
            # put it there in the preceding lines? If we're concerned about
            # upload failure, shouldn't we notice that as part of SCPConn.
            # upload() instead of waiting until now? And the message below
            # seems to suggest more of a user operation sequence error --
            # which I think is now logically impossible -- than a network
            # failure.) In any case: if dry_run is set, we won't have uploaded
            # to our scp repository, so don't even perform this test as it
            # would definitely fail.
            if not (dry_run or SCPConn.SCPFileExists(tarfilename)):
                raise SCPConnectionError("Error: File must exist on internal server before uploading to S3")
            S3Conn.upload(tarfilename, None, dry_run)

# This function is reached from autobuild_main, which always passes generic
# optparse-style (options, args).
def make_tarfile_main(options, args):
    make_tarfile(args,
                 [options.platform] if options.platform else common.PLATFORMS,
                 os.path.realpath(options.configdir),
                 options.tarfiledir,
                 options.version,
                 options.dry_run)

    if options.dry_run:
        print "This was only a dry-run."

# This function is reached from autobuild_main, which always passes generic
# optparse-style (options, args). On error, it prints a message and
# terminates. It might also be chatty on sys.stdout.
def upload_main(options, args):
    try:
        upload(args, options.s3, options.dry_run)
    except (UploadError, SCPConnectionError), err:
        sys.exit(os.linesep.join((str(err), "(Use -h for help)")))

    if options.dry_run:
        print "This was only a dry-run."

if __name__ == '__main__':
    sys.exit("Please invoke this script using either 'autobuild package' or 'autobuild upload'")
