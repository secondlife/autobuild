import logging
import os

import autobuild.autobuild_tool_manifest as manifest
from autobuild import common, configfile
from tests.baseline_compare import AutobuildBaselineCompare
from tests.basetest import BaseTest

logger = logging.getLogger("test_manifest")

class TestManifest(BaseTest, AutobuildBaselineCompare):
    def setUp(self):
        BaseTest.setUp(self)
        os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.abspath(os.path.dirname(__file__))])
        self.tmp_file = self.get_tmp_file()
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        package = configfile.PackageDescription('test')
        package.license = 'Public Domain'
        working_platform = configfile.PlatformDescription()
        common_platform = configfile.PlatformDescription()
        package.platforms[common.get_current_platform()] = working_platform
        package.platforms['common'] = common_platform
        self.config.package_description = package

    def test_add(self):
        manifest.add(self.config, 'common', '*.cpp')
        manifest.add(self.config, 'common', '*.h')
        manifest.add(self.config, 'common', '*.py')
        common_manifest = self.config.get_platform('common').manifest
        assert ('*.cpp' in common_manifest) and ('*.h' in common_manifest) and ('*.py' in common_manifest)
        assert len(common_manifest) == 3

    def test_remove(self):
        manifest.add(self.config, 'common', '*.cpp')
        manifest.add(self.config, 'common', '*.h')
        manifest.add(self.config, 'common', '*.py')
        manifest.remove(self.config, 'common', '*.cpp')
        common_manifest = self.config.get_platform('common').manifest
        assert (not '*.cpp' in common_manifest)
        assert ('*.h' in common_manifest) and ('*.py' in common_manifest)
        assert len(common_manifest) == 2

    def test_clear(self):
        manifest.add(self.config, 'common', '*.cpp')
        manifest.add(self.config, 'common', '*.h')
        manifest.add(self.config, 'common', '*.py')
        manifest.clear(self.config, 'common')
        common_manifest = self.config.get_platform('common').manifest
        assert not common_manifest

    def test_autobuild_manifest(self):
        self.config.save()
        self.autobuild("manifest", "--config-file=" + self.tmp_file,
                       "-p", "common", "add", "*.cpp", "*.h", "*.py")
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        common_manifest = self.config.get_platform('common').manifest
        assert ('*.cpp' in common_manifest) and ('*.h' in common_manifest) and ('*.py' in common_manifest)
        self.autobuild('manifest', '--config-file=' + self.tmp_file,
                       '-p', 'common', 'remove', '*.cpp')
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        common_manifest = self.config.get_platform('common').manifest
        assert (not '*.cpp' in common_manifest)
        assert ('*.h' in common_manifest) and ('*.py' in common_manifest)

    def tearDown(self):
        self.cleanup_tmp_file()
        BaseTest.tearDown(self)
