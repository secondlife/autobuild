# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

"""
Create archives of build output, ready for upload to the server.
"""

import sys
import os
import common
from autobuild_base import AutobuildBase
from configfile import ConfigFile, AUTOBUILD_CONFIG_FILE
from connection import SCPConnection, S3Connection, S3ConnectionError, SCPConnectionError

class UploadError(common.AutobuildError):
    pass

class AutobuildTool(AutobuildBase):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description="upload tool for autobuild")

    def register(self, parser):
        """
        Define arguments specific to this subcommand (tool).
        """
        parser.add_argument('archive', nargs=1,
                            help="specify the archive to upload to install-packages.lindenlab.com "
                                 "or to S3, as indicated by config file")
        parser.add_argument('--upload-to-s3',
            action='store_true',
            default=False,
            dest='upload_to_s3',
            help="upload this archive to amazon S3")

    def run(self, args):
        # upload() is written to expect a list of files, and in fact at some
        # point we may decide to accept more than one on the autobuild command
        # line. Here's the odd part. We call it 'archive' so it shows up as
        # singular in help text -- but in fact, because of argparse
        # processing, it arrives as a list.
        upload(args.archive, args.upload_to_s3, args.dry_run)
        if args.dry_run:
            print "This was only a dry-run."


# This function is intended for use by another Python script. It takes a
# specific argument list and indicates error by raising an exception.
def upload(wildfiles, upload_to_s3, dry_run=False):
    """
    wildfiles is an iterable of archive pathnames -- of which we only examine
    the first. (Historical quirk.) Despite the parameter name, we do not
    perform glob matching on that pathname. The basename of the archive
    pathname must be in canonical autobuild archive form:
    package-version-platform-datestamp.extension

    dry_run specifies that no actual uploads are to be performed.

    Returns a sequence of destination "URLs" to which the specified archive
    was uploaded (or would be, in the dry_run=True case). This could be empty
    if the archive in question already exists on all targets. scp URLs have an
    scp: scheme but are otherwise non-canonical.
    """
    if not wildfiles:
        raise UploadError("Error: no tarfiles specified to upload.")
    wildfiles = wildfiles[:1]
    # This logic used to perform glob expansion on all of wildfiles. Now we
    # accept a single tarfile name which must match a real file, rather than
    # being a glob pattern. That's why we only look at wildfiles[:1], and why
    # we capture a 'tarfiles' list.
    tarfiles = [tarfile for tarfile in wildfiles if os.path.exists(tarfile)]
    if not tarfiles:
        raise UploadError("No files found matching %s. Nothing to upload." %
                          " or ".join(repr(w) for w in wildfiles))
    if upload_to_s3:
        s3ables = tarfiles
    else:
        s3ables = []

    # Now upload to our internal install-packages server.
    uploaded = _upload_to_internal(tarfiles, dry_run)

    # Finally, upload to S3 any tarfiles that should be uploaded to S3.
    if not s3ables:
        return uploaded
    
    s3uploaded = _upload_to_s3(s3ables, dry_run)
    uploaded.extend(s3uploaded)
    
    return uploaded


def upload_package(package, toS3=False):
    """
    Upload a package (optionally to S3 when flag is set).
    """
    if not os.path.exists(package):
        raise UploadError("Package %s does not exist." % package)
    files = [package]
    uploaded = _upload_to_internal(files)
    if toS3:
        s3uploaded = _upload_to_s3(files)
        uploaded.extend(s3uploaded)
    return uploaded
    

def _upload_to_internal(tarfiles, dry_run=False):
    SCPConn = SCPConnection()
    uploaded = SCPConn.upload(tarfiles, None, None, dry_run)
    return uploaded


def _upload_to_s3(tarfiles, dry_run=False):
    S3Conn = S3Connection()
    uploaded = []
    for tarfilename in tarfiles:
        if S3Conn.upload(tarfilename, None, dry_run):
            uploaded.append(S3Conn.getUrl(tarfilename))
    return uploaded
    

# provide this line to make the tool work standalone too (which all tools should)
if __name__ == "__main__":
    sys.exit( AutobuildTool().main( sys.argv[1:] ) )
