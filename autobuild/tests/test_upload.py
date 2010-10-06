#!/usr/bin/python
"""\
@file   test_upload.py
@author Nat Goodspeed
@date   2010-04-23
@brief  Test autobuild/autobuild_tool_upload.py.

$LicenseInfo:firstyear=2010&license=internal$
Copyright (c) 2010, Linden Research, Inc.
$/LicenseInfo$
"""

import os
import sys
import time
import errno
import shutil
import tarfile
import urllib2
import tempfile
import subprocess
from cStringIO import StringIO
from nose.tools import *                # assert_etc()
from autobuild import common
from autobuild.autobuild_tool_upload import upload, UploadError, \
     SCPConnection, S3Connection, S3ConnectionError, SCPConnectionError

from autobuild.configfile import ConfigFile, PackageInfo

scp = common.get_default_scp_command()
ssh = common.find_executable(['ssh', 'plink'], ['.exe'])
USER = os.environ.get("USER", common.get_current_user())

def assert_in(sought, data):
    assert sought in data, "%r not in %r" % (sought, data)

def assert_not_in(sought, data):
    assert sought not in data, "%r in %r" % (sought, data)

def assert_startswith(data, pfx):
    assert data.startswith(pfx), "%r doesn't startwith(%r)" % (data, pfx)

def setup():
    """
    This setup() function is run once for this whole module, as opposed to
    TestWithConfigFile.setup(), which is run once per test method.
    """
    if not ssh:
        raise common.AutobuildError("Cannot find ssh command to clean up scp server")
    # TestWithConfigFile.teardown() has the benefit of working with a list of
    # specific server:pathname items, so it can be very specific about
    # cleaning them up. We have to guess based on SCPConnection's default
    # server and directory.
    scpconn = SCPConnection()
    # We now require that every "archive" file uploaded by this test script
    # have its platform set to "$USER.bogus". That is, they should all match
    # the following glob pattern:
    bogus = "*-*-%s.bogus-*.txt" % USER
    command = [ssh, scpconn.server, "rm", '-vf', '/'.join((scpconn.dest_dir, bogus))]
    print ' '.join(command)
    subprocess.call(command)
    # We don't check the rc because we fully expect that most of the time, rm
    # will complain about not being able to find a file called
    # "*-*-$USER.bogus-*.txt". rc will only be 0 when there are garbage files
    # to clean up. The only error case that should raise an alarm is when
    # there ARE such files, but we can't remove them -- but I don't think
    # that's distinguishable by rc value.

class TestLocally(object):
    @raises(UploadError)
    def testNoFiles(self):
        upload([], "autobuild.xml", dry_run=True)

    @raises(UploadError)
    def testBadFile(self):
        upload(["bogus>filename"], "autobuild.xml", dry_run=True)

