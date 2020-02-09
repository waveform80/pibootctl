import io
import os
import shlex
import errno
import struct


def _hexdump(filename, fmt='>L'):
    try:
        size = struct.calcsize(fmt)
        with io.open(filename, 'rb') as f:
            return struct.unpack(fmt, f.read(size))[0]
    except FileNotFoundError:
        return -1


def get_board_revision():
    return _hexdump('/proc/device-tree/system/linux,revision')


def get_board_serial():
    return _hexdump('/proc/device-tree/system/linux,serial', '>Q')


def get_board_types():
    # Derived (excluding unsupported types) from the table at:
    # https://www.raspberrypi.org/documentation/hardware/raspberrypi/revision-codes/README.md
    # And from the filters listed under:
    # https://www.raspberrypi.org/documentation/configuration/config-txt/conditional.md
    try:
        return {
            0x0:  {'pi1'},
            0x1:  {'pi1'},
            0x2:  {'pi1'},
            0x3:  {'pi1'},
            0x4:  {'pi2'},
            0x5:  {'pi1'},
            0x6:  {'pi1'},
            0x8:  {'pi3'},
            0x9:  {'pi0'},
            0xa:  {'pi3'},
            0xc:  {'pi0', 'pi0w'},
            0xd:  {'pi3', 'pi3+'},
            0xe:  {'pi3', 'pi3+'},
            0x10: {'pi3', 'pi3+'},
            0x11: {'pi4'},
        }[get_board_revision() >> 4 & 0xff]
    except:
        return set()
