"""Environment-related utilities"""

import os
from types import TracebackType

__author__ = "Vince Reuter"
__email__ = "vreuter@virginia.edu"

__all__ = ["TmpEnv"]


class TmpEnv(object):
    """Temporary environment variable setting."""

    def __init__(self, overwrite: bool = False, **kwargs: str) -> None:
        if not overwrite:
            already_set = [k for k, v in kwargs.items() if os.getenv(k, v) != v]
            if already_set:
                msg = "{} variable(s) already set: {}".format(
                    len(already_set), ", ".join(already_set)
                )
                raise ValueError(msg)
        self._kvs = kwargs
        self._originals = {}
        for k in kwargs:
            if k in os.environ:
                self._originals[k] = os.environ[k]

    def __enter__(self) -> "TmpEnv":
        for k, v in self._kvs.items():
            os.environ[k] = v
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        for k in self._kvs:
            if k in self._originals:
                os.environ[k] = self._originals[k]
            else:
                try:
                    del os.environ[k]
                except KeyError:
                    pass
