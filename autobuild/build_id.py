import logging
import os
import time

from autobuild.configfile import ConfigurationDescription
from autobuild.scm import git

logger = logging.getLogger(__name__)


def establish_build_id(build_id_arg, config: ConfigurationDescription):
    """determine and return a build_id based on (in preference order):
       the --id argument,
       the AUTOBUILD_BUILD_ID environment variable,
       the autodiscovered SCM version (if config has use_scm_version enabled)
       the date/time
    If we reach the date fallback, a warning is logged
    In addition to returning the id value, this sets the AUTOBUILD_BUILD_ID environment
    variable for any descendent processes so that recursive invocations will have access
    to the same value.
    """
    build_id = build_id_arg or get_build_id(config)
    logger.debug("Build id %s" % build_id)
    os.environ['AUTOBUILD_BUILD_ID'] = str(build_id)
    return build_id


def get_build_id(config: "ConfigurationDescription") -> str:
    if 'AUTOBUILD_BUILD_ID' in os.environ:
        return os.environ['AUTOBUILD_BUILD_ID']

    if config.package_description.use_scm_version:
        config_dir = os.path.dirname(config.path)
        build_id = git.get_version(config_dir)
        if build_id:
            logger.warning("Warning: no --id argument or AUTOBUILD_BUILD_ID environment variable specified;\n    using SCM version (%s), which may not be unique" % build_id)
            return build_id

    # construct a timestamp that will fit into a signed 32 bit integer:
    #   <two digit year><three digit day of year><two digit hour><two digit minute>

    build_id = time.strftime("%y%j%H%M", time.gmtime())
    logger.warning("Warning: no --id argument or AUTOBUILD_BUILD_ID environment variable specified;\n    using a value from the UTC date and time (%s), which may not be unique" % build_id)
    return build_id
