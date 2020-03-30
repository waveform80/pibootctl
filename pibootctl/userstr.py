# Copyright (c) 2020 Canonical Ltd.
# Copyright (c) 2020 Dave Jones <dave@waveform.org.uk>
#
# This file is part of pibootctl.
#
# pibootctl is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pibootctl is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pibootctl.  If not, see <https://www.gnu.org/licenses/>.

"""
The :mod:`pibootctl.userstr` module provides the :class:`UserStr` class which
represents unparsed user input on the command line.

The module also provides a variety of functions for converting input (either
from JSON, YAML, or other structured formats, or from unparsed
:class:`UserStr`) into common types (:func:`to_bool`, :func:`to_int`,
:func:`to_str`, etc).

.. autoclass:: UserStr

.. autofunction:: to_bool

.. autofunction:: to_int

.. autofunction:: to_float

.. autofunction:: to_str

.. autofunction:: to_list
"""

import gettext

_ = gettext.gettext


class UserStr(str):
    """
    Type used to represent a value expressed as a string on the command line.
    In other words, any value bearing this type is a string representation of
    some other type (possibly :class:`str`, :class:`int`, :data:`None`, etc.)

    Primarily used by various conversion routines (:func:`to_bool`,
    :func:`to_str`, etc.) to determine whether a value is a string parsed from
    some serialization format (like JSON or YAML) which should be treated as a
    string literal.

    .. note::

        The blank :class:`UserStr` is special in that it *always* represents
        :data:`None` in conversions.
    """


def to_bool(s):
    """
    Converts the :class:`UserStr` (or other type) *s* to a :class:`bool`.
    Various "typical" string representations of true and false are accepted
    including "true", "yes", and "on", along with their counter-parts "false",
    "no", and "off". Literal :data:`None` passes through unchanged, and a blank
    :class:`UserStr` will convert to :data:`None`.
    """
    if s is None:
        return None
    elif isinstance(s, UserStr):
        try:
            return {
                '':      None,
                'auto':  None,
                'true':  True,
                'yes':   True,
                'on':    True,
                '1':     True,
                'y':     True,
                'false': False,
                'no':    False,
                'off':   False,
                '0':     False,
                'n':     False,
            }[s.strip().lower()]
        except KeyError:
            raise ValueError(
                _('{value} is not a valid bool').format(value=s))
    return bool(s)


def to_int(s):
    """
    Converts the :class:`UserStr` (or other type) *s* to a :class:`int`. As
    with all :class:`UserStr` conversions, blank string inputs are converted to
    :data:`None`, and literal :data:`None` passes through unchanged. Otherwise,
    decimal integers and hexi-decimal integers prefixed with "0x" are accepted.
    """
    if s is None:
        return None
    elif isinstance(s, str):
        if isinstance(s, UserStr):
            if not s:
                return None
        s = s.strip().lower()
        if s[:2] == '0x':
            return int(s, base=16)
    return int(s)


def to_float(s):
    """
    Converts the :class:`UserStr` (or other type) *s* to a :class:`float`. As
    with all :class:`UserStr` conversions, blank string inputs are converted to
    :data:`None`, and literal :data:`None` passes through unchanged. Otherwise,
    typical floating point values (optionally prefixed with sign, optionally
    suffixed with an exponent) are accepted.
    """
    if s is None:
        return None
    elif isinstance(s, str):
        if isinstance(s, UserStr):
            if not s:
                return None
    return float(s)


def to_str(s):
    """
    Converts the :class:`UserStr` (or other type) *s* to a :class:`str`. Blank
    :class:`UserStr` are converted to :data:`None`, and literal :data:`None`
    passes through unchanged. Everything else is simply passed to the
    :class:`str` constructor.
    """
    if s is None:
        return None
    elif isinstance(s, UserStr):
        if not s:
            return None
        else:
            return s.strip()
    return str(s)


def to_list(s, sep=','):
    """
    Converts the :class:`UserStr` (or other type) *s* to a :class:`list` based
    on the separator character *sep* (which defaults to ","). Blank
    :class:`UserStr` are converted to :data:`None`, and literal :data:`None`
    passes through unchanged. Everything else is passed to the :class:`list`
    constructor. This ensures that the result is always a unique reference.
    """
    if s is None:
        return None
    elif isinstance(s, UserStr):
        if not s:
            return None
        else:
            s = s.strip()
    if isinstance(s, str):
        if sep in s:
            return [elem.strip() for elem in s.split(sep)]
        else:
            return [s]
    return list(s)
