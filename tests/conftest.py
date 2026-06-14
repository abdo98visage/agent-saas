import builtins
import os


_real_open = builtins.open


def _utf8_open(file, mode="r", *args, **kwargs):
    if "b" not in mode and "encoding" not in kwargs:
        try:
            path = os.fspath(file)
        except TypeError:
            path = None
        if isinstance(path, str) and path.endswith(".html"):
            kwargs["encoding"] = "utf-8"
    return _real_open(file, mode, *args, **kwargs)


builtins.open = _utf8_open
