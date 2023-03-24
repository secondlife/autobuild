"""Utilities for detecting file types"""

class ArchiveType:
    GZ = "gz"
    BZ2 = "bz2"
    ZIP = "zip"
    ZST = "zst"


# File signatures used for sniffing archive type
# https://www.garykessler.net/library/file_sigs.html
_ARCHIVE_MAGIC_NUMBERS = {
    b"\x1f\x8b\x08": ArchiveType.GZ,
    b"\x42\x5a\x68": ArchiveType.BZ2,
    b"\x50\x4b\x03\x04": ArchiveType.ZIP,
    b"\x28\xb5\x2f\xfd": ArchiveType.ZST,
}

_ARCHIVE_MAGIC_NUMBERS_MAX = max(len(x) for x in _ARCHIVE_MAGIC_NUMBERS)


def _archive_type_from_signature(filename: str):
    """Sniff archive type using file signature"""
    with open(filename, "rb") as f:
        head = f.read(_ARCHIVE_MAGIC_NUMBERS_MAX)
        for magic, f_type in _ARCHIVE_MAGIC_NUMBERS.items():
            if head.startswith(magic):
                return f_type 
    return None


def _archive_type_from_extension(filename: str):
    if filename.endswith(".tar.gz"):
        return ArchiveType.GZ
    if filename.endswith(".tar.bz2"):
        return ArchiveType.BZ2
    if filename.endswith(".tar.zst"):
        return ArchiveType.ZST
    if filename.endswith(".zip"):
        return ArchiveType.ZIP
    return None


def detect_archive_type(filename: str):
    """Given a filename, detect its ArchiveType using file extension and signature."""
    f_type = _archive_type_from_extension(filename)
    if f_type:
        return f_type
    return _archive_type_from_signature(filename)
