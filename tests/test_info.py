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

from unittest import mock

from pibootctl.info import *


def test_get_board_revision():
    with mock.patch('io.open', mock.mock_open(read_data=b'\x00\xa0\x20\xd3')) as m:
        assert get_board_revision() == 0xa020d3
    with mock.patch('io.open') as m:
        m.side_effect = FileNotFoundError
        assert get_board_revision() == -1


def test_get_board_serial():
    with mock.patch(
            'io.open',
            mock.mock_open(read_data=b'\x00\x00\x00\x00\x12\x34\x56\x78')) as m:
        assert get_board_serial() == 0x12345678
    with mock.patch('io.open') as m:
        m.side_effect = FileNotFoundError
        assert get_board_serial() == -1


def test_get_board_types():
    with mock.patch('io.open', mock.mock_open(read_data=b'\x00\xa0\x20\xd3')) as m:
        assert get_board_types() == {'pi3', 'pi3+'}
    # TODO Check the size of linux,revision on a pi1 (might be 2 bytes?)
    with mock.patch('io.open', mock.mock_open(read_data=b'\x00\x00\x00\x0d')) as m:
        assert get_board_types() == {'pi1'}
    with mock.patch('io.open') as m:
        m.side_effect = FileNotFoundError
        assert get_board_types() == set()


def test_get_board_mem():
    with mock.patch('io.open', mock.mock_open(read_data=b'\x00\xa0\x20\xd3')) as m:
        assert get_board_mem() == 1024
    # TODO Again, check size of linux,revision
    with mock.patch('io.open', mock.mock_open(read_data=b'\x00\x00\x00\x0d')) as m:
        assert get_board_mem() == 512
    with mock.patch('io.open') as m:
        m.side_effect = FileNotFoundError
        assert get_board_mem() == 0
