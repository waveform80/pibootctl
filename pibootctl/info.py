# Copyright (c) 2020 Canonical Ltd.
# Copyright (c) 2019, 2020 Dave Jones <dave@waveform.org.uk>
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
The :mod:`pibootctl.info` module contains some simple routines for determining
information about the Pi that the application is running on.

.. autofunction:: get_board_revision

.. autofunction:: get_board_serial

.. autofunction:: get_board_type

.. autofunction:: get_board_types

.. autofunction:: get_board_mem
"""

import io
import struct


def _hexdump(filename, fmt='>L'):
    try:
        size = struct.calcsize(fmt)
        with io.open(filename, 'rb') as f:
            return struct.unpack(fmt, f.read(size))[0]
    except FileNotFoundError:
        return -1


def get_board_revision():
    """
    Return the Pi's board revision as an unsigned 32-bit integer number. This
    is the same number as reported under "Revision" in :file:`/proc/cpuinfo`.
    """
    return _hexdump('/proc/device-tree/system/linux,revision')


def get_board_serial():
    """
    Return the Pi's serial number as an unsigned 64-bit integer number. This
    can also be queried as "Serial" under :file:`/proc/cpuinfo`.
    """
    return _hexdump('/proc/device-tree/system/linux,serial', '>Q')


def get_board_type():
    """
    Return a string indicating the overall model of the Pi, e.g. "pi0w", "pi2",
    or "pi3+". This is derived from the result of :func:`get_board_revision`
    according to the Pi's `revision codes table`_.

    .. _revision codes table:
       https://www.raspberrypi.org/documentation/hardware/raspberrypi/revision-codes/README.md
    """
    try:
        rev = get_board_revision()
        if rev & 0x800000:
            return {
                0x0:  'pi1',
                0x1:  'pi1',
                0x2:  'pi1',
                0x3:  'pi1',
                0x4:  'pi2',
                0x5:  'pi1',
                0x6:  'pi1',
                0x8:  'pi3',
                0x9:  'pi0',
                0xa:  'pi3',
                0xc:  'pi0w',
                0xd:  'pi3+',
                0xe:  'pi3+',
                0x10: 'pi3+',
                0x11: 'pi4',
            }[rev >> 4 & 0xff]
        else:
            # All old-style revs are pi1 models (A, B, A+, B+, CM1)
            return 'pi1'
    except KeyError:
        return None


def get_board_types():
    """
    Return a set of strings used for matching the model of Pi against
    configuration sections according to the `conditional filters table`_.

    .. _conditional filters table:
       https://www.raspberrypi.org/documentation/configuration/config-txt/conditional.md
    """
    return {
        None:  set(),
        'pi0':  {'pi0'},
        'pi0w': {'pi0', 'pi0w'},
        'pi1':  {'pi1'},
        'pi2':  {'pi2'},
        'pi3':  {'pi3'},
        'pi3+': {'pi3', 'pi3+'},
        'pi4':  {'pi4'},
    }[get_board_type()]


def get_board_mem():
    """
    Return the amount of memory (in megabytes) present on the Pi, according to
    the model returned by :func:`get_board_revision`.
    """
    try:
        rev = get_board_revision()
        if rev & 0x800000:
            return {
                0: 256,
                1: 512,
                2: 1024,
                3: 2048,
                4: 4096,
                5: 8192,
            }[rev >> 20 & 0x7]
        else:
            return {
                0x0002: 256,
                0x0003: 256,
                0x0004: 256,
                0x0005: 256,
                0x0006: 256,
                0x0007: 256,
                0x0008: 256,
                0x0009: 256,
                0x0012: 256,
                0x0015: 256, # sometimes 512
                0x000d: 512,
                0x000e: 512,
                0x000f: 512,
                0x0010: 512,
                0x0011: 512,
                0x0013: 512,
                0x0014: 512,
            }[rev]
    except KeyError:
        return 0


def get_display_id(display=None):
    raise NotImplementedError
