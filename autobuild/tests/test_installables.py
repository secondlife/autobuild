# $LicenseInfo:firstyear=2010&license=mit$
# Copyright (c) 2010, Linden Research, Inc.
# $/LicenseInfo$
#
# Unit testing of manifest subcommand.
#


import os
import subprocess
import sys
import unittest

from autobuild import configfile
from autobuild import common
from autobuild.autobuild_main import Autobuild
from baseline_compare import AutobuildBaselineCompare
import autobuild.autobuild_tool_installables as installables


class TestInstallables(unittest.TestCase, AutobuildBaselineCompare):
    def setUp(self):
        os.environ["PATH"] = os.pathsep.join([os.environ["PATH"], os.path.abspath(os.path.dirname(__file__))])
        self.tmp_file = self.get_tmp_file(0)
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        
    def test_add_edit_remove(self):
        data = dict(license='GPL', license_file='LICENSES/test.txt', platform='darwin',
            url='http://foo.bar.com/test.tar.bz2')
        installables.add(self.config, 'test', data)
        assert len(self.config.installables) == 1
        package_description = self.config.installables['test']
        assert package_description.name == 'test'
        assert package_description.license == data['license']
        assert data['platform'] in package_description.platforms
        platform_description = package_description.platforms[data['platform']]
        assert platform_description.archive is not None
        assert platform_description.archive.url == data['url']
        edit_data = dict(license='Apache', platform='darwin', hash_algorithm='sha-1')
        installables.edit(self.config, 'test', edit_data)
        assert package_description.license == edit_data['license']
        assert platform_description.archive.hash_algorithm == edit_data['hash_algorithm']
        installables.remove(self.config, 'test')
        assert len(self.config.installables) == 0

    def test_autobuild_installables(self):
        self.config.save()
        cmd = "autobuild installables --config-file=%s "\
            "--archive http://foo.bar.com/test-1.1-darwin-20101008.tar.bz2 add license=GPL "\
            "license_file=LICENSES/test.txt platform=darwin"% \
            self.tmp_file
        result = subprocess.call(cmd, shell=True)
        assert result == 0
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        assert len(self.config.installables) == 1
        package_description = self.config.installables['test']
        assert package_description.name == 'test'
        assert package_description.license == 'GPL'
        assert 'darwin' in package_description.platforms
        platform_description = package_description.platforms['darwin']
        assert platform_description.archive is not None
        assert platform_description.archive.url == 'http://foo.bar.com/test-1.1-darwin-20101008.tar.bz2'
        cmd = "autobuild installables --config-file=%s "\
            "edit test license=Apache hash=74688495b0871ddafcc0ca1a6db57c34 "\
            "url=http://foo.bar.com/test-1.1-darwin-20101008.tar.bz2 " \
            "hash_algorithm='sha-1' platform=darwin"% \
            self.tmp_file
        result = subprocess.call(cmd, shell=True)
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        assert len(self.config.installables) == 1
        package_description = self.config.installables['test']
        platform_description = package_description.platforms['darwin']
        assert package_description.license == 'Apache'
        assert package_description.version == '1.1'
        assert package_description.name == 'test'
        assert platform_description.archive.hash_algorithm == 'sha-1'
        assert platform_description.archive.hash == "74688495b0871ddafcc0ca1a6db57c34"
        assert platform_description.archive.url == 'http://foo.bar.com/test-1.1-darwin-20101008.tar.bz2'
        cmd = "autobuild installables --config-file=%s remove test"% \
            self.tmp_file
        result = subprocess.call(cmd, shell=True)
        assert result == 0
        self.config = configfile.ConfigurationDescription(self.tmp_file)
        assert len(self.config.installables) == 0
                    
    def tearDown(self):
        self.cleanup_tmp_file()
