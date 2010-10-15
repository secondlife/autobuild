#!/usr/bin/env python

import unittest
from autobuild.executable import Executable

class TestExecutable(unittest.TestCase):
    def setUp(self):
        pass

    def test_simple_executable(self):
        sleepExecutable = Executable(command='sleep', arguments=['1'])
        result = sleepExecutable()
        assert result == 0
        
    def test_compound_executable(self):
        parentExecutable = Executable(command='grep', arguments=['foobarbaz', '.', '>/dev/null'], options=['-l', '-r'])
        childExecutable = Executable(parent=parentExecutable, options=['-i'])
        otherChildExecutable = Executable(parent=parentExecutable, command='egrep', arguments=['foo','.'])
        assert childExecutable.get_options() == ['-l', '-r', '-i']
        assert childExecutable.get_command() == 'grep'
        assert otherChildExecutable.get_command() == 'egrep'
        assert otherChildExecutable.get_arguments() == ['foo','.']
        result = childExecutable()
        assert result == 0
        result = parentExecutable()
        assert result == 0
 
    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()
