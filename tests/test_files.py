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
