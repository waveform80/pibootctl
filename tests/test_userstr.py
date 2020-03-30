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

import pytest

from pibootctl.userstr import *


def test_to_bool():
    assert to_bool(None) is None
    assert to_bool('') is False
    assert to_bool('1') is True
    assert to_bool('0') is True
    assert to_bool(UserStr('')) is None
    assert to_bool(UserStr('1')) is True
    assert to_bool(UserStr('YES')) is True
    assert to_bool(UserStr(' true ')) is True
    assert to_bool(UserStr(' 0')) is False
    assert to_bool(UserStr('n')) is False
    assert to_bool(UserStr('false ')) is False
    assert to_bool(UserStr(' ')) is None
    with pytest.raises(ValueError):
        to_bool(UserStr('foo'))


def test_to_int():
    assert to_int(None) is None
    assert to_int(1) == 1
    assert to_int('1') == 1
    assert to_int('  10001') == 10001
    assert to_int(3.0) == 3
    assert to_int(UserStr('')) is None
    assert to_int(UserStr('1')) == 1
    assert to_int(UserStr('  10001 ')) == 10001
    assert to_int(UserStr(' 0XA')) == 0xa
    assert to_int(UserStr('0xd00dfeed ')) == 0xd00dfeed
    with pytest.raises(ValueError):
        to_int(UserStr('d00dfeed'))
    with pytest.raises(ValueError):
        to_int(UserStr(' foo'))
    with pytest.raises(ValueError):
        to_int(UserStr('0o644'))


def test_to_float():
    assert to_float(None) is None
    assert to_float(1) == 1.0
    assert to_float(1.5) == 1.5
    assert to_float('1.5') == 1.5
    assert to_float('  1e4') == 10000.0
    assert to_float(UserStr('')) is None
    assert to_float(UserStr('1.5')) == 1.5
    assert to_float(UserStr('  1e4 ')) == 10000.0
    with pytest.raises(ValueError):
        to_float(UserStr('0x10'))
    with pytest.raises(ValueError):
        to_float(UserStr(' foo'))
    with pytest.raises(ValueError):
        to_float(UserStr('0o644'))


def test_to_str():
    assert to_str(None) is None
    assert to_str('') == ''
    assert to_str('foo') == 'foo'
    assert to_str('  foo') == '  foo'
    assert to_str(1) == '1'
    assert to_str(UserStr('')) is None
    assert to_str(UserStr(' ')) == ''
    assert to_str(UserStr('  foo')) == 'foo'


def test_to_list():
    assert to_list(None) is None
    assert to_list('') == ['']
    assert to_list([]) == []
    assert to_list('foo') == ['foo']
    assert to_list('foo,bar') == ['foo', 'bar']
    assert to_list(UserStr('')) is None
    assert to_list(UserStr(' ')) == ['']
    assert to_list(UserStr('  foo')) == ['foo']
    assert to_list(UserStr('foo,bar')) == ['foo', 'bar']
