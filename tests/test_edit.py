import os

import llsd

from autobuild import configfile
from autobuild.autobuild_tool_edit import AutobuildTool
from tests.baseline_compare import AutobuildBaselineCompare
from tests.basetest import BaseTest


class TestEdit(BaseTest, AutobuildBaselineCompare):
    def setUp(self):
        BaseTest.setUp(self)
        os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.abspath(os.path.dirname(__file__))])
        self.tmp_file = self.get_tmp_file()
        self.edit_cmd = AutobuildTool()

    def _try_cmd(self, args):
        """
        Try running an edit 'command with args'.
        Return results.
        """
        self.edit_cmd.main(args)
        with open(self.tmp_file, 'rb') as f:
            return llsd.parse(f.read())

    def test_build(self):
        """
        Perform non-interactive configuration of build command.
        Check results.
        """
        args = ['build', "--config-file=%s" % self.tmp_file, 'name=newbuild', 'platform=windows', 'command=makethis']
        expected_config = {'package_description': {'platforms': {'windows': {'name': 'windows', 'configurations': {'newbuild': {'build': {'command': 'makethis'}, 'name': 'newbuild'}}}}}, 'version': configfile.AUTOBUILD_CONFIG_VERSION, 'type': 'autobuild'}
        built_config = self._try_cmd(args)
        self.assertEqual(expected_config, built_config)

    def test_configure(self):
        """
        Perform non-interactive configuration of configure command.
        Check results.
        """
        args = ['configure', "--config-file=%s" % self.tmp_file, 'name=newbuild', 'platform=windows', 'command=makethat']
        expected_config = {'package_description': {'platforms': {'windows': {'name': 'windows', 'configurations': {'newbuild': {'configure': {'command': 'makethat'}, 'name': 'newbuild'}}}}}, 'version': configfile.AUTOBUILD_CONFIG_VERSION, 'type': 'autobuild'}
        built_config = self._try_cmd(args)
        self.assertEqual(expected_config, built_config)

    def test_build_configure(self):
        """
        Perform two updates to the config file in series.
        Check results after each iteration.
        """
        args = ['configure', "--config-file=%s" % self.tmp_file, 'name=newbuild', 'platform=windows', 'command=makethat']
        built_config1 = self._try_cmd(args)
        expected_config1 = {'package_description': {'platforms': {'windows': {'name': 'windows', 'configurations': {'newbuild': {'configure': {'command': 'makethat'}, 'name': 'newbuild'}}}}}, 'version': configfile.AUTOBUILD_CONFIG_VERSION, 'type': 'autobuild'}
        self.assertEqual(expected_config1, built_config1)
        args = ['build', "--config-file=%s" % self.tmp_file, 'name=newbuild', 'platform=windows', 'command=makethis']
        built_config2 = self._try_cmd(args)
        expected_config2 = {'package_description': {'platforms': {'windows': {'name': 'windows', 'configurations': {'newbuild': {'build': {'command': 'makethis'}, 'name': 'newbuild', 'configure': {'command': 'makethat'}}}}}}, 'version': configfile.AUTOBUILD_CONFIG_VERSION, 'type': 'autobuild'}
        self.assertEqual(expected_config2, built_config2)

    def test_platform_configure(self):
        args = ['platform', "--config-file=%s" % self.tmp_file, 'name=windows', 'build_directory=foo/bar/baz']
        built_config = self._try_cmd(args)
        self.assertEqual(built_config['package_description']['platforms']['windows']['build_directory'], 'foo/bar/baz')

    def test_platform_configure_ios(self):
        args = ['platform', "--config-file=%s" % self.tmp_file, 'name=common', 'build_directory=foo/bar/baz']
        built_config = self._try_cmd(args)
        args = ['platform', "--config-file=%s" % self.tmp_file, 'name=darwin_ios', 'build_directory=foo/bar/baz_ios']
        built_config = self._try_cmd(args)
        self.assertEqual(built_config['package_description']['platforms']['common']['build_directory'], 'foo/bar/baz')
        self.assertEqual(built_config['package_description']['platforms']['darwin_ios']['build_directory'], 'foo/bar/baz_ios')

    def tearDown(self):
        self.cleanup_tmp_file()
        BaseTest.tearDown(self)


class TestEditCmdLine(BaseTest, AutobuildBaselineCompare):
    def setUp(self):
        BaseTest.setUp(self)
        os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.abspath(os.path.dirname(__file__))])
        self.tmp_file = self.get_tmp_file()

    def test_autobuild_edit(self):
        self.autobuild('edit', '--config-file=' + self.tmp_file, '--help')
        self.autobuild('edit', 'build', '--config-file=' + self.tmp_file,
                       'name=foo', 'command=buildme.py')

    def tearDown(self):
        self.cleanup_tmp_file()
        BaseTest.tearDown(self)
