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
The :mod:`pibootctl.term` module contains various utilities for determining the
type of terminal the script is running under (:func:`term_is_dumb`,
:func:`term_is_utf8`, and :func:`term_size`), for directing terminal output
through the system's :func:`pager`, and for constructing an overall
:class:`ErrorHandler` for the script.

.. autoclass:: ErrorHandler
    :members:

.. autoclass:: ErrorAction(message, exitcode)

.. autofunction:: term_is_dumb

.. autofunction:: term_is_utf8

.. autofunction:: term_size

.. autofunction:: pager
"""

import os
import io
import sys
import fcntl
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
    """
    Returns :data:`True` if stdout is something other than a TTY (e.g. a file
    redirection or a pipe).
    """
    try:
        stdout_fd = sys.stdout.fileno()
    except OSError:
        return True
    else:
        return not os.isatty(stdout_fd)


def term_is_utf8():
    "Returns :data:`True` if the code-set of the current locale is 'UTF-8'."
    locale.setlocale(locale.LC_ALL, '')
    return locale.nl_langinfo(locale.CODESET) == 'UTF-8'


def term_size():
    "Returns the size of the console as a (rows, cols) tuple."

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
def pager(enable=None):
    """
    Used as a context manager to redirect stdout to the system's pager utility
    ("pager", "less", or "more" are all attempted, in that order).

    By default (when *enable* is :data:`None`), stdout will only be redirected
    if stdout is connected to a TTY. If *enable* is :data:`True` stdout will
    always be redirected, and likewise when *enable* is :data:`False` the
    function will do nothing.

    For example, the following script should print "Hello, world!", piping the
    result through the system's pager::

        from pibootctl.term import pager
        with pager():
            print("Hello, world!")
    """
    if enable is None:
        enable = not term_is_dumb()
    if enable:
        env = os.environ.copy()
        env['LESS'] = 'FRSXMK'
        for exe in ('pager', 'less', 'more'):
            try:
                proc = subprocess.Popen(exe, stdin=subprocess.PIPE, env=env)
            except FileNotFoundError:
                pass
            except OSError as exc:
                print(_("Failed to execute pager: {}").format(exe),
                      file=sys.stderr)
                print(str(exc), file=sys.stderr)
            else:
                try:
                    with io.TextIOWrapper(proc.stdin,
                                          encoding=sys.stdout.encoding,
                                          write_through=True) as proc_in:
                        with redirect_stdout(proc_in):
                            yield
                finally:
                    proc.stdin.close()
                    proc.wait()
                break
        else:
            yield
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


class ErrorHandler:
    """
    Global configurable application exception handler. For "basic" errors (I/O
    errors, keyboard interrupt, etc.) just the error message is printed as
    there's generally no need to confuse the user with a complete stack trace
    when it's just a missing file. Other exceptions, however, are logged with
    the usual full stack trace.

    The configuration can be augmented with other exception classes that should
    be handled specially by treating the instance as a dictionary mapping
    exception classes to :class:`ErrorAction` tuples (or any 2-tuple, which
    will be converted to an :class:`ErrorAction`).

    For example::

        >>> from pibootctl.term import ErrorAction, ErrorHandler
        >>> import sys
        >>> sys.excepthook = ErrorHandler()
        >>> sys.excepthook[KeyboardInterrupt]
        (None, 1)
        >>> sys.excepthook[SystemExit]
        (None, <function ErrorHandler.exc_value at 0x7f6178915e18>)
        >>> sys.excepthook[ValueError] = (sys.excepthook.exc_message, 3)
        >>> sys.excepthook[Exception] = ("An error occurred", 1)
        >>> raise ValueError("foo is not an integer")
        foo is not an integer

    Note the lack of a traceback in the output; if the example were a script
    it would also have exited with return code 3.
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
        """
        Extracts the message associated with the exception (by calling
        :class:`str` on the exception instance). The result is returned as a
        one-element list containing the message.
        """
        return [str(exc_value)]

    @staticmethod
    def exc_value(exc_type, exc_value, exc_tb):
        """
        Returns the first argument of the exception instance. In the case of
        :exc:`SystemExit` this is the expected return code of the script.
        """
        return exc_value.args[0]

    @staticmethod
    def syntax_error(exc_type, exc_value, exc_tb):
        """
        Returns the message associated with the exception, and an additional
        line suggested the user try the ``--help`` option. This should be used
        in response to exceptions indicating the user made an error in their
        command line.
        """
        return ErrorHandler.exc_message(exc_type, exc_value, exc_tb) + [
            _('Try the --help option for more information.'),
        ]

    def clear(self):
        """
        Remove all pre-defined error handlers.
        """
        self._config.clear()

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
                    sys.stderr.flush()
                raise SystemExit(value)
        # Otherwise, log the stack trace and the exception into the log
        # file for debugging purposes
        for line in traceback.format_exception(exc_type, exc_value, exc_tb):
            for msg in line.rstrip().split('\n'):
                print(msg, file=sys.stderr)
        sys.stderr.flush()
        raise SystemExit(1)
