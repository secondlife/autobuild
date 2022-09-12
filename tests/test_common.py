from autobuild import common
from tests.basetest import BaseTest


class TestCommon(BaseTest):
    def setUp(self):
        BaseTest.setUp(self)

    def test_find_executable(self):
        shell = "sh"
        if common.get_current_platform() == common.PLATFORM_WINDOWS:
            shell = "cmd"

        exe_path = common.find_executable(shell)
        assert exe_path != None

    def tearDown(self):
        BaseTest.tearDown(self)
