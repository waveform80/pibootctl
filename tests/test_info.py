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
