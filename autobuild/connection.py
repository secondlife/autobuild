#!/usr/bin/python
"""\
@file   connection.py
@author Nat Goodspeed
@date   2010-04-20
@brief  Classes shared between package.py and upload.py

$LicenseInfo:firstyear=2010&license=internal$
Copyright (c) 2010, Linden Research, Inc.
$/LicenseInfo$
"""

import os
import sys
import glob
import urllib2
import subprocess
import common

# canonical path of parent directory, avoiding symlinks
script_path = os.path.dirname(os.path.realpath(__file__))

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
            command = [common.get_default_scp_command()] + uploadables + [self.scp_dest]
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

    def __init__(self, S3_dest_dir="viewer-source-downloads/install_pkgs"):
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
            raise S3ConnectionError("Error: Cannot upload to S3.  Helper script 's3curl.pl' is not Windows-compatible. Try uploading from a unix environment, or see the wiki for uploading to S3 from Windows.")
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
