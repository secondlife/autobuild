import os

import autobuild.common as common
import autobuild.configfile as configfile
from autobuild import autobuild_tool_configure as configure
from tests.baseline_compare import AutobuildBaselineCompare
from tests.basetest import BaseTest
from tests.executables import echo, noop


class TestConfigure(BaseTest, AutobuildBaselineCompare):
    def setUp(self):
        BaseTest.setUp(self)
        os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.abspath(os.path.dirname(__file__))])
        self.tmp_file = self.get_tmp_file()
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        package = configfile.PackageDescription('test')
        package.license="LGPL"
        package.copyright="copy left"
        package.license_file="LICENSES/file"
        platform = configfile.PlatformDescription()
        build_configuration = configfile.BuildConfigurationDescription()
        build_configuration.configure = noop
        build_configuration.default = True
        build_configuration.name = 'Release'
        platform.configurations['Release'] = build_configuration
        package.platforms[common.get_current_platform()] = platform
        self.config.package_description = package
        self.config.save()

    def test_configure(self):
        # tests underlying API
        build_configuration = self.config.get_build_configuration('Release')
        result = configure._configure_a_configuration(self.config, build_configuration, [])
        assert result == 0

    def test_autobuild_configure(self):
        self.autobuild('configure', '--config-file=' + self.tmp_file, '--id=123456')
        self.autobuild('configure', '--config-file=' + self.tmp_file, '--id=123456', '--', '--foo', '-b')

    def test_substitutions(self):
        self.config.package_description.platforms[common.get_current_platform()] \
            .configurations['Release'].configure = echo("foo$AUTOBUILD_ADDRSIZE")
        self.config.save()
        assert "foo32" in self.autobuild('configure', '--config-file=' + self.tmp_file,
                                        '-A', '32')
        assert "foo64" in self.autobuild('configure', '--config-file=' + self.tmp_file,
                                        '-A', '64')
    def test_id(self):
        self.config.package_description.platforms[common.get_current_platform()] \
            .configurations['Release'].configure = echo("foo$AUTOBUILD_BUILD_ID")
        self.config.save()
        assert "foo666" in self.autobuild('configure', '--config-file=' + self.tmp_file,
                                        '-i', '666')

    def tearDown(self):
        self.cleanup_tmp_file()
        BaseTest.tearDown(self)
