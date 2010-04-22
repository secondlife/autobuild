# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$

"""
Create archives of build output, ready for upload to the server.
"""

import sys
import os
import common
from configfile import ConfigFile
from connection import SCPConnection, S3Connection, S3ConnectionError, SCPConnectionError

AutobuildError = common.AutobuildError

# better way to do this?
S3Conn = S3Connection()
SCPConn = SCPConnection()

class UploadError(AutobuildError):
    pass

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
# specific argument list and indicates error by raising an exception.
def upload(wildfiles, dry_run=False):
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
    config.load()
    s3ables = [tarfile for tarfile in tarfiles if checkTarfileForUpload(config, tarfile)]

    # Now upload to our internal install-packages server.
    SCPConn.upload(tarfiles, None, None, dry_run)

    # Finally, upload to S3 any tarfiles that should be uploaded to S3.
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
            raise SCPConnectionError("Error: File must exist on internal server before uploading to S3")
        S3Conn.upload(tarfilename, None, dry_run)

# This function is reached from autobuild_main, which always passes generic
# optparse-style (options, args).
def main(options, args):
    upload(args, options.dry_run)
    if options.dry_run:
        print "This was only a dry-run."

if __name__ == '__main__':
    sys.exit("Please invoke this script using 'autobuild upload'")
