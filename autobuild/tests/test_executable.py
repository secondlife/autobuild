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

import sys
import unittest
from nose.plugins.skip import SkipTest
from autobuild.executable import Executable
from .basetest import BaseTest

class TestExecutable(BaseTest):
    def setUp(self):
        BaseTest.setUp(self)

    def test_simple_executable(self):
        sleepExecutable = Executable(command='sleep', arguments=['1'])
        result = sleepExecutable()
        assert result == 0
        
    def test_compound_executable(self):
        parentExecutable = Executable(command='grep', arguments=['foobarbaz', '.'], options=['-l', '-r'])
        childExecutable = Executable(parent=parentExecutable, options=['-i'])
        otherChildExecutable = Executable(parent=parentExecutable, command='egrep', arguments=['foo','.'])
        assert childExecutable.get_options() == ['-l', '-r', '-i']
        assert childExecutable.get_command() == 'grep'
        assert otherChildExecutable.get_command() == 'egrep'
        assert otherChildExecutable.get_arguments() == ['foo','.']
        # On Windows, you can't count on grep or egrep.
        if sys.platform.startswith("win"):
            raise SkipTest("On Windows, can't count on finding grep")
        result = childExecutable()
        assert result == 0, "%s => %s" % (childExecutable._get_all_arguments([]), result)
        result = parentExecutable()
        assert result == 0, "%s => %s" % (parentExecutable._get_all_arguments([]), result)
 
    def tearDown(self):
        BaseTest.tearDown(self)

if __name__ == '__main__':
    unittest.main()
