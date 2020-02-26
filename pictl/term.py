import os
import io
import sys
import fcntl
import errno
import struct
import locale
import gettext
import termios
import argparse
import traceback
import subprocess
from collections import OrderedDict, namedtuple
from contextlib import contextmanager, redirect_stdout

_ = gettext.gettext


def term_is_dumb():
    try:
        stdout_fd = sys.stdout.fileno()
    except OSError:
        return True
    else:
        return not os.isatty(stdout_fd)


def term_is_utf8():
    locale.setlocale(locale.LC_ALL, '')
    return locale.nl_langinfo(locale.CODESET) == 'UTF-8'


def term_size():
    "Returns the size (cols, rows) of the console"

    # POSIX query_console_size() adapted from
    # http://mail.python.org/pipermail/python-list/2006-February/365594.html
    # http://mail.python.org/pipermail/python-list/2000-May/033365.html

    def get_handle_size(handle):
        "Subroutine for querying terminal size from std handle"
        try:
            buf = fcntl.ioctl(handle, termios.TIOCGWINSZ, '12345678')
            row, col = struct.unpack('hhhh', buf)[0:2]
            return (col, row)
        except OSError:
            return None

    stdin, stdout, stderr = 0, 1, 2
    # Try stderr first as it's the least likely to be redirected
    result = (
        get_handle_size(stderr) or
        get_handle_size(stdout) or
        get_handle_size(stdin)
    )
    if not result:
        try:
            fd = os.open(os.ctermid(), os.O_RDONLY)
        except OSError:
            pass
        else:
            try:
                result = get_handle_size(fd)
            finally:
                os.close(fd)
    if not result:
        try:
            result = (os.environ['COLUMNS'], os.environ['LINES'])
        except KeyError:
            # Default
            result = (80, 24)
    return result


@contextmanager
def pager():
    if term_is_dumb():
        yield
    else:
        env = os.environ.copy()
        env['LESS'] = 'FRSXMK'
        for exe in ('pager', 'less', 'more'):
            try:
                p = subprocess.Popen(exe, stdin=subprocess.PIPE, env=env)
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    print(_("Failed to execute pager: {}").format(exe),
                          file=sys.stderr)
                    print(str(exc), file=sys.stderr)
            else:
                with io.TextIOWrapper(p.stdin, encoding=sys.stdout.encoding,
                                      write_through=True) as w:
                    with redirect_stdout(w):
                        yield
                p.stdin.close()
                p.wait()
                break
        else:
            yield


class ErrorAction(namedtuple('ErrorAction', ('message', 'exitcode'))):
    """
    Named tuple dictating the action to take in response to an unhandled
    exception of the type it is associated with in :class:`ErrorHandler`.
    The *message* is an iterable of lines to be output as critical error
    log messages, and *exitcode* is an integer to return as the exit code of
    the process.

    Either of these can also be functions which will be called with the
    exception info (type, value, traceback) and will be expected to return
    an iterable of lines (for *message*) or an integer (for *exitcode*).
    """
    pass


class ErrorHandler:
    """
    Global configurable application exception handler. For "basic" errors (I/O
    errors, keyboard interrupt, etc.) just the error message is printed as
    there's generally no need to confuse the user with a complete stack trace
    when it's just a missing file. Other exceptions, however, are logged with
    the usual full stack trace.

    The configuration can be augmented with other exception classes that should
    be handled specially by treating the instance as a dictionary mapping
    exception classes to :class:`ErrorAction` tuples.
    """
    def __init__(self):
        self._config = OrderedDict([
            # Exception type,        (handler method, exit code)
            (SystemExit,             (None, self.exc_value)),
            (KeyboardInterrupt,      (None, 2)),
            (argparse.ArgumentError, (self.syntax_error, 2)),
        ])

    @staticmethod
    def exc_message(exc_type, exc_value, exc_tb):
        return [exc_value]

    @staticmethod
    def exc_value(exc_type, exc_value, exc_tb):
        return exc_value

    @staticmethod
    def syntax_error(exc_type, exc_value, exc_tb):
        return [exc_value, _('Try the --help option for more information.')]

    def __len__(self):
        return len(self._config)

    def __contains__(self, key):
        return key in self._config

    def __getitem__(self, key):
        return self._config[key]

    def __setitem__(self, key, value):
        self._config[key] = ErrorAction(*value)

    def __delitem__(self, key):
        del self._config[key]

    def __call__(self, exc_type, exc_value, exc_tb):
        for exc_class, (message, value) in self._config.items():
            if issubclass(exc_type, exc_class):
                if callable(message):
                    message = message(exc_type, exc_value, exc_tb)
                if callable(value):
                    value = value(exc_type, exc_value, exc_tb)
                if message is not None:
                    for line in message:
                        print(line, file=sys.stderr)
                return value
        # Otherwise, log the stack trace and the exception into the log
        # file for debugging purposes
        for line in traceback.format_exception(exc_type, exc_value, exc_tb):
            for msg in line.rstrip().split('\n'):
                print(msg, file=sys.stderr)
        return 1
