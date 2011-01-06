#!/usr/bin/python
"""\
@file   connection.py
@author Nat Goodspeed
@date   2010-04-20
@brief  Classes shared between package.py and upload.py

$LicenseInfo:firstyear=2010&license=mit$
Copyright (c) 2010, Linden Research, Inc.

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

import glob
import os
import re
import logging
import subprocess
import sys
import urllib2

import common
import boto.s3.connection

logger = logging.getLogger('autobuild.connection')

AutobuildError = common.AutobuildError

class ConnectionError(AutobuildError):
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
        uploaded = []
        for file in files:
            if self.SCPFileExists(file, server, dest_dir):
                print ("Info: A file with name '%s' in dir '%s' already exists on %s. Not uploading." % (self.basename, self.dest_dir, self.server))
            else:
                uploadables.append(file)
                uploaded.append(self.SCPurl)
        if uploadables:
            print "Uploading to: %s" % self.scp_dest
            command = [common.get_default_scp_command()] + uploadables + [self.scp_dest]
            if dry_run:
                logger.warning(" ".join(command))
            else:
                rc = subprocess.call(command) # interactive -- possible password req'd
                if rc != 0:
                    raise SCPConnectionError("Failed to upload (rc %s): %s" % (rc, uploadables))
        return uploaded

    def SCPFileExists(self, filename, server=None, dest_dir=None):
        """Set member vars and check if file already exists on dest server.
        @param filename Full path to file to be uploaded.
        @param server If provided, specifies server to upload to.
        @param dest_dir If provided, specifies destination directory on server.
        @return Returns boolean indicating whether file exists on server.
        """
        self.setDestination(server, dest_dir)
        self.loadFile(filename)
        try:
            return self.fileExists(self.url)
        except urllib2.HTTPError, err:
            print >>sys.stderr, "\nChecking %s: %s: %s" % (self.url, err.__class__.__name__, err)
            raise

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


class S3Connection(Connection):
    """Twiddly bits of talking to S3.  Hi S3!
    """
    # keep S3 url http instead of https
    amazonS3_server = "http://s3.amazonaws.com/"

    def __init__(self, S3_dest_dir="viewer-source-downloads/install_pkgs"):
        """Set server dir for all transactions.
        Alternately, use member methods directly, supplying S3_dest_dir.
        """

        S3_creds = _load_s3curl_credentials()

        # here by design -- server dir should be specified explicitly
        self.connection = boto.s3.connection.S3Connection(S3_creds['id'], S3_creds['key'])
        # in case S3_dest_dir is explicitly passed as None
        self.bucket = None
        self.partial_key = ""
        # initialize self.bucket, self.partial_key
        self.setS3DestDir(S3_dest_dir)

    def _get_key(self, pathname):
        """
        @param pathname Local filesystem pathname for which to get the
        corresponding S3 key object. Relies on the current self.bucket and
        self.partial_key (from S3_dest_dir). Extracts just the basename from
        pathname and glues it onto self.partial_key.
        """
        if self.bucket is None:
            # This object was initialized with S3_dest_dir=None, and we've
            # received no subsequent setS3DestDir() call with a non-None value.
            raise S3ConnectionError("Error: S3 destination directory must be set.")
        # I find new_key() a somewhat misleading method name: it doesn't have
        # any effect on S3; it merely instantiates a new Key object tied to
        # the bucket on which you make the call.
        return self.bucket.new_key('/'.join((self.partial_key, os.path.basename(pathname))))

    def upload(self, filename, S3_dest_dir=None, dry_run=False, S3_acl='public-read'):
        """Upload file specified by filename to S3.
        If file already exists at specified destination, raises exception.
        NOTE:  Knowest whither thou uploadest! Ill fortune will befall
        those who upload blindly.
        """
        if S3_dest_dir is not None:
            self.setS3DestDir(S3_dest_dir)
        # Get the S3 key object on which we can perform operations.
        key = self._get_key(filename)
        if key.exists():
            print ("A file with name '%s/%s' already exists on S3. Not uploading."
                   % (self.bucket.name, key.name))
            return False

        print "Uploading to: %s" % self.getUrl(filename)
        if not dry_run:
            key.set_contents_from_filename(filename)
            key.set_acl(S3_acl)
        # The True return is intended to indicate whether we were GOING to
        # upload the file: that is, whether it already existed. It's not
        # affected by dry_run because the caller knows perfectly well whether
        # s/he passed dry_run.
        return True

    def S3FileExists(self, filename):
        """Check if file exists on S3.
        @param filename Filename (incl. path) of file to be uploaded.
        @return Returns boolean indicating whether file already exists on S3.
        """
        return self._get_key(filename).exists()

    def setS3DestDir(self, S3_dest_dir):
        """Set class vars for the destination dir on S3."""
        if S3_dest_dir is None:  # allow: == ""
            return
        # We don't actually store S3_dest_dir itself any more. The important
        # side effect of setting S3_dest_dir is to set self.bucket and
        # self.partial_key.
        # To get the bucket name, split off only before the FIRST slash.
        bucketname, self.partial_key = S3_dest_dir.split('/', 1)
        self.bucket = self.connection.get_bucket(bucketname)

    def getUrl(self, filename):
        """Return the url the pkg would be at if on the server."""
        key = self._get_key(filename)
        return "%s%s/%s" % (self.amazonS3_server, self.bucket.name, self._get_key(filename).name)

def _load_s3curl_credentials(account_name = 'lindenlab', credentials_file=None):
    """
    Helper function for loading 'lindenlab' s3 credentials from s3curl.pl's ~/.s3curl config file
    see the README file in the s3curl distribution (http://developer.amazonwebservices.com/connect/entry.jspa?externalID=128)
    """
    credentials_path = os.path.expanduser("~/.s3curl")

    # *HACK - half-assed regex for parsing the perl hash that s3curl.pl stores its credentials i.n
    # s3curl.pl parses the file by calling eval(), as if perl wasn't dirty enough as it is...
    # example:
    # %awsSecretAccessKeys = (
    #   lindenlab => {
    #       id => 'ABCDABCDABCDABCD',
    #       key => '01234567890abcdABCD/01234567890abcdABCD+',
    #   },
    #} 
    credentials_pattern = '%s\s*=>\s*{\s*id\s*=>\s*\'([^\']*)\'\s*,\s*key\s*=>\s*\'([^\']*)\',\s*}' % account_name

    try:
        if not credentials_file:
            credentials_file = open(credentials_path)
        s3curl_text = credentials_file.read()

        m = re.search(credentials_pattern, s3curl_text, re.MULTILINE)
        creds = dict(id=m.group(1), key=m.group(2))
        return creds
    except IOError, err:
        # IOError happens when ~/.s3curl is missing
        raise S3ConnectionError("failed to find s3 credentials in '%s' -- see the README file in the s3curl distribution (http://developer.amazonwebservices.com/connect/entry.jspa?externalID=128)'" % credentials_path)
    except AttributeError, err:
        # AttributeError happens when regex doesn't find a match
        raise S3ConnectionError("failed to parse s3 credentials from '%s' -- see the README file in the s3curl distribution (http://developer.amazonwebservices.com/connect/entry.jspa?externalID=128)'" % credentials_path)
