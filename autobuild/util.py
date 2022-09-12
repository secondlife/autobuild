import os
import subprocess


def is_env_disabled(key: str) -> bool:
    """Check whether an envvar has an explicit falsey value. Useful for opt-out behavior."""
    return os.environ.get(key, "true").lower() in {"false", "0", "f", "no"}


def is_env_enabled(key: str) -> bool:
    """Check whether an envvar has an explicit truthy value. Useful for opt-in behavior."""
    return os.environ.get(key, "false").lower() in {"true", "1", "t", "yes"}


def cmd(*cmd, **kwargs) -> subprocess.CompletedProcess[str]:
    """Shorthand subprocess.run"""
    p = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, text=True, **kwargs)
    p.stdout = p.stdout.rstrip("\n")
    return p


def has_cmd(name) -> bool:
    """Check whether an executable exists by attempting to run its 'help' subcommand"""
    try:
        p = cmd(name, "help")
    except OSError:
        return False
    return not p.returncode
