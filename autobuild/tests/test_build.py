# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# $/LicenseInfo$


import os
import sys
import logging
import pprint
import tempfile
import unittest
from nose.tools import *                # assert_equals
from .baseline_compare import AutobuildBaselineCompare
from autobuild import autobuild_tool_build as build
import autobuild.configfile as configfile
import autobuild.common as common
from autobuild.configfile import PACKAGE_METADATA_FILE, MetadataDescription
from autobuild.autobuild_tool_build import BuildError, AutobuildTool
from .basetest import BaseTest, clean_dir, exc
from .executables import envtest, noop, echo

# ****************************************************************************
#   TODO
# - Test for specific --build-dir (new select_directories() mechanism)
# - Test building to configuration-specific build directory
# - Test building to build trees for --all configurations
# - Test building to build directory(ies) for specified --configuration(s)
# ****************************************************************************
logger = logging.getLogger("autobuild.test_build")

def build(*args):
    """
    Some of our tests use BaseTest.autobuild() to run the build command as a
    child process. Some call the build command in-process. This is the latter.
    """
    AutobuildTool().main(list(args))

class LocalBase(BaseTest, AutobuildBaselineCompare):
    def setUp(self):
        BaseTest.setUp(self)
        # We intend to ask our child autobuild command to run a script located
        # in this directory. Make sure this directory is on child autobuild's
        # PATH so we find it.
        os.environ["PATH"] = os.pathsep.join([os.path.abspath(os.path.dirname(__file__)),
                                              os.environ["PATH"]])
        # Create and return a config file appropriate for this test class.
        self.tmp_file = self.get_tmp_file()
        self.tmp_build_dir=tempfile.mkdtemp(prefix=os.path.dirname(self.tmp_file)+"/build-")
        self.config = self.get_config()
        self.config.save()

    def get_config(self):
        config = configfile.ConfigurationDescription(self.tmp_file)
        package = configfile.PackageDescription('test')
        package.license = "LGPL"
        package.license_file="LICENSES/file"
        package.copyright="copy right"
        platform = configfile.PlatformDescription()
        platform.build_directory = self.tmp_build_dir
        package.version_file = os.path.join(self.tmp_build_dir, "version.txt")
        with open(package.version_file, "w") as vf:
            vf.write("1.0\n")
        build_configuration = configfile.BuildConfigurationDescription()
        # Formally you might consider that noop.py is an "argument" rather
        # than an "option" -- but the way Executable is structured, if we pass
        # it as an "argument" then the "build" subcommand gets inserted before
        # it, which thoroughly confuses the Python interpreter.
        build_configuration.build = noop
        build_configuration.default = True
        build_configuration.name = 'Release'
        platform.configurations['Release'] = build_configuration
        package.platforms[common.get_current_platform()] = platform
        config.package_description = package
        return config

    def tearDown(self):
        self.cleanup_tmp_file()
        if self.tmp_build_dir:
            clean_dir(self.tmp_build_dir)
        BaseTest.tearDown(self)

    def read_metadata(self, platform=None):
        # Metadata file is relative to the build directory. Find the build
        # directory by drilling down to correct platform.
        platforms = self.config.package_description.platforms
        if platform:
            platdata = platforms[platform]
        else:
            assert len(platforms) == 1, \
                   "read_metadata(no platform) ambiguous: " \
                   "pass one of %s" % ', '.join(list(platforms.keys()))
            _, platdata = platforms.popitem()
        return MetadataDescription(os.path.join(platdata.build_directory,
                                                PACKAGE_METADATA_FILE))

class TestBuild(LocalBase):
    def get_config(self):
        config = super(TestBuild, self).get_config()
        #config.package_description.version = "0"
        logger.debug("config: %s" % pprint.pformat(config))
        return config

    def test_autobuild_build_default(self):
        self.autobuild('build', '--no-configure', '--config-file=' + self.tmp_file, '--id=123456')
        self.autobuild('build', '--config-file=' + self.tmp_file, '--id=123456', '--', '--foo', '-b')
        metadata = self.read_metadata()
        assert not metadata.package_description.version_file, \
               "version_file erroneously propagated into metadata"
        assert_equals(metadata.package_description.version, "1.0")

    def test_autobuild_build_all(self):
        self.autobuild('build', '--config-file=' + self.tmp_file, '--id=123456', '-a')

    def test_autobuild_build_release(self):
        self.autobuild('build', '--config-file=' + self.tmp_file, '-c', 'Release', '--id=123456')

