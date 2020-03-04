import io
import argparse
from unittest import mock

from pictl.term import *


def test_term_is_dumb():
    with mock.patch('os.isatty') as m:
        m.return_value = False
        assert term_is_dumb()
        m.return_value = True
        assert not term_is_dumb()
    with mock.patch('sys.stdout.fileno') as m:
        m.side_effect = OSError
        assert term_is_dumb()


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
    assert handler(SystemExit, SystemExit(4), None) == 4
    captured = capsys.readouterr()
    assert not captured.out
    assert not captured.err
    assert handler(KeyboardInterrupt, KeyboardInterrupt(3), None) == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert not captured.err
    assert handler(ValueError, ValueError('Wrong value'), None) == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err == 'Wrong value\n'
    assert handler(argparse.ArgumentError,
                   argparse.ArgumentError(None, 'Invalid option'), None) == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err == 'None\nTry the --help option for more information.\n'
    with mock.patch('traceback.format_exception') as m:
        del handler[Exception]
        m.return_value = ['Traceback lines\n', 'from some file\n', 'with some context\n']
        assert handler(ValueError, ValueError('Another wrong value'), {}) == 1
        captured = capsys.readouterr()
        assert not captured.out
        assert captured.err == 'Traceback lines\nfrom some file\nwith some context\n'


def test_term_pager(capsys, tmpdir):
    with mock.patch('pictl.term.term_is_dumb') as dumb, \
            mock.patch('subprocess.Popen') as popen:
        dumb.return_value = True
        with pager():
            print('dumb terminal passes thru')
        captured = capsys.readouterr()
        assert captured.out == 'dumb terminal passes thru\n'
        assert captured.err == ''
        dumb.return_value = False
        popen.side_effect = OSError(2, "File not found")
        with pager():
            print('foo')
        captured = capsys.readouterr()
        assert captured.out == 'foo\n'
        assert captured.err == ''
        popen.side_effect = OSError(1, "Permission denied")
        with pager():
            print('foo bar')
        captured = capsys.readouterr()
        assert captured.out == 'foo bar\n'
        assert captured.err == """\
Failed to execute pager: pager
[Errno 1] Permission denied
Failed to execute pager: less
[Errno 1] Permission denied
Failed to execute pager: more
[Errno 1] Permission denied
"""
        popen.side_effect = None
        popen.return_value = mock.Mock(stdin=tmpdir.join('pager.out').open('wb'))
        with pager():
            print('foo bar baz')
        captured = capsys.readouterr()
        assert captured.out == ''
        assert captured.err == ''
        assert tmpdir.join('pager.out').read_binary() == b'foo bar baz\n'
