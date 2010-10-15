#!/usr/bin/python
"""\
@file   hash_algorithms.py
@author Nat Goodspeed
@date   2010-10-13
@brief  Implementations for various values of configfile.ArchiveDescription.hash_algorithm

$LicenseInfo:firstyear=2010&license=mit$
Copyright (c) 2010, Linden Research, Inc.
$/LicenseInfo$
"""

import common
from common import AutobuildError

def verify_hash(hash_algorithm, pathname, hash):
    if not hash:
        # If there's no specified hash value, what can we do? We could
        # unconditionally fail, but that risks getting the user stuck. So
        # -- if there's no specified hash value, unconditionally accept
        # the download.
        print "Warning: unable to verify %s; expected hash value not specified" % pathname
        return True

    if not hash_algorithm:
        # Historical: if there IS a hash value, but no hash_algorithm,
        # assume MD5 because that used to be the only supported hash
        # algorithm. There may be files out there that don't specify.
        hash_algorithm = "md5"

    try:
        function = globals()["_verify_" + hash_algorithm]
    except KeyError:
        raise AutobuildError("Unsupported hash type %s for %s" %
                             (hash_algorithm, pathname))

    # Apparently we do have a function to support this hash_algorithm. Call
    # it.
    return function(pathname, hash)

def _verify_md5(pathname, hash):
    return common.compute_md5(pathname) == hash
