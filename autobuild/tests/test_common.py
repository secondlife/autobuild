#!/usr/bin/env python
#!/usr/bin/env python

import unittest
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

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()

