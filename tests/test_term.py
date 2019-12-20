import argparse
from unittest import mock

from pictl.term import *


def test_term_color():
    with mock.patch('os.isatty') as m:
        m.return_value = False
        assert not term_color()
        m.return_value = True
        assert term_color()
    with mock.patch('sys.stdout.fileno') as m:
        m.side_effect = OSError
        assert not term_color()


def test_term_size():
    with mock.patch('fcntl.ioctl') as ioctl:
        ioctl.side_effect = [
            OSError,
            b'B\x00\xf0\x00\x00\x00\x00\x00',
        ]
        assert term_size() == (240, 66)
        with mock.patch('os.ctermid') as ctermid, mock.patch('os.open') as os_open:
            ioctl.side_effect = [
                OSError,
                OSError,
                OSError,
                b'C\x00\xf0\x00\x00\x00\x00\x00',
            ]
            assert term_size() == (240, 67)
            with mock.patch('os.environ', {}) as environ:
                ioctl.side_effect = OSError
                os_open.side_effect = OSError
                environ['COLUMNS'] = 240
                environ['LINES'] = 68
                assert term_size() == (240, 68)
                environ.clear()
                assert term_size() == (80, 24)


def test_error_handler_ops():
    handler = ErrorHandler()
    assert len(handler) == 3
    assert SystemExit in handler
    assert KeyboardInterrupt in handler
    handler[Exception] = (handler.exc_message, 1)
    assert len(handler) == 4
    assert handler[Exception] == (handler.exc_message, 1)
    del handler[Exception]
    assert len(handler) == 3


def test_error_handler_call(capsys):
    handler = ErrorHandler()
    handler[Exception] = (handler.exc_message, 1)
    assert handler(SystemExit, 4, None) == 4
    captured = capsys.readouterr()
    assert not captured.out
    assert not captured.err
    assert handler(KeyboardInterrupt, 3, None) == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert not captured.err
    assert handler(ValueError, 'Wrong value', None) == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err == 'Wrong value\n'
    assert handler(argparse.ArgumentError, 'Invalid option', None) == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err == 'Invalid option\nTry the --help option for more information.\n'
    with mock.patch('traceback.format_exception') as m:
        del handler[Exception]
        m.return_value = ['Traceback lines\n', 'from some file\n', 'with some context\n']
        assert handler(ValueError, 'Another wrong value', {}) == 1
        captured = capsys.readouterr()
        assert not captured.out
        assert captured.err == 'Traceback lines\nfrom some file\nwith some context\n'
