# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

"""
Create archives of build output, ready for upload to the server.
"""

import sys
import os
import common
from autobuild_base import autobuild_base
from configfile import ConfigFile, BUILD_CONFIG_FILE
from connection import SCPConnection, S3Connection, S3ConnectionError, SCPConnectionError

class UploadError(common.AutobuildError):
    pass

class autobuild_tool(autobuild_base):
    def get_details(self):
        return dict(name=self.name_from_file(__file__),
                    description="upload tool for autobuild")

    def register(self, parser):
        """
        Define arguments specific to this subcommand (tool).
        """
        parser.add_argument('archive', nargs=1,
                            help="Specify the archive to upload to install-packages.lindenlab.com "
                                 "or to S3, as indicated by config file")
        parser.add_argument('--config-file', default=BUILD_CONFIG_FILE,
                            dest='config_file',
                            help='The file used to describe how to build the package.')

    def run(self, args):
        # upload() is written to expect a list of files, and in fact at some
        # point we may decide to accept more than one on the autobuild command
        # line. Here's the odd part. We call it 'archive' so it shows up as
        # singular in help text -- but in fact, because of argparse
        # processing, it arrives as a list.
        upload(args.archive, args.config_file, args.dry_run)
        if args.dry_run:
            print "This was only a dry-run."

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

def checkTarfileForUpload(config, tarfilename):
    """Get status on S3ability of a tarfile.  Returns boolean."""
    pkgname, platform = dissectTarfileName(tarfilename)

    info = config.package(pkgname)      # from tarfile name
    if info is None:
        # We don't know how to proceed. A safe guess would be to skip
        # uploading to S3 -- but that presents the likelihood of nasty
        # surprises later (e.g. broken open-source build). Inform the user.
        raise UploadError("Unknown package %s (tarfile %s) -- can't decide whether to upload to S3"
                          % (pkgname, tarfilename))
    # Here info is definitely not None.
    if info.uploadtos3 is None:
        raise UploadError("Package %s (tarfile %s) does not specify whether to upload to S3" %
                          (pkgname, tarfilename))
    return info.uploadtos3


# This function is intended for use by another Python script. It takes a
# specific argument list and indicates error by raising an exception.
def upload(wildfiles, config_file, dry_run=False):
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

    # Check whether the config file specifies S3 upload; if it doesn't say,
    # that's an error. Do this before SCP upload so that such an error doesn't
    # leave us in the awkward position of having to rename the tarfile to
    # retry the upload to SCP and S3. Collect any tarfiles that should be
    # uploaded to S3 in a separate list.
    config = ConfigFile()
    config.load(config_file)
    s3ables = [tarfile for tarfile in tarfiles if checkTarfileForUpload(config, tarfile)]

    # Now upload to our internal install-packages server.
    SCPConn = SCPConnection()
    SCPConn.upload(tarfiles, None, None, dry_run)

    # Finally, upload to S3 any tarfiles that should be uploaded to S3.
    if not s3ables:
        # If there aren't any, don't even bother instantiating the connection.
        return
    
    S3Conn = S3Connection()
    for tarfilename in s3ables:
        # Normally, check that we've successfully uploaded the tarfile to our
        # scp repository before uploading to S3. (But why? We've just put it
        # there in the preceding lines? If we're concerned about upload
        # failure, shouldn't we notice that as part of SCPConn.upload()
        # instead of waiting until now? And the message below seems to suggest
        # more of a user operation sequence error -- which I think is now
        # logically impossible -- than a network failure.) In any case: if
        # dry_run is set, we won't have uploaded to our scp repository, so
        # don't even perform this test as it would definitely fail.
        if not (dry_run or SCPConn.SCPFileExists(tarfilename)):
            raise UploadError("Error: File must exist on internal server before uploading to S3")
        S3Conn.upload(tarfilename, None, dry_run)

# provide this line to make the tool work standalone too (which all tools should)
if __name__ == "__main__":
    sys.exit( autobuild_tool().main( sys.argv[1:] ) )
