import pytest

from autobuild.scm.base import Semver


@pytest.mark.parametrize("input,want", [
    ("v1.0.0", "1.0.0"),
    ("v1", "1.0.0"),
    ("1", "1.0.0"),
    ("v1.0", "1.0.0"),
    ("v1.0.0+r0", "1.0.0+r0"),
    ("v1.0.0-alpha1", "1.0.0-alpha1"),
    ("v1.0.0-alpha1+001", "1.0.0-alpha1+001"),
    ("v1.0.0-", "1.0.0"),
    ("hotdog", "None"),
])
def test_semver(input, want):
    assert str(Semver.parse(input)) == want


@pytest.mark.parametrize("input,want", [
    ("v1.0.0", "1.0.1"),
    ("v1.0.0-", "1.0.1"),
    ("v1.0.0-alpha1", "1.0.0"),
])
def test_semver_next(input, want):
    assert str(Semver.parse(input).next) == want
