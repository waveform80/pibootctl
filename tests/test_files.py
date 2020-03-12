import os
from unittest import mock

import pytest

from pibootctl.files import *


def test_atomic_write_success(tmpdir):
    with AtomicReplaceFile(str(tmpdir.join('foo'))) as f:
        f.write(b'\x00' * 4096)
        temp_name = f.name
    assert os.path.exists(str(tmpdir.join('foo')))
    assert not os.path.exists(temp_name)
    # TODO Test file permissions?


def test_atomic_write_failed(tmpdir):
    with pytest.raises(IOError):
        with AtomicReplaceFile(str(tmpdir.join('foo'))) as f:
            f.write(b'\x00' * 4096)
            temp_name = f.name
            raise IOError("Something went wrong")
        assert not os.path.exists(str(tmpdir.join('foo')))
        assert not os.path.exists(temp_name)


def test_umask_child_thread():
    with mock.patch('threading.current_thread') as current_thread, \
            mock.patch('threading.main_thread') as main_thread:
        current_thread.return_value = object()
        main_thread.return_value = object()
        with pytest.raises(RuntimeError):
            get_umask()
