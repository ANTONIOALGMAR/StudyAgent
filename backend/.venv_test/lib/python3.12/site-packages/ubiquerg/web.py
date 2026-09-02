"""Web-related utilities"""

import re

__all__ = ["is_url", "has_scheme"]

# from Django 1.3.x
# https://github.com/django/django/blob/6726d750979a7c29e0dd866b4ea367eef7c8a420/django/core/validators.py#L45-L51
_URL_REGEX = re.compile(
    r"^(?:http|ftp)s?://"
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"
    r"localhost|"
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    r"(?::\d+)?"
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)

_SCHEME_REGEX = re.compile(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://")


def has_scheme(maybe_url: str) -> bool:
    """Check whether a string starts with a URI scheme (e.g. s3://, gs://, file://).

    Args:
        maybe_url: string to check

    Returns:
        bool: whether string starts with a URI scheme
    """
    return _SCHEME_REGEX.match(str(maybe_url)) is not None


def is_url(maybe_url: str) -> bool:
    """Determine whether a path is a URL.

    Args:
        maybe_url: path to investigate as URL

    Returns:
        bool: whether path appears to be a URL
    """
    return _URL_REGEX.match(str(maybe_url)) is not None
