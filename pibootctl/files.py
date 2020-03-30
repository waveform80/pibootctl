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

"""
The :mod:`pibootctl.files` module contains the :class:`AtomicReplaceFile`
context manager, used to "safely" replace files by writing to a temporary
file in the same directory, then moving the result over the target if no
exception occurs within the block. The result is that external processes either
see the "old" state of the file, or the "new" state, but nothing in between::

    >>> from pathlib import Path
    >>> from pibootctl.files import AtomicReplaceFile
    >>> foo = Path('foo.txt')
    >>> foo.write_text('foo')
    >>> foo.read_text()
    'foo'
    >>> with AtomicReplaceFile(foo, encoding='ascii') as f:
    ...     f.write('bar')
    ...     raise Exception('something went wrong!')
    ...
    3
    Traceback (most recent call last):
      File "<stdin>", line 3, in <module>
    Exception: something went wrong!
    >>> foo.read_text()
    'foo'

.. autoclass:: AtomicReplaceFile
"""

import os
import tempfile
import threading
from pathlib import Path


def get_umask():
    """
    Return the umask of the current process.

    .. warning::

        This function is *not* safe in a multi-threaded context. For a brief
        moment, the umask of the process will be modified (as this is the only
        means of querying the umask without writing stuff to disk, which is
        subject to all sorts of caveats over location). To this end, the
        function will refuse to run in anything but the main thread.
    """
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError('get_umask called from thread other than main')
    mask = os.umask(0)
    os.umask(mask)
    return mask


class AtomicReplaceFile:
    """
    A context manager for atomically replacing a target file.

    Uses :func:`tempfile.NamedTemporaryFile` to construct a temporary file in
    the same directory as the target file. The associated file-like object is
    returned as the context manager's variable; you should write the content
    you wish to this object.

    When the context manager exits, if no exception has occurred, the temporary
    file will be renamed over the target file atomically (and sensible
    permissions will be set, i.e. 0666 & umask).  If an exception occurs during
    the context manager's block, the temporary file will be deleted leaving the
    original target file unaffected and the exception will be re-raised.

    :type path: str or pathlib.Path
    :param path:
        The full path and filename of the target file. This is expected to be
        an absolute path.

    :param str encoding:
        If :data:`None` (the default), the temporary file will be opened in
        binary mode. Otherwise, this specifies the encoding to use with text
        mode.
    """
    umask = get_umask()

    def __init__(self, path, encoding=None):
        if not isinstance(path, Path):
            path = Path(path)
        self._path = path
        self._tempfile = tempfile.NamedTemporaryFile(
            mode='wb' if encoding is None else 'w',
            dir=str(self._path.parent), encoding=encoding, delete=False)
        self._withfile = None

    def __enter__(self):
        self._withfile = self._tempfile.__enter__()
        return self._withfile

    def __exit__(self, exc_type, exc_value, exc_tb):
        os.fchmod(self._withfile.file.fileno(),
                  0o666 & ~AtomicReplaceFile.umask)
        result = self._tempfile.__exit__(exc_type, exc_value, exc_tb)
        if exc_type is None:
            os.rename(self._withfile.name, str(self._path))
        else:
            os.unlink(self._withfile.name)
        return result
