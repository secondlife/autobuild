import os
import time
from unittest.mock import MagicMock, patch

from autobuild.build_id import establish_build_id, get_build_id
from autobuild.configfile import ConfigurationDescription, PackageDescription
from tests.basetest import chdir, envvar, git_repo, temp_dir


def mock_config(path: str) -> ConfigurationDescription:
    """Build a basic ConfigurationDescription"""
    config = ConfigurationDescription(path)
    config.package_description = PackageDescription("test-package")
    config.package_description.use_scm_version = False
    return config


@patch("time.gmtime")
def test_get_build_id(mock_gmtime: MagicMock):
    ts = time.struct_time([2022, 9, 3, 0, 0, 0, 5, 246, 0])
    want_build_id = "222460000"
    mock_gmtime.return_value = ts

    # Create a git repo to test SCM behavior
    with git_repo() as git_root, envvar("AUTOBUILD_BUILD_ID", None):
        # Check that default behavior is to use gmtime unless
        # config.package_description.use_scm_version = True
        config = mock_config(os.path.join(git_root, "autobuild.xml"))
        build_id = get_build_id(config)
        assert build_id == want_build_id

        # Now test that SCM version is used if AUTOBUILD_SCM=yes
        config.package_description.use_scm_version = True
        build_id = get_build_id(config)
        assert build_id == "1.0.0"

    # Make a clean temp directory to ensure we are not in a git checkout location
    with temp_dir() as dir, chdir(dir), envvar("AUTOBUILD_BUILD_ID", None):
        config = mock_config(os.path.join(dir, "autobuild.xml"))
        build_id = get_build_id(config)
        assert build_id == want_build_id

    # Finally, check that the AUTOBUILD_BUILD_ID is used by default
    with temp_dir() as dir, chdir(dir), envvar("AUTOBUILD_BUILD_ID", "50000"):
        config = mock_config(os.path.join(dir, "autobuild.xml"))
        build_id = get_build_id(config)
        assert build_id == "50000"


def test_establish_build_id():
    with temp_dir() as dir, envvar("AUTOBUILD_BUILD_ID", None):
        config = mock_config(os.path.join(dir, "autobuild.xml"))
        build_id = establish_build_id("50000", config)
        assert build_id == "50000"
        assert os.environ.get("AUTOBUILD_BUILD_ID") == "50000", "Expected establish_build_id to set AUTOBUILD_BUILD_ID"
