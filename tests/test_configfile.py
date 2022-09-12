from autobuild import configfile
from autobuild.executable import Executable
from tests.baseline_compare import AutobuildBaselineCompare
from tests.basetest import BaseTest


class TestConfigFile(BaseTest, AutobuildBaselineCompare):

    def setUp(self):
        BaseTest.setUp(self)

    def fake_config(self):
        tmp_file = self.get_tmp_file()
        config = configfile.ConfigurationDescription(tmp_file)
        package = configfile.PackageDescription('test')
        config.package_description = package
        platform = configfile.PlatformDescription()
        platform.build_directory = '.'
        build_cmd = Executable(command="gcc", options=['-wall'])
        build_configuration = configfile.BuildConfigurationDescription()
        build_configuration.build = build_cmd
        platform.configurations['common'] = build_configuration
        config.package_description.platforms['common'] = platform
        return config

    def test_configuration_simple(self):
        config = self.fake_config()
        config.save()

        reloaded = configfile.ConfigurationDescription(config.path)
        assert reloaded.package_description.platforms['common'].build_directory == '.'
        assert reloaded.package_description.platforms['common'].configurations['common'].build.get_command() == 'gcc'

    def test_configuration_inherit(self):
        tmp_file = self.get_tmp_file()
        config = configfile.ConfigurationDescription(tmp_file)
        package = configfile.PackageDescription('test')
        config.package_description = package

        common_platform = configfile.PlatformDescription()
        common_platform.build_directory = 'common_build'
        common_cmd = Executable(command="gcc", options=['-wall'])
        common_configuration = configfile.BuildConfigurationDescription()
        common_configuration.build = common_cmd
        common_platform.configurations['common'] = common_configuration
        config.package_description.platforms['common'] = common_platform

        darwin_platform = configfile.PlatformDescription()
        darwin_platform.build_directory = 'darwin_build'
        darwin_cmd = Executable(command="clang", options=['-wall'])
        darwin_configuration = configfile.BuildConfigurationDescription()
        darwin_configuration.build = darwin_cmd
        darwin_platform.configurations['darwin'] = darwin_configuration
        config.package_description.platforms['darwin'] = darwin_platform

        config.save()

        reloaded = configfile.ConfigurationDescription(tmp_file)
        assert reloaded.get_platform('common').build_directory == 'common_build'
        assert reloaded.get_platform('darwin').build_directory == 'darwin_build'
        # check that we fall back to the 32 bit version if no 64 bit is found
        assert reloaded.get_platform('darwin64').build_directory == 'darwin_build'

    def test_configuration_save_expanded(self):
        config = self.fake_config()
        # pretend to expand variables -- doesn't matter that there are no
        # $variables in config, or that we don't pass any variables anyway
        config.expand_platform_vars({})
        with self.assertRaises(configfile.ConfigurationError):
            # We definitely do NOT want to resave any ConfigurationDescription
            # whose $variables have been expanded!
            config.save()

    def tearDown(self):
        self.cleanup_tmp_file()
        BaseTest.tearDown(self)

class TestExpandVars(BaseTest):
    def setUp(self):
        self.vars = dict(one="1", two="2", three="3")

    def test_expand_vars_string(self):
        # no substitutions should return string unchanged
        self.assertEqual(configfile._expand_vars_string("no subs", self.vars), "no subs")
        # simple substitutions handled by string.Template
        self.assertEqual(configfile._expand_vars_string("'$one', '${two}'", self.vars),
                          "'1', '2'")

        # string.Template bad syntax
        with self.assertRaises(configfile.ConfigurationError) as ctx:
            configfile._expand_vars_string("$-", self.vars)
        assert "$-" in str(ctx.exception)

        # string.Template undefined variable
        with self.assertRaises(configfile.ConfigurationError) as ctx:
            configfile._expand_vars_string("$four", self.vars)
        assert "undefined" in str(ctx.exception)
        assert "four" in str(ctx.exception)

        # extended ${var|fallback} syntax

        # bad syntax isn't recognized by our regexp, falls through to Template
        # error
        with self.assertRaises(configfile.ConfigurationError) as ctx:
            configfile._expand_vars_string("abc ${jjfjfj|xxxx", self.vars)
        assert "${jjfjfj" in str(ctx.exception)

        # defined variable expands to variable's value
        self.assertEqual(configfile._expand_vars_string("abc${one|fallback}def", self.vars),
                          "abc1def")

        # undefined expands to fallback
        self.assertEqual(configfile._expand_vars_string("abc${four|fallback}def", self.vars),
                          "abcfallbackdef")

        # multiple instances
        self.assertEqual(
            configfile._expand_vars_string(
                "abc_${one|nope}_def_${four|nofour}_ghi_${five|}_jkl",
                self.vars),
            "abc_1_def_nofour_ghi__jkl")

    def test_expand_vars(self):
        testdict = dict(
            f=1.0,
            i=17,
            t=(0, "$one", 2),
            l=["$three", 4, 5],
            d={"$one": "$one",
               "four" : {"four": "${four|4}"},
              },
            )

        expanded = configfile.expand_vars(testdict, self.vars)

        # should not have messed with testdict
        self.assertEqual(testdict["t"][1], "$one")
        self.assertEqual(testdict["l"][0], "$three")
        self.assertEqual(testdict["d"]["$one"], "$one")
        self.assertEqual(testdict["d"]["four"]["four"], "${four|4}")

        # expanded should have embedded strings expanded
        self.assertEqual(
            expanded,
            dict(
                f=1.0,
                i=17,
                t=(0, "1", 2),
                l=["3", 4, 5],
                d={"$one": "1",
                   "four" : {"four": "4"},
                  },
            ))
