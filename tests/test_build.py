import logging
import os
import pprint
import tempfile

import autobuild.common as common
import autobuild.configfile as configfile
from autobuild import autobuild_tool_build as build
from autobuild.autobuild_tool_build import AutobuildTool, BuildError
from autobuild.common import cmd
from autobuild.configfile import PACKAGE_METADATA_FILE, MetadataDescription
from tests.baseline_compare import AutobuildBaselineCompare
from tests.basetest import BaseTest, clean_dir, envvar, exc, needs_git
from tests.executables import echo, envtest, noop

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
        self.assertEqual(metadata.package_description.version, "1.0")

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
        with exc(BuildError, "name"):
            build('build', '--config-file=' + self.tmp_file, '--id=123456')

class TestMissingVersion(LocalBase):
    def get_config(self):
        config = super(TestMissingVersion, self).get_config()
        config.package_description.version_file = ""
        return config

    def test_autobuild_build(self):
        with exc(configfile.NoVersionFileKeyError):
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

@needs_git
class TestSCMVersion(LocalBase):
    def get_config(self):
        config = super(TestSCMVersion, self).get_config()
        # Enable SCM version discovery
        config.package_description.use_scm_version = True
        # create empty file to check into git
        with open(os.path.join(self.tmp_build_dir, "empty"), "w"):
            pass
        # create a git root and add a version tag
        cmd("git", "init", cwd=self.tmp_build_dir)
        cmd("git", "remote", "add", "origin", "https://example.com/foo.git", cwd=self.tmp_build_dir)
        cmd("git", "add", "empty", cwd=self.tmp_build_dir)
        cmd("git", "commit", "-m", "initial", cwd=self.tmp_build_dir)
        cmd("git", "tag", "v5.0.0", cwd=self.tmp_build_dir)
        return config

    def test_autobuild_build(self):
        build('build', '--config-file=' + self.tmp_file, '--id=123456')
        self.assertEqual(self.read_metadata().package_description.version, "5.0.0")

@needs_git
class TestVCSInfo(LocalBase):
    def get_config(self):
        config = super(TestVCSInfo, self).get_config()
        # create empty file to check into git
        with open(os.path.join(self.tmp_build_dir, "empty"), "w"):
            pass
        # create a git root and add a version tag
        cmd("git", "init", cwd=self.tmp_build_dir)
        cmd("git", "checkout", "-b", "main", cwd=self.tmp_build_dir)
        cmd("git", "remote", "add", "origin", "https://example.com/foo.git", cwd=self.tmp_build_dir)
        cmd("git", "add", "empty", cwd=self.tmp_build_dir)
        cmd("git", "commit", "-m", "initial", cwd=self.tmp_build_dir)
        return config

    def test_opt_in(self):
        with envvar("AUTOBUILD_VCS_INFO", "true"):
            build('build', '--config-file=' + self.tmp_file, '--id=123456')
            pkg = self.read_metadata()
            self.assertEqual(pkg.package_description.vcs_branch, "main")
            self.assertEqual(pkg.package_description.vcs_url, "https://example.com/foo.git")
            self.assertTrue(len(pkg.package_description.vcs_revision) > 7)

    def test_no_info(self):
        with envvar("AUTOBUILD_VCS_INFO", None):
            build('build', '--config-file=' + self.tmp_file, '--id=123456')
            pkg = self.read_metadata()
            self.assertIsNone(pkg.package_description.vcs_branch)
            self.assertIsNone(pkg.package_description.vcs_url)
            self.assertIsNone(pkg.package_description.vcs_revision)


class TestVersionFileOddWhitespace(LocalBase):
    def get_config(self):
        config = super(TestVersionFileOddWhitespace, self).get_config()
        # overwrite the version_file
        with open(config.package_description.version_file, "w") as vf:
            vf.write("   2.3   ")
        return config

    def test_autobuild_build(self):
        build('build', '--config-file=' + self.tmp_file, '--id=123456')
        self.assertEqual(self.read_metadata().package_description.version, "2.3")

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
