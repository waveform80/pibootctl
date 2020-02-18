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
        rev = get_board_revision()
        if rev & 0x800000:
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
            }[rev >> 4 & 0xff]
        else:
            # All old-style revs are pi1 models (A, B, A+, B+, CM1)
            return {'pi1'}
    except:
        return set()


def get_board_mem():
    # See get_board_types for source data locations
    try:
        rev = get_board_revision()
        if rev & 0x800000:
            return {
                0: 256,
                1: 512,
                2: 1024,
                3: 2048,
                4: 4096,
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
    except:
        return 0
