import shutil
from os import path
from pathlib import Path
from tests.basetest import temp_dir

import pytest
from autobuild import archive_utils


_DATA_DIR = Path(__file__).parent / "data"

_ARCHIVE_TEST_CASES = (
    (path.join(_DATA_DIR, "archive.tar.bz2"), archive_utils.ArchiveType.BZ2),
    (path.join(_DATA_DIR, "archive.tar.gz"), archive_utils.ArchiveType.GZ),
    (path.join(_DATA_DIR, "archive.tar.zst"), archive_utils.ArchiveType.ZST),
    (path.join(_DATA_DIR, "archive.zip"), archive_utils.ArchiveType.ZIP),
)


@pytest.mark.parametrize("filename,expected_type", _ARCHIVE_TEST_CASES)
def test_detect_from_extension(filename, expected_type):
    f_type = archive_utils.detect_archive_type(filename)
    assert f_type == expected_type


@pytest.mark.parametrize("filename,expected_type", _ARCHIVE_TEST_CASES)
def test_detect_from_signature(filename, expected_type):
    with temp_dir() as dir:
        filename_no_ext = str(Path(dir) / "archive")
        shutil.copyfile(filename, filename_no_ext)
        f_type = archive_utils.detect_archive_type(filename_no_ext)
        assert f_type == expected_type