class TestWithConfigFile(object):
    def setup(self):
        # Create a temp directory for fixture data.
        self.tempdir = tempfile.mkdtemp()
        self.origdir = os.path.join(self.tempdir, "orig")
        os.mkdir(self.origdir)
        self.downloads = os.path.join(self.tempdir, "downloads")
        os.mkdir(self.downloads)
        self.config_file_upshrug = os.path.join(self.tempdir, "autobuild_upshrug.xml")
        self.config_file_upno = os.path.join(self.tempdir, "autobuild_upno.xml")
        self.config_file_upyes = os.path.join(self.tempdir, "autobuild_upyes.xml")
        self.scpconn = SCPConnection()
        self.s3conn = S3Connection()
        self.cleanups = set()
        self.scpcleanups = set()
        self.S3cleanups = set()

        # Upload to S3 value unset.
        c_upshrug = ConfigFile('upshrug')
        c_upshrug.save(self.config_file_upshrug)
        
        # Do not upload to S3
        c_upno = ConfigFile('upno')
        c_upno.package_definition.uploadtos3 = False
        c_upno.save(self.config_file_upno)
        
        # Upload to S3
        c_upyes = ConfigFile('upyes')
        c_upyes.package_definition.uploadtos3 = True
        c_upyes.save(self.config_file_upyes)

        # Now make bogus archive files for all those
        self.unknown_archive = self.make_archive("unknown")
        self.upshrug_archive = self.make_archive("upshrug")
        self.upno_archive = self.make_archive("upno")
        self.upyes_archive = self.make_archive("upyes")

    def make_archive(self, name, version="1.0"):
        # N.B. We used to accept an optional platform= argument, but nowadays
        # we force the platform to '$USER.bogus' so test setup can clean out any
        # such files left in place from previous failed test runs.
        platform = "%s.bogus" % USER
        pathname = os.path.join(self.origdir,
                                "%s-%s-%s-%s.txt" %
                                (name, version, platform, time.strftime("%Y%m%d")))
        f = open(pathname, "w")
        # The upload subcommand doesn't care what's in a specified archive. So
        # just write some text.
        f.write("%s version %s for %s\n" % (name, version, platform))
        f.close()
        return pathname

    def make_PackageInfo(self, name, version="1.0", platform="%s.bogus" % USER):
        p = PackageInfo()
        # Swipe dummy package info from test_configfile.py
        # Intentionally omit the uploadtos3 property: some of our tests want
        # that unset. Caller must set it if desired.
        p.summary = "%s package" % name
        p.description = "%s package created by %s" % (name, os.path.basename(__file__))
        p.copyright = time.strftime("Copyright (c) %Y, Linden Research, Inc.")
        p.license = "GPL2"
        p.licensefile = "http://develop.secondlife.com/develop-on-sl-platform/viewer-licensing/gpl/"
        p.homepage = "http://www.secondlife.com/"
        p.source = "http://www.secondlife.com/%s-source" % name
        p.sourcetype = "archive"
        p.sourcedir = "%s-source" % name
        p.version = version
        p.patches = "foo bar"
        p.obsoletes = "baz bar foo"

        p.set_archives_url(platform, 'http://www.secondlife.com')
        p.set_archives_md5(platform, '22eac1bea219257a71907cbe1170c640')

        p.set_dependencies_url(platform, 'http://www.secondlife.com')
        p.set_dependencies_md5(platform, '22eac1bea219257a71907cbe1170c640')

        p.set_configure_command('common', 'configure --enabled-shared')
        p.set_build_command('common', 'build.sh')
        p.set_build_directory('common', "%s-build" % name)
        p.set_post_build_command('common', 'postbuild.sh')

        p.set_manifest_files('common', ['file1','file2'])
        p.set_manifest_files('windows', ['file3'])
        return p

    def teardown(self):
        # Get rid of the temp download directory.
        shutil.rmtree(self.tempdir)
        reraise = None
        for f in self.cleanups:
            try:
                os.remove(f)
            except OSError, err:
                # Nonexistence is an acceptable reason for remove() failure.
                if err.errno != errno.ENOENT:
                    print >>sys.stderr, "\nCan't delete %r: %s" % (f, err)
                    # Because we want to clean up all the rest of the files,
                    # don't just propagate the exception: finish the loop
                    # first, and then (courtesy of the reraise flag) raise.
                    reraise = sys.exc_info()
        if self.scpcleanups:
            # Collect scp items into a dict whose key is the server name and
            # whose value is a list of pathnames; that lets us clean up all
            # test files uploaded to the same server with a single remote
            # command.
            paths = {}
            for item in self.scpcleanups:
                # Each 'item' should be of the form server:pathname.
                # Decompose to capture in the dict.
                server, path = item.split(':', 1)
                paths.setdefault(server, []).append(path)
            # Now, for each server in the dict, use 'ssh rm' to remove all the
            # pathnames we uploaded to that server.
            for server, pathnames in paths.iteritems():
                command = [ssh, server, 'rm'] + pathnames
                print ' '.join(command)
                rc = subprocess.call(command)
                if rc != 0:
                    print >>sys.stderr, "\n*** scp cleanup failed (%s): %s" % (rc, ' '.join(command))
                for path in pathnames:
                    dirname, basename = os.path.split(path)
                    self.scpconn.setDestination(server, dirname)
                    if self.scpconn.SCPFileExists(basename):
                        print >>sys.stderr, "\n*** failed to clean up:", ':'.join(server, path)
        if self.S3cleanups:
            for item in self.S3cleanups:
                # Each 'item' should be an S3 URL. Decompose.
                if not item.startswith(self.s3conn.amazonS3_server):
                    print >>sys.stderr, "\n*** Unexpected S3 URL, can't clean up:", item
                    continue
                # Okay, this item does start as we expect, lop off prefix.
                pathname = item[len(self.s3conn.amazonS3_server):]
                # Break off just the filename part from the path part.
                dirname, filename = os.path.split(pathname)
                self.s3conn.setS3DestDir(dirname)
                # Sanity-check that the file actually exists on the server.
                if not self.s3conn.S3FileExists(filename):
                    print >>sys.stderr, "\n*** S3 URL not found:", item
                    continue
                # Now get an S3 "key" object describing the file in question.
                # This is internal, not an operation we expose to clients of
                # S3Connection. Using this key, we can remove the server file.
                self.s3conn._get_key(filename).delete()
                # Sanity-check that the file no longer exists on the server.
                if self.s3conn.S3FileExists(filename):
                    print >>sys.stderr, "\n*** Hand-delete from S3:", item
                
        if reraise is not None:
            raise reraise[0], reraise[1], reraise[2]

    @raises(UploadError)
    def testUnknown(self):
        upload([self.unknown_archive], self.config_file_upshrug, dry_run=True)

    @raises(UploadError)
    def testShrug(self):
        upload([self.upshrug_archive], self.config_file_upshrug, dry_run=True)

    def testNoDry(self):
        # Capture print output
        oldout, sys.stdout = sys.stdout, StringIO()
        try:
            uploaded = upload([self.upno_archive], self.config_file_upno, dry_run=True)
        finally:
            testout, sys.stdout = sys.stdout, oldout
        # We shouldn't have talked about S3
        assert_not_in("amazonaws", testout.getvalue())
        # We should have claimed to upload to exactly one dest, with an scp: URL
        assert_equals(len(uploaded), 1)
        assert_startswith(uploaded[0], "scp:")
        # But in fact we should NOT have actually uploaded the file there.
        assert not self.scpconn.SCPFileExists(self.upno_archive)

    def testYesDry(self):
        # Capture print output
        oldout, sys.stdout = sys.stdout, StringIO()
        try:
            uploaded = upload([self.upyes_archive], self.config_file_upyes, dry_run=True)
        finally:
            testout, sys.stdout = sys.stdout, oldout
        # We should have talked about S3
        assert_in("amazonaws", testout.getvalue())
        # We should have claimed to upload to both dests
        assert_equals(len(uploaded), 2)
        # We're sure one of these should start with "http:" while the other
        # should start with "scp:", but we don't want to have to know which is
        # which. sort() to order them.
        uploaded.sort()
        assert_startswith(uploaded[0], "http:")
        assert_startswith(uploaded[1], "scp:")
        # But in fact we should NOT have actually uploaded to either.
        assert not self.scpconn.SCPFileExists(self.upyes_archive)
        assert not self.s3conn.S3FileExists(self.upyes_archive)

    def testNo(self):
        # Establish that this upload() call actually changes the return from
        # SCPFileExists().
        assert not self.scpconn.SCPFileExists(self.upno_archive)
        # Let dry_run default to False
        uploaded = upload([self.upno_archive], self.config_file_upno)
        # Should claim to have uploaded exactly one file
        assert_equals(len(uploaded), 1)
        self.scp_verify(self.upno_archive, uploaded[0])
        # Now detect a duplicate upload attempt. Because we take pains to try
        # to give each new archive a unique name, we don't consider that an
        # already existing file is an error; we assume we're retrying an
        # upload already performed earlier. upload() indicates that it didn't
        # perform any actual uploading in a couple ways, though.
        # capture print output
        oldout, sys.stdout = sys.stdout, StringIO()
        try:
            # Try to upload the same file
            uploaded = upload([self.upno_archive], self.config_file_upno)
        finally:
            testout, sys.stdout = sys.stdout, oldout
        assert not uploaded, "dup scp-only upload returned %s" % uploaded
        testmsg = testout.getvalue().lower()
        assert_in("already exists", testmsg)
        assert_in("not uploading", testmsg)

    def testYes(self):
        # Want to change the state of both servers.
        assert not self.scpconn.SCPFileExists(self.upyes_archive)
        assert not self.s3conn.S3FileExists(self.upyes_archive)
        # Let dry_run default to False
        uploaded = upload([self.upyes_archive], self.config_file_upyes)
        # One file, two servers, should get two URLs back
        assert_equals(len(uploaded), 2)
        # Sort URLs so we're sure they're ["http:...", "scp:..."]
        uploaded.sort()
        self.scp_verify(self.upyes_archive, uploaded[1])
        self.s3_verify(self.upyes_archive, uploaded[0])
        # Try to upload same file again, should result in info messges with no
        # new URLs.
        oldout, sys.stdout = sys.stdout, StringIO()
        try:
            uploaded = upload([self.upyes_archive], self.config_file_upyes)
        finally:
            testout, sys.stdout = sys.stdout, oldout
        assert not uploaded, "dup scp+s3 upload returned %s" % uploaded
        testmsg = testout.getvalue().lower()
        assert_in("already exists on s3", testmsg)

    def scp_verify(self, archive, uploaded):
        # Decompose the URL so we can fetch it back.
        pfx = "scp:"
        assert_startswith(uploaded, pfx)
        url = uploaded[len(pfx):]
        # Clean it up during teardown().
        self.scpcleanups.add(url)
        # The file should now be present on our scp server.
        assert self.scpconn.SCPFileExists(archive)
        # Fetch the temp file by running:
        # scp server:pathname tempdir/downloads/
        command = [scp, url, self.downloads + '/']
        print ' '.join(command)
        # That better run successfully
        assert_equals(0, subprocess.call(command))
        # Now verify that the file we downloaded has the same contents as
        # the file we uploaded.
        assert_equals(open(os.path.join(self.downloads, os.path.basename(archive)), "rb").read(),
                      open(archive, "rb").read())

    def s3_verify(self, archive, uploaded):
        # Clean it up during teardown().
        self.S3cleanups.add(uploaded)
        # The file should now be present on S3.
        assert self.s3conn.S3FileExists(archive)
        # Read the uploaded archive and compare to the original.
        assert_equals(urllib2.urlopen(uploaded).read(), open(archive, "rb").read())

def collect_uploads(uploaded):
    """
    upload() returns a collection of URLs, of which some start with "scp:" and
    some with "http:". Organize those as a dict like this:
    dict(scp=["scp:this", "scp:that"],
         http=["http:this", "http:that"])
    """
    result = {}
    for url in uploaded:
        result.setdefault(url.split(':', 1)[0], []).append(url)
    return result
