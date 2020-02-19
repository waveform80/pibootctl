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

    Uses :class:`tempfile.NamedTemporaryFile` to construct a temporary file in
    the same directory as the target file. The associated file-like object is
    returned as the context manager's variable; you should write the content
    you wish to this object.

    When the context manager exits, if no exception has occurred, the temporary
    file will be renamed over the target file atomically (and sensible
    permissions will be set, i.e. 0666 & umask).  If an exception occurs during
    the context manager's block, the temporary file will be deleted leaving the
    original target file unaffected and the exception will be re-raised.

    :param pathlib.Path path:
        The full path and filename of the target file. This is expected to be
        an absolute path.

    :param str encoding:
        If ``None`` (the default), the temporary file will be opened in binary
        mode. Otherwise, this specifies the encoding to use with text mode.
    """
    umask = None

    def __init__(self, path, encoding=None):
        if isinstance(path, str):
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
        if AtomicReplaceFile.umask is None:
            AtomicReplaceFile.umask = get_umask()
        os.fchmod(self._withfile.file.fileno(),
                  0o666 & AtomicReplaceFile.umask)
        result = self._tempfile.__exit__(exc_type, exc_value, exc_tb)
        if exc_type is None:
            os.rename(self._withfile.name, str(self._path))
        else:
            os.unlink(self._withfile.name)
        return result
