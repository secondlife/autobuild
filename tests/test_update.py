from unittest import TestCase

from autobuild import update
from tests.basetest import exc
from tests.patch import patch


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
        assert len(update._updaters["1.1"]) == 2

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
        self.assertEqual(len(triples), 1)
        self.assertEqual(triples[0][:2], ("1.3", "1.4"))

        # two versions older, need two updaters
        triples = update._get_applicable_updaters("NAME", "1.2")
        self.assertEqual(len(triples), 2)
        self.assertEqual(triples[0][:2], ("1.2", "1.3"))
        self.assertEqual(triples[1][:2], ("1.3", "1.4"))

        # three versions older, need three updaters
        triples = update._get_applicable_updaters("NAME", "1.1")
        self.assertEqual(len(triples), 3)
        self.assertEqual(triples[0][:2], ("1.1", "1.2"))
        self.assertEqual(triples[1][:2], ("1.2", "1.3"))
        self.assertEqual(triples[2][:2], ("1.3", "1.4"))

        # verify that the functions we registered are the ones we get back
        config = []
        for _, _, func in triples:
            config = func(config)
        self.assertEqual(config, ["to 1.2", "to 1.3", "to 1.4"])

        # way way old, so sorry
        with exc(update.UpdateError):
            triples = update._get_applicable_updaters("NAME", "1.0")

        # introduce a shortcut converter from 1.2 to 1.4
        update._register("1.2", "1.4", lambda config: config + ["jump 1.4"])

        # conversion from 1.2 should now always take the shortcut
        triples = update._get_applicable_updaters("NAME", "1.1")
        self.assertEqual(len(triples), 2)
        self.assertEqual(triples[0][:2], ("1.1", "1.2"))
        self.assertEqual(triples[1][:2], ("1.2", "1.4"))

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
        self.assertEqual(orig_ver, None)
        assert "track" not in config, "updater called on current config"

        # oldest supported config gets all updaters
        config, orig_ver = update.convert_to_current("NAME", dict(version="1.1"))
        self.assertEqual(orig_ver, "1.1")
        assert "track" in config, "updater not called on old config"
        self.assertEqual(config["track"], ["to 1.2", "to 1.3", "to 1.4"])
        self.assertEqual(config["version"], "1.4")
