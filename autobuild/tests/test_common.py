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
#!/usr/bin/python

import os
import shutil
import tarfile
import tempfile
import unittest
from zipfile import ZipFile
from autobuild import common

class TestCommon(unittest.TestCase):
    def setUp(self):
        pass

    def test_find_executable(self):
        shell = "sh"
        if common.get_current_platform() == common.PLATFORM_WINDOWS:
            shell = "cmd"

        exe_path = common.find_executable(shell)
        assert exe_path != None
        
    def test_extract_package(self):
        try:
            tmp_dir = tempfile.mkdtemp()
            tar_cachename = common.get_package_in_cache("test.tar.bz2")
            zip_cachename = common.get_package_in_cache("test.zip")
            test_file_path = os.path.join("data", "package-test", "file2")
            
            # Test tarball extraction
            tar_file = tarfile.open(tar_cachename, 'w:bz2')
            tar_file.add(os.path.join(os.path.dirname(__file__), test_file_path), test_file_path)
            tar_file.close()
            common.extract_package("test.tar.bz2", tmp_dir)
            assert os.path.isfile(os.path.join(tmp_dir, "data", "package-test", "file2"))
            
            # Test zip extraction
            zip_archive = ZipFile(zip_cachename, 'w')
            zip_archive.write(os.path.join(os.path.dirname(__file__), test_file_path), test_file_path)
            zip_archive.close()
            common.extract_package("test.zip", tmp_dir)
            assert os.path.isfile(os.path.join(tmp_dir, "data", "package-test", "file2"))
        finally:
            if os.path.isfile(tar_cachename):
                os.remove(tar_cachename)
            if os.path.isfile(zip_cachename):
                os.remove(zip_cachename)
            shutil.rmtree(tmp_dir, True)


    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()

