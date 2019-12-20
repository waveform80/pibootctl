from unittest import mock

from pictl.info import *


def test_get_board_revision():
    with mock.patch('io.open', mock.mock_open(read_data=b'\x00\xa0\x20\xd3')) as m:
        assert get_board_revision() == 0xa020d3
    with mock.patch('io.open') as m:
        m.side_effect = FileNotFoundError
        assert get_board_revision() == 0


def test_get_board_serial():
    with mock.patch(
            'io.open',
            mock.mock_open(read_data=b'\x00\x00\x00\x00\x12\x34\x56\x78')) as m:
        assert get_board_serial() == 0x12345678
    with mock.patch('io.open') as m:
        m.side_effect = FileNotFoundError
        assert get_board_serial() == 0


def test_get_board_types():
    with mock.patch('io.open', mock.mock_open(read_data=b'\x00\xa0\x20\xd3')) as m:
        assert get_board_types() == {'pi3', 'pi3+'}
    with mock.patch('io.open') as m:
        m.side_effect = FileNotFoundError
        assert get_board_types() == set()
