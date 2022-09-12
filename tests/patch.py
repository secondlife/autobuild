import contextlib


@contextlib.contextmanager
def patch(module, attribute, value):
    """
    Usage:

    # assert configfile.AUTOBUILD_CONFIG_VERSION == "1.3"
    with patch(configfile, "AUTOBUILD_CONFIG_VERSION", "1.5"):
        # assert configfile.AUTOBUILD_CONFIG_VERSION == "1.5"
        # ...
    # assert configfile.AUTOBUILD_CONFIG_VERSION == "1.3" again
    """
    try:
        # what's the current value of the attribute?
        saved = getattr(module, attribute)
    except AttributeError:
        # doesn't exist, we're adding it, so delete it later
        restore = lambda: delattr(module, attribute)
    else:
        # 'saved' is prev value, so reset to 'saved' later
        restore = lambda: setattr(module, attribute, saved)

    try:
        # set the desired module attribute
        setattr(module, attribute, value)
        # run body of 'with' block
        yield
    finally:
        # no matter how we leave, restore to previous state
        restore()
