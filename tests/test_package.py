import json
import logging
import os
import re
import shutil
import tarfile
import tempfile
from string import Template
from zipfile import ZipFile

import autobuild.autobuild_tool_package as package
from autobuild import common, configfile, archive_utils
from tests.basetest import BaseTest, CaptureStdout, ExpectError, clean_dir, clean_file

# ****************************************************************************
#   TODO
# - Test for specific --build-dir (new select_directories() mechanism)
# - Test packaging from configuration-specific build directory
# - Test packaging from --all configurations
# - Test packaging from build directory(ies) for specified --configuration(s)
# ****************************************************************************

logger=logging.getLogger("autobuild.test_package")

class PackageOptions(object):
    def __init__(self, data_dir):
        self.addrsize=common.DEFAULT_ADDRSIZE
        self.clean_only=True
        self.check_license=False
        self.dry_run=False
        self.all=False
        self.configurations=None
        self.platform=None
        self.results_file=None
        self.archive_filename=None
        self.archive_format=None
        self.select_dir=None
        self.autobuild_filename=os.path.join(data_dir, "autobuild-package-config.xml")

class TestPackaging(BaseTest):
    def setUp(self):
        BaseTest.setUp(self)
        self.temp_dir = tempfile.mkdtemp()
        # Copy our data_dir to temp_dir because loading a config file may
        # cause it to be updated and resaved.
        orig_data_dir = os.path.join(self.this_dir, "data")
        self.data_dir = os.path.join(self.temp_dir, "data")
        shutil.copytree(orig_data_dir, self.data_dir)
        self.config_path = os.path.join(self.data_dir, "autobuild-package-config.xml")
        self.config = configfile.ConfigurationDescription(self.config_path)
        self.platform = 'common'
        self.tar_basename = os.path.join(self.data_dir, "test1-1.0-common-123456")
        self.tar_name = self.tar_basename + ".tar.bz2"
        self.tar_gz_name = self.tar_basename + ".tar.gz"
        self.tar_xz_name = self.tar_basename + ".tar.xz"
        self.tar_zst_name = self.tar_basename + ".tar.zst"
        self.zip_name = self.tar_basename + ".zip"
        self.expected_files=['include/file1','LICENSES/test1.txt','autobuild-package.xml']
        self.expected_files.sort()
        self.saved_dir=os.getcwd()
        os.chdir(os.path.join(self.temp_dir, "data"))

    def instantiateTemplate(self, source_name, dest_name, changes):
        template_file=open(source_name,'r')
        template=Template(template_file.read())
        template_file.close()
        modified=template.substitute(changes)
        dest=open(dest_name,'w')
        dest.write(modified)
        dest.close()

    def tearDown(self):
        os.chdir(self.saved_dir)
        clean_dir(self.temp_dir)
        BaseTest.tearDown(self)

    def tar_has_expected(self,tar):
        if 'tar.zst' in tar:
            tarball = archive_utils.ZstdTarFile(tar, 'r')
        else:
            tarball = tarfile.open(tar, 'r')
        packaged_files=tarball.getnames()
        packaged_files.sort()
        self.assertEqual(packaged_files, self.expected_files)
        tarball.close()

    def zip_has_expected(self,zip):
        zip_file = ZipFile(zip,'r')
        packaged_files=zip_file.namelist()
        packaged_files.sort()
        self.assertEqual(packaged_files, self.expected_files)
        zip_file.close()

    def test_package(self):
        logger.setLevel(logging.DEBUG)
        package.package(self.config, self.config.get_build_directory(None, 'common'), 'common', archive_format='tbz2')
        assert os.path.exists(self.tar_name), "%s does not exist" % self.tar_name
        self.tar_has_expected(self.tar_name)

    def test_results(self):
        logger.setLevel(logging.DEBUG)
        results_output=tempfile.mktemp()
        package.package(self.config, self.config.get_build_directory(None, 'common'),
                        'common', archive_format='tbz2', results_file=results_output)
        expected_results_regex='''\
autobuild_package_name="%s"
autobuild_package_version="%s"
autobuild_package_clean="true"
autobuild_package_metadata="%s"
autobuild_package_platform="%s"
autobuild_package_filename="%s"
autobuild_package_md5="%s"
autobuild_package_blake2b="%s"
autobuild_package_sha1="%s"
autobuild_package_sha256="%s"
$''' % ('test1', '1.0', re.escape(os.path.join(self.data_dir, "package-test", "autobuild-package.xml")),
        "common", re.escape(self.tar_name), "[0-9a-f]{32}", "[0-9a-f]{128}", "[0-9a-f]{40}", "[0-9a-f]{64}")
        expected=re.compile(expected_results_regex, flags=re.MULTILINE)
        assert os.path.exists(results_output), "results file not found: %s" % results_output
        actual_results = open(results_output,'r').read()
        assert expected.match(actual_results), \
          "\n!!! expected regex:\n%s\n!!! actual result:\n%s" % (expected_results_regex, actual_results)
        clean_file(results_output)

    def test_results_json(self):
        logger.setLevel(logging.DEBUG)
        results_file = tempfile.mktemp() + '.json'
        package.package(self.config, self.config.get_build_directory(None, 'common'),
                        'common', archive_format='tbz2', results_file=results_file)
        with open(results_file) as f:
            results = json.load(f)
            self.assertEqual(results["autobuild_package_name"], "test1")
            self.assertEqual(results["autobuild_package_version"], "1.0")
            self.assertEqual(results["autobuild_package_clean"], "true")
            self.assertEqual(results["autobuild_package_metadata"], os.path.join(self.data_dir, "package-test", "autobuild-package.xml"))
            self.assertEqual(results["autobuild_package_platform"], "common")
            self.assertEqual(results["autobuild_package_filename"], self.tar_name)
            self.assertEqual(len(results["autobuild_package_md5"]), 32)
            self.assertEqual(len(results["autobuild_package_blake2b"]), 128)
            self.assertEqual(len(results["autobuild_package_sha1"]), 40)
            self.assertEqual(len(results["autobuild_package_sha256"]), 64)

    def test_package_other_version(self):
        # read the existing metadata file and update stored package version
        build_directory = self.config.get_build_directory(None, 'common')
        metadata_filename = os.path.join(build_directory,
                                         configfile.PACKAGE_METADATA_FILE)
        metadata = configfile.MetadataDescription(metadata_filename)
        metadata.package_description.version = "2.3"
        metadata.save()
        # okay, now use that to build package
        package.package(self.config, build_directory, 'common', archive_format='tbz2')
        # should have used updated package version in tarball name
        expected_tar_name = self.tar_name.replace("-1.0-", "-2.3-")
        if not os.path.exists(expected_tar_name):
            if os.path.exists(self.tar_name):
                raise AssertionError("package built %s instead of %s" %
                                     (self.tar_name, expected_tar_name))
            raise AssertionError("package built neither %s nor %s" %
                                 (self.tar_name, expected_tar_name))

    def test_autobuild_package(self):
        with CaptureStdout() as stream:
            self.autobuild("package",
                           "--config-file=" + self.config_path,
                           "-p", "common")
        assert os.path.exists(self.tar_name), "%s does not exist" % self.tar_name
        self.tar_has_expected(self.tar_name)
        self.remove(self.tar_name)
        self.autobuild("package",
                       "--config-file=" + self.config_path,
                       "--archive-format=tgz",
                       "-p", "common")
        assert os.path.exists(self.tar_gz_name), "%s does not exist" % self.tar_gz_name
        self.tar_has_expected(self.tar_gz_name)
        self.remove(self.tar_gz_name)
        self.autobuild("package",
                       "--config-file=" + self.config_path,
                       "--archive-format=txz",
                       "-p", "common")
        assert os.path.exists(self.tar_xz_name), "%s does not exist" % self.tar_xz_name
        self.tar_has_expected(self.tar_xz_name)
        self.remove(self.tar_xz_name)
        self.autobuild("package",
                       "--config-file=" + self.config_path,
                       "--archive-format=tzst",
                       "-p", "common")
        assert os.path.exists(self.tar_zst_name), "%s does not exist" % self.tar_zst_name
        self.tar_has_expected(self.tar_zst_name)
        self.remove(self.tar_zst_name)
        self.autobuild("package",
                       "--config-file=" + self.config_path,
                       "--archive-format=zip",
                       "-p", "common")
        assert os.path.exists(self.zip_name), "%s does not exist" % self.zip_name
        self.zip_has_expected(self.zip_name)
        self.remove(self.zip_name)

        self.autobuild("package",
                       "--config-file=" + self.config_path,
                       "-p", "common",
                       "--dry-run")
        assert not os.path.exists(self.zip_name), "%s created by dry run" % self.zip_name
        assert not os.path.exists(self.tar_name), "%s created by dry run" % self.tar_name

    def test_disallowed_paths(self):
        self.options = PackageOptions(self.data_dir)
        config_template=os.path.join(self.data_dir,"autobuild-package-disallowedpath-config.xml")
        # earlier tests establish the 'common' platform
        # clear that out so that this test uses both the current and common
        del os.environ['AUTOBUILD_PLATFORM']
        del os.environ['AUTOBUILD_PLATFORM_OVERRIDE']
        common.Platform=None
        self.platform=common.get_current_platform()
        logger.debug("platform "+self.platform)
        self.options.platform=self.platform
        platform_config=self.platform+"-autobuild-package-disallowedpath-config.xml"
        self.instantiateTemplate(config_template
                                ,platform_config
                                ,{'PLATFORM':self.platform})
        self.options.autobuild_filename = platform_config
        # it's hard to come up with a root path (such as /etc/passwd) that will be on all platforms
        # so we use "/" here; if you use some /etc/passwd, you get a different exception
        # (No files matched manifest specifiers) when the file does not exist
        badpaths=["include/../include/file1","include/../file2","../package-test/include/file1","include/..","/"]
        with ExpectError("Absolute paths or paths with parent directory elements are not allowed:\n  "+'\n  '.join(sorted(badpaths))+"\n",
                         "Bad paths not detected"):
            package.AutobuildTool().run(self.options)

    def test_package_missing(self):
        self.options = PackageOptions(self.data_dir)
        config_template=os.path.join(self.data_dir,"autobuild-package-missing-config.xml")
        # earlier tests establish the 'common' platform
        # clear that out so that this test uses both the current and common
        del os.environ['AUTOBUILD_PLATFORM']
        del os.environ['AUTOBUILD_PLATFORM_OVERRIDE']
        common.Platform=None
        self.platform=common.get_current_platform()
        logger.debug("platform "+self.platform)
        self.options.platform=self.platform
        platform_config=self.platform+"-autobuild-package-missing-config.xml"
        self.instantiateTemplate(config_template
                                ,platform_config
                                ,{'PLATFORM':self.platform})
        self.options.autobuild_filename = platform_config
        with ExpectError("No files matched manifest specifiers:\n"+'\n'.join(["missing/\\*.txt","not_there.txt"]),
                         "Missing files not detected"):
            package.AutobuildTool().run(self.options)
