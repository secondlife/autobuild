"""
Implementations for various values of configfile.ArchiveDescription.hash_algorithm
"""
from autobuild import common
from autobuild.common import AutobuildError

# Valid configfile.ArchiveDescription.hash_algorithm values are registered
# here by means of the @hash_algorithm decorator.
REGISTERED_ALGORITHMS = {}


class hash_algorithm(object):
    """
    This decorator is used to register each supported hash algorithm in
    REGISTERED_ALGORITHMS using syntax like:

    @hash_algorithm("md5")
    def _verify_md5(self, pathname, hash):
        ...
    """
    # called when we instantiate @hash_algorithm("md5")
    def __init__(self, key):
        self.key = key

    # called when this decorator is applied to an implementation function
    def __call__(self, func):
        global REGISTERED_ALGORITHMS
        # Register the decorated function with the specified key.
        REGISTERED_ALGORITHMS[self.key] = func
        # Unlike many decorators, we don't want to wrap the passed function in
        # any way; just return the same function.
        return func


def verify_hash(hash_algorithm, pathname, hash):
    """
    Primary entry point for this module
    """
    if not hash:
        # If there's no specified hash value, what can we do? We could
        # unconditionally fail, but that risks getting the user stuck. So
        # -- if there's no specified hash value, unconditionally accept
        # the download.
        print("Warning: unable to verify %s; expected hash value not specified" % pathname)
        return True

    if not hash_algorithm:
        # Historical: if there IS a hash value, but no hash_algorithm,
        # assume MD5 because that used to be the only supported hash
        # algorithm. There may be files out there that don't specify.
        hash_algorithm = "md5"

    try:
        function = REGISTERED_ALGORITHMS[hash_algorithm]
    except KeyError:
        raise AutobuildError("Unsupported hash type %s for %s" %
                             (hash_algorithm, pathname))

    # Apparently we do have a function to support this hash_algorithm. Call
    # it.
    return function(pathname, hash)


@hash_algorithm("md5")
def verify_md5(pathname, hash):
    return common.compute_md5(pathname) == hash


@hash_algorithm("blake2b")
def verify_blake2b(pathname, hash):
    return common.compute_blake2b(pathname) == hash


@hash_algorithm("sha1")
def verify_sha1(pathname, hash):
    return common.compute_sha1(pathname) == hash


@hash_algorithm("sha256")
def verify_sha256(pathname, hash):
    return common.compute_sha256(pathname) == hash