class TestEnvironment(LocalBase):
    def get_config(self):
        config = super(TestEnvironment, self).get_config()
        config.package_description.copyright="no copy"
        # Formally you might consider that noop.py is an "argument" rather
        # than an "option" -- but the way Executable is structured, if we pass
        # it as an "argument" then the "build" subcommand gets inserted before
        # it, which thoroughly confuses the Python interpreter.
        config.package_description.platforms[common.get_current_platform()] \
              .configurations["Release"].build = envtest
        return config

    def test_env(self):
        # verify that the AUTOBUILD env var is set to point to something executable
        self.autobuild('build', '--no-configure', '--config-file=' + self.tmp_file, '--id=123456')

class TestMissingPackageNameCurrent(LocalBase):
    def get_config(self):
        config = super(TestMissingPackageNameCurrent, self).get_config()
        config.package_description.name = ""
        return config

    def test_autobuild_build(self):
        # Make sure the verbose 'new requirement' message is only produced
        # when the missing key is in fact version_file.
        with exc(BuildError, "name", without="(?i)new requirement"):
            build('build', '--config-file=' + self.tmp_file, '--id=123456')

class TestMissingPackageNameOld(LocalBase):
    def get_config(self):
        config = super(TestMissingPackageNameOld, self).get_config()
        config.package_description.name = ""
        config.version = "1.2"
        return config

    def test_autobuild_build(self):
        # Make sure the verbose 'new requirement' message is only produced
        # when the missing key is in fact version_file, especially with an
        # older version config file.
        with exc(BuildError, "name", without="(?i)new requirement"):
            build('build', '--config-file=' + self.tmp_file, '--id=123456')

class TestMissingVersionFileCurrent(LocalBase):
    def get_config(self):
        config = super(TestMissingVersionFileCurrent, self).get_config()
        config.package_description.version_file = ""
        return config

    def test_autobuild_build(self):
        # Make sure the verbose 'new requirement' message isn't produced with
        # a current format config file.
        with exc(BuildError, "version_file", without="(?i)new requirement"):
            build('build', '--config-file=' + self.tmp_file, '--id=123456')

class TestMissingVersionFileOld(LocalBase):
    def get_config(self):
        config = super(TestMissingVersionFileOld, self).get_config()
        config.package_description.version_file = ""
        config.version = "1.2"
        return config

    def test_autobuild_build(self):
        # Make sure the verbose 'new requirement' message is produced when the
        # missing key is version_file with an older version config file. The
        # (?s) flag allows '.' to match newline, important because 'new
        # requirement' may be on a different line of the exception message
        # than the attribute name version_file.
        with exc(BuildError, "(?is)version_file.*new requirement"):
            build('build', '--config-file=' + self.tmp_file, '--id=123456')

class TestAbsentVersionFile(LocalBase):
    def get_config(self):
        config = super(TestAbsentVersionFile, self).get_config()
        # nonexistent file
        config.package_description.version_file = "venison.txt"
        return config

    def test_autobuild_build(self):
        with exc(common.AutobuildError, "version_file"):
            build('build', '--config-file=' + self.tmp_file, '--id=123456')

class TestEmptyVersionFile(LocalBase):
    def get_config(self):
        config = super(TestEmptyVersionFile, self).get_config()
        # stomp the version_file with empty content
        with open(config.package_description.version_file, "w"):
            pass
        return config

    def test_autobuild_build(self):
        with exc(common.AutobuildError, "version_file"):
            build('build', '--config-file=' + self.tmp_file, '--id=123456')

class TestVersionFileOddWhitespace(LocalBase):
    def get_config(self):
        config = super(TestVersionFileOddWhitespace, self).get_config()
        # overwrite the version_file
        with open(config.package_description.version_file, "w") as vf:
            vf.write("   2.3   ")
        return config

    def test_autobuild_build(self):
        build('build', '--config-file=' + self.tmp_file, '--id=123456')
        assert_equals(self.read_metadata().package_description.version, "2.3")

class TestSubstitutions(LocalBase):
    def get_config(self):
        config = super(TestSubstitutions, self).get_config()
        config.package_description.platforms[common.get_current_platform()] \
              .configurations['Release'].build = echo("foo$AUTOBUILD_ADDRSIZE")
        return config

    def test_substitutions(self):
        assert "foo32" in self.autobuild('build', '--config-file=' + self.tmp_file,
                                        '-A', '32')
        assert "foo64" in self.autobuild('build', '--config-file=' + self.tmp_file,
                                        '-A', '64')

    def test_id(self):
        self.config.package_description.platforms[common.get_current_platform()] \
            .configurations['Release'].build = echo("foo$AUTOBUILD_BUILD_ID")
        self.config.save()
        assert "foo666" in self.autobuild('build', '--config-file=' + self.tmp_file,
                                        '-i', '666')
        
if __name__ == '__main__':
    unittest.main()
