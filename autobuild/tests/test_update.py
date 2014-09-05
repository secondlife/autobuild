#!/usr/bin/python
"""\
@file   test_update.py
@author Nat Goodspeed
@date   2014-09-05
@brief  Test the functionality of the update.py module.

$LicenseInfo:firstyear=2014&license=internal$
Copyright (c) 2014, Linden Research, Inc.
$/LicenseInfo$
"""

import re
from contextlib import contextmanager
from unittest import TestCase
from nose.tools import *                # assert_equals() et al.
from patch import patch

try:
    import update
except ImportError:
    import os
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
    import update

@contextmanager
def exc(exceptionslist, pattern=None):
    """
    Usage:

    # succeeds
    with exc(ValueError):
        int('abc')

    # fails with AssertionError
    with exc(ValueError):
        int('123')

    # can specify multiple expected exceptions
    with exc((IndexError, ValueError)):
        int(''[0])
    with exc((IndexError, ValueError)):
        int('a'[0])

    # can match expected message, when exception type isn't sufficient
    with exc(Exception, 'badness'):
        raise Exception('much badness has occurred')
    """
    try:
        # run the body of the with block
        yield
    except exceptionslist as err:
        # okay, with block did raise one of the expected exceptions;
        # did the caller need the exception message to match a pattern?
        if pattern and not re.search(pattern, str(err)):
            raise AssertionError("exception %s does not match '%s': '%s'" %
                                 (err.__class__.__name__, pattern, err))
    else:
        # with block did not raise any of the expected exceptions: FAIL
        try:
            # did caller pass a tuple of exceptions?
            iter(exceptionslist)
        except TypeError:
            # just one exception class: use its name
            exceptionnames = exceptionslist.__class__.__name__
        else:
            # tuple of exception classes: format their names
            exceptionnames = "any of (%s)" % \
                ','.join(ex.__class__.__name__ for ex in exceptionslist)
        raise AssertionError("with block did not raise " + exceptionnames)


def test_register():
    # We're going to mess with the registry of updaters; restore it when we're
    # done to avoid breaking other tests that rely on the real values.
    with patch(update, "_updaters", {}):
        update._register("1.1", "1.2", lambda config: config + ["to 1.2"])
        update._register("1.1", "1.3", lambda config: config + ["to 1.3"])
        update._register("1.2", "1.4", lambda config: config + ["to 1.4"])

        # directly examining _updaters is fragile; update.py maintenance may
        # require changing this test; but _register() has no other observable
        # side effects
        assert_equals(len(update._updaters["1.1"]), 2)

class TestUpdater(TestCase):
    def setUp(self):
        self.save_confver  = update.AUTOBUILD_CONFIG_VERSION
        self.save_updaters = update._updaters

        update.AUTOBUILD_CONFIG_VERSION = "1.4"

        update._updaters = {}

    def tearDown(self):
        update._updaters = self.save_updaters
        update.AUTOBUILD_CONFIG_VERSION = self.save_confver

    def test_applicable_normal(self):
        # This is the expected scenario: each updater bumps exactly one
        # version; we have an unbroken chain of updaters; the only variance is
        # in the version at which we start (version saved in the input file).
        update._register("1.1", "1.2", lambda config: config + ["to 1.2"])
        update._register("1.2", "1.3", lambda config: config + ["to 1.3"])
        update._register("1.3", "1.4", lambda config: config + ["to 1.4"])

        # already current
        triples = update._get_applicable_updaters("NAME", "1.4")
        assert not triples

        # one previous version, need one updater
        triples = update._get_applicable_updaters("NAME", "1.3")
        assert_equals(len(triples), 1)
        assert_equals(triples[0][:2], ("1.3", "1.4"))

        # two versions older, need two updaters
        triples = update._get_applicable_updaters("NAME", "1.2")
        assert_equals(len(triples), 2)
        assert_equals(triples[0][:2], ("1.2", "1.3"))
        assert_equals(triples[1][:2], ("1.3", "1.4"))

        # three versions older, need three updaters
        triples = update._get_applicable_updaters("NAME", "1.1")
        assert_equals(len(triples), 3)
        assert_equals(triples[0][:2], ("1.1", "1.2"))
        assert_equals(triples[1][:2], ("1.2", "1.3"))
        assert_equals(triples[2][:2], ("1.3", "1.4"))

        # verify that the functions we registered are the ones we get back
        config = []
        for _, _, func in triples:
            config = func(config)
        assert_equals(config, ["to 1.2", "to 1.3", "to 1.4"])

        # way way old, so sorry
        with exc(update.UpdateError):
            triples = update._get_applicable_updaters("NAME", "1.0")

        # introduce a shortcut converter from 1.2 to 1.4
        update._register("1.2", "1.4", lambda config: config + ["jump 1.4"])

        # conversion from 1.2 should now always take the shortcut
        triples = update._get_applicable_updaters("NAME", "1.1")
        assert_equals(len(triples), 2)
        assert_equals(triples[0][:2], ("1.1", "1.2"))
        assert_equals(triples[1][:2], ("1.2", "1.4"))

        # whoops, suddenly we're trying to reach a version for which we have
        # no updater
        update.AUTOBUILD_CONFIG_VERSION = "1.5"

        with exc(update.UpdateError):
            triples = update._get_applicable_updaters("NAME", "1.1")

    def test_applicable_loop(self):
        update._register("1.1", "1.2", lambda config: config + ["to 1.2"])
        update._register("1.2", "1.3", lambda config: config + ["to 1.3"])
        update._register("1.3", "1.1", lambda config: config + ["back to 1.1"])

        with exc(AssertionError, "loop"):
            triples = update._get_applicable_updaters("NAME", "1.1")

    def test_applicable_stuck(self):
        # This test constructs a chain of updaters that could be resolved by a
        # graph search, but which suffices to confuse our "always take
        # shortcuts" logic. If we ever introduce a graph search, we expect
        # this test to start failing because the call should start working.
        update._register("1.1", "1.2", lambda config: config + ["to 1.2"])
        update._register("1.1", "1.3", lambda config: config + ["to 1.3"])
        update._register("1.2", "1.4", lambda config: config + ["to 1.4"])

        with exc(update.UpdateError):
            triples = update._get_applicable_updaters("NAME", "1.1")

    # helper for test_convert: conversion method that updates config["track"]
    @staticmethod
    def track_config(config, breadcrumb):
        config.setdefault("track", []).append(breadcrumb)
        return config

    def test_convert(self):
        # normal type registry
        update._register("1.1", "1.2", lambda config: self.track_config(config, "to 1.2"))
        update._register("1.2", "1.3", lambda config: self.track_config(config, "to 1.3"))
        update._register("1.3", "1.4", lambda config: self.track_config(config, "to 1.4"))

        # config too old to even have a version key
        with exc(update.UpdateError):
            config, orig_ver = update.convert_to_current("NAME", {})

        # current config needs no update
        config, orig_ver = update.convert_to_current("NAME", dict(version="1.4"))
        assert_equals(orig_ver, None)
        assert "track" not in config, "updater called on current config"

        # oldest supported config gets all updaters
        config, orig_ver = update.convert_to_current("NAME", dict(version="1.1"))
        assert_equals(orig_ver, "1.1")
        assert "track" in config, "updater not called on old config"
        assert_equals(config["track"], ["to 1.2", "to 1.3", "to 1.4"])
        assert_equals(config["version"], "1.4")
