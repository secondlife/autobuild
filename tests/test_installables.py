import os

import autobuild.autobuild_tool_installables as installables
from autobuild import configfile
from tests.baseline_compare import AutobuildBaselineCompare
from tests.basetest import BaseTest, assert_in


class TestInstallables(BaseTest, AutobuildBaselineCompare):
    def setUp(self):
        BaseTest.setUp(self)
        os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.abspath(os.path.dirname(__file__))])
        self.tmp_file = self.get_tmp_file()
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        self.datadir = os.path.join(os.path.dirname(__file__), "data")

    def test_add_edit_remove(self):
        local_archive=os.path.join(self.datadir,'bogus-0.1-common-111.tar.bz2')
        data = ('license=tut', 'license_file=LICENSES/bogus.txt', 'platform=darwin',
            'url='+local_archive)
        installables.add(self.config, 'bogus', None, data)
        self.assertEqual(len(self.config.installables), 1)
        package_description = self.config.installables['bogus']
        self.assertEqual(package_description.name, 'bogus')
        self.assertEqual(package_description.license, 'tut')
        assert_in('darwin', package_description.platforms)
        platform_description = package_description.platforms['darwin']
        assert platform_description.archive is not None
        assert platform_description.archive.url.endswith(local_archive)
        edit_data = ('license=Apache', 'platform=darwin', 'hash_algorithm=sha-1')
        installables.edit(self.config, 'bogus', None, edit_data)
        self.assertEqual(package_description.license, 'Apache')
        self.assertEqual(platform_description.archive.hash_algorithm, 'sha-1')
        installables.remove(self.config, 'bogus')
        self.assertEqual(len(self.config.installables), 0)

    def tearDown(self):
        self.cleanup_tmp_file()
        BaseTest.tearDown(self)
