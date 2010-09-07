#!/usr/bin/env python
#
# Integration test to exercise the config file reading/writing
#

import unittest
import os
import sys
from baseline_compare import AutobuildBaselineCompare
from autobuild import configfile

class TestConfigFile(unittest.TestCase, AutobuildBaselineCompare):

    def setUp(self):
        pass

    def test_0(self):
        """
        Create a new config file from scratch
        """
        tmp_file = self.get_tmp_file(0)

        c = configfile.ConfigFile()

        p = configfile.PackageInfo()
        p.summary = "Test package"
        p.description = "Test package created by test_configfile.py"
        p.copyright = "Copyright (c) 2010, Linden Research, Inc."
        p.set_archives_url('linux', 'http://www.secondlife.com')
        p.set_archives_md5('linux', '22eac1bea219257a71907cbe1170c640')
        c.set_package('test1', p)

        p = configfile.PackageInfo()
        p.summary = "Another package"
        p.description = "A second test package created by test_configfile.py"
        p.copyright = "Copyright (c) 2010, Linden Research, Inc."
        p.set_archives_url('common', 'http://www.secondlife.com/package-common')
        p.set_archives_md5('common', '22eac1bea219257a71907cbe1170c640')
        p.set_archives_url('windows', 'http://www.secondlife.com/package-windows')
        p.set_archives_md5('windows', '28189f725a5c53684ce1c925ee5fecd7')
        c.set_package('test2', p)

        c.save(tmp_file)
        self.diff_tmp_file_against_baseline("data/config_test_0.xml")

    def test_1(self):
        """
        Create a new config file with all supported fields
        """
        tmp_file = self.get_tmp_file(1)

        c = configfile.ConfigFile()

        p = configfile.PackageInfo()
        p.summary = "Test package"
        p.description = "Test package created by test_configfile.py"
        p.copyright = "Copyright (c) 2010, Linden Research, Inc."
        p.license = "GPL2"
        p.licensefile = "http://develop.secondlife.com/develop-on-sl-platform/viewer-licensing/gpl/"
        p.homepage = "http://www.secondlife.com/"
        p.uploadtos3 = False
        p.source = "http://www.secondlife.com/package-source"
        p.sourcetype = "archive"
        p.sourcedir = "package-source"
        p.version = "1.0"
        p.patches = "foo bar"
        p.obsoletes = "baz bar foo"

        p.set_archives_url('linux', 'http://www.secondlife.com')
        p.set_archives_md5('linux', '22eac1bea219257a71907cbe1170c640')

        p.set_dependencies_url('linux', 'http://www.secondlife.com')
        p.set_dependencies_md5('linux', '22eac1bea219257a71907cbe1170c640')

        p.set_configure_command('common', 'configure --enabled-shared')
        p.set_build_command('common', 'build.sh')
        p.set_build_directory('common', 'bin')
        p.set_post_build_command('common', 'postbuild.sh')

        p.set_manifest_files('common', ['file1','file2'])
        p.set_manifest_files('windows', ['file3'])

        c.set_package('test1', p)

        c.save(tmp_file)
        self.diff_tmp_file_against_baseline("data/config_test_1.xml")

    def test_2(self):
        """
        Read and write an existing config file
        """
        tmp_file = self.get_tmp_file(2)

        c = configfile.ConfigFile()
        c.load(os.path.join(sys.path[0], "data/config_test_2.xml"))
        c.save(tmp_file)
        self.diff_tmp_file_against_baseline("data/config_test_2.xml")

    def test_3(self):
        """
        Read a config file and print some fields
        """
        tmp_file = self.get_tmp_file(3)

        c = configfile.ConfigFile()
        c.load(os.path.join(sys.path[0], "data/config_test_3.xml"))

        lines = []
        p = c.package_definition
        lines.append("name: %s\n" % p.name)
        lines.append("summary: %s\n" % p.summary)
        lines.append("description: %s\n" % p.description)
        lines.append("copyright: %s\n" % p.copyright)
        lines.append("license: %s\n" % p.license)
        lines.append("homepage: %s\n" % p.homepage)
        lines.append("uploadtos3: %s\n" % p.uploadtos3)
        lines.append("source: %s\n" % p.source)
        lines.append("sourcetype: %s\n" % p.sourcetype)
        lines.append("sourcedir: %s\n" % p.sourcedir)
        lines.append("builddir: %s\n" % p.build_directory('common'))
        lines.append("version: %s\n" % p.version)
        lines.append("patches: %s\n" % p.patches)
        lines.append("obsoletes: %s\n" % p.obsoletes)

        lines.append("archives_url(linux): %s\n" % p.archives_url('linux'))
        lines.append("archives_md5(linux): %s\n" % p.archives_md5('linux'))

        lines.append("dependencies_url(common): %s\n" % p.dependencies_url('linux'))
        lines.append("dependencies_md5(common): %s\n" % p.dependencies_md5('linux'))

        lines.append("configure(common): %s\n" % p.configure_command('common'))
        lines.append("build(common): %s\n" % p.build_command('common'))
        lines.append("postBuild(common): %s\n" % p.post_build_command('common'))

        lines.append("manifest(common): %s\n" % p.manifest_files('common'))
        lines.append("manifest(windows): %s\n" % p.manifest_files('windows'))
        lines.append("-" * 40 + "\n")

        open(tmp_file, "w").writelines(lines)
        self.diff_tmp_file_against_baseline("data/config_test_3.txt")

    def test_4(self):
        """
        Test property checking logic on PackageInfo
        """
        p = configfile.PackageInfo()
        try:
            p.foobar = "Shouldn't work"
        except:
            pass
        else:
            self.fail("Should not be able to set p.foobar")

    def tearDown(self):
        self.cleanup_tmp_file()

if __name__ == '__main__':
    unittest.main()

