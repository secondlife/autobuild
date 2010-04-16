#!/usr/bin/env python
#
# Integration test to exercise the config file reading/writing
#

import unittest
import os
import sys
import difflib
from autobuild import configfile

class TestConfigFile(unittest.TestCase):

    def setUp(self):
        self.failed = False
        self.tmp_file = None

    def setTmpFile(self, n):
        """
        Write to a different tmp file for each test, so we can remove
        it if the test passes, or leave it around for debugging if it
        fails.
        """
        self.tmp_file = os.path.join(sys.path[0], "configfile_%d.out" % n)

    def diff(self,output, baseline):
        """
        Do a udiff between two fails and raise an exception if different
        """
        baseline = os.path.join(sys.path[0], baseline)
        output_lines = [x.rstrip() for x in file(output, 'rb').readlines()]
        baseline_lines = [x.rstrip() for x in file(baseline, 'rb').readlines()]
        udiff = difflib.unified_diff(output_lines, baseline_lines, fromfile=output,
                                     tofile=baseline, lineterm="")
        error = []
        for line in udiff:
            error.append(line)
        if error:
            self.failed = True
            self.fail("Output does not match baseline.\nOutput: %s\nBaseline: %s\nDiff:\n%s" %
                      (output, baseline, "\n".join(error)))

    def test_0(self):
        """
        Create a new config file from scratch
        """
        self.setTmpFile(0)

        c = configfile.ConfigFile()

        p = configfile.PackageInfo()
        p.summary = "Test package"
        p.description = "Test package created by test_configfile.py"
        p.copyright = "Copyright (c) 2010, Linden Research, Inc."
        p.setPackagesUrl('linux', 'http://www.secondlife.com')
        p.setPackagesMD5('linux', '22eac1bea219257a71907cbe1170c640')
        c.setPackage('test1', p)

        p = configfile.PackageInfo()
        p.summary = "Another package"
        p.description = "A second test package created by test_configfile.py"
        p.copyright = "Copyright (c) 2010, Linden Research, Inc."
        p.setPackagesUrl('common', 'http://www.secondlife.com/package-common')
        p.setPackagesMD5('common', '22eac1bea219257a71907cbe1170c640')
        p.setPackagesUrl('windows', 'http://www.secondlife.com/package-windows')
        p.setPackagesMD5('windows', '28189f725a5c53684ce1c925ee5fecd7')
        c.setPackage('test2', p)

        c.setLicense('GPL', 'Blah blah blah ...')

        c.save(self.tmp_file)
        self.diff(self.tmp_file, "data/config_test_0.xml")

    def test_1(self):
        """
        Create a new config file with all supported fields
        """
        self.setTmpFile(1)

        c = configfile.ConfigFile()

        p = configfile.PackageInfo()
        p.summary = "Test package"
        p.description = "Test package created by test_configfile.py"
        p.copyright = "Copyright (c) 2010, Linden Research, Inc."
        p.license = "GPL2"
        p.homepage = "http://www.secondlife.com/"
        p.uploadtos3 = False
        p.source = "http://www.secondlife.com/package-source"
        p.sourcetype = "archive"
        p.sourcedir = "package-source"
        p.builddir = "package-build"
        p.version = "1.0"
        p.patches = "foo bar"
        p.obsoletes = "baz bar foo"

        p.setPackagesUrl('linux', 'http://www.secondlife.com')
        p.setPackagesMD5('linux', '22eac1bea219257a71907cbe1170c640')

        p.setDependsUrl('linux', 'http://www.secondlife.com')
        p.setDependsMD5('linux', '22eac1bea219257a71907cbe1170c640')

        p.setConfigureCommand('common', 'configure --enabled-shared')
        p.setBuildCommand('common', 'build.sh')
        p.setPostBuildCommand('common', 'postbuild.sh')

        p.setManifestFiles('common', 'file1 file2')
        p.setManifestFiles('windows', 'file3')

        c.setPackage('test1', p)

        c.setLicense('GPL', 'Blah blah blah ...')
        c.setLicense('GPL2', 'Blah blah blah ...')

        c.save(self.tmp_file)
        self.diff(self.tmp_file, "data/config_test_1.xml")

    def test_2(self):
        """
        Read and write an existing config file
        """
        self.setTmpFile(2)

        c = configfile.ConfigFile()
        c.load(os.path.join(sys.path[0], "data/config_test_2.xml"))
        c.save(self.tmp_file)
        self.diff(self.tmp_file, "data/config_test_2.xml")

    def test_3(self):
        """
        Read a config file and print some fields
        """
        self.setTmpFile(3)

        c = configfile.ConfigFile()
        c.load(os.path.join(sys.path[0], "data/config_test_3.xml"))

        lines = []
        for name in c.packages:
            p = c.package(name)
            lines.append("name: %s\n" % name)
            lines.append("summary: %s\n" % p.summary)
            lines.append("description: %s\n" % p.description)
            lines.append("copyright: %s\n" % p.copyright)
            lines.append("license: %s\n" % p.license)
            lines.append("homepage: %s\n" % p.homepage)
            lines.append("uploadtos3: %s\n" % p.uploadtos3)
            lines.append("source: %s\n" % p.source)
            lines.append("sourcetype: %s\n" % p.sourcetype)
            lines.append("sourcedir: %s\n" % p.sourcedir)
            lines.append("builddir: %s\n" % p.builddir)
            lines.append("version: %s\n" % p.version)
            lines.append("patches: %s\n" % p.patches)
            lines.append("obsoletes: %s\n" % p.obsoletes)

            lines.append("packagesUrl(linux): %s\n" % p.packagesUrl('linux'))
            lines.append("packagesMD5(linux): %s\n" % p.packagesMD5('linux'))

            lines.append("dependsUrl(common): %s\n" % p.dependsUrl('linux'))
            lines.append("dependsMD5(common): %s\n" % p.dependsMD5('linux'))

            lines.append("configure(common): %s\n" % p.configureCommand('common'))
            lines.append("build(common): %s\n" % p.buildCommand('common'))
            lines.append("postBuild(common): %s\n" % p.postBuildCommand('common'))

            lines.append("manifest(common): %s\n" % p.manifestFiles('common'))
            lines.append("manifest(windows): %s\n" % p.manifestFiles('windows'))
            lines.append("-" * 40 + "\n")

        for name in c.licenses:
            lines.append("license: %s\n" % name)
            lines.append("%s\n" % c.license(name))
            lines.append("-" * 40 + "\n")
            
        open(self.tmp_file, "w").writelines(lines)
        self.diff(self.tmp_file, "data/config_test_3.txt")

    def test_4(self):
        """
        Test property checking logic on PackageInfo
        """
        self.setTmpFile(4)

        c = configfile.ConfigFile()
        p = configfile.PackageInfo()
        try:
            p.foobar = "Shouldn't work"
        except:
            pass
        else:
            self.fail("Should not be able to set p.foobar")

    def tearDown(self):
        """
        Remove our temp file, though if the test succeeded
        """
        if not self.failed and os.path.exists(self.tmp_file):
            os.remove(self.tmp_file)


if __name__ == '__main__':
    unittest.main()

