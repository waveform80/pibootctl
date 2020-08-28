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

from pathlib import Path
from unittest import mock
from zipfile import ZipFile
from datetime import datetime

import pytest

from pibootctl.parser import *
from pibootctl.setting import *
from pibootctl.store import *


@pytest.fixture()
def boot_path(request, tmpdir):
    return Path(str(tmpdir))


@pytest.fixture()
def store_path(request, boot_path):
    return boot_path / 'pibootctl'


cond_all = BootConditions()
cond_none = cond_all.evaluate('none')


def test_singleton_reprs():
    assert repr(Current) == 'Current'
    assert repr(Default) == 'Default'


def test_store_container(boot_path, store_path):
    store = Store(boot_path, store_path)
    (boot_path / 'config.txt').write_text("""\
dtparam=i2c=on
dtparam=spi=on
""")
    store_path.mkdir()
    with (store_path / 'foo.zip').open('wb') as f:
        with ZipFile(f, 'w') as z:
            z.comment = ('pibootctl:0:' + store[Current].hash).encode('ascii')
            store[Current].files['config.txt'].add_to_zip(z)
    with (store_path / 'invalid.zip').open('wb') as f:
        with ZipFile(f, 'w') as z:
            z.comment = ('pibootctl:999:' + store[Current].hash).encode('ascii')
            store[Current].files['config.txt'].add_to_zip(z)
    assert len(store) == 3
    assert Current in store
    assert Default in store
    assert 'foo' in store
    assert 'bar' not in store
    assert set(store) == {Default, Current, 'foo'}
    with pytest.raises(KeyError):
        store['bar']


def test_store_bad_arc(boot_path, store_path):
    store = Store(boot_path, store_path)
    (boot_path / 'config.txt').write_text("""\
dtparam=i2c=on
dtparam=spi=on
""")
    store_path.mkdir()
    with (store_path / 'foo.zip').open('wb') as f:
        with ZipFile(f, 'w') as z:
            z.comment = b'pibootctl:badver:'
            z.writestr('config.txt', b'')
    with pytest.raises(KeyError):
        store['foo']
    with (store_path / 'foo.zip').open('wb') as f:
        with ZipFile(f, 'w') as z:
            z.comment = b'pibootctl:0:badhash'
            z.writestr('config.txt', b'')
    with pytest.raises(ValueError):
        store['foo']
    with (store_path / 'foo.zip').open('wb') as f:
        with ZipFile(f, 'w') as z:
            z.comment = b'pibootctl:0:' + b'h' * 40
            z.writestr('config.txt', b'')
    with pytest.raises(ValueError):
        store['foo']


def test_store_getitem(boot_path, store_path):
    store = Store(boot_path, store_path)
    content = b"""\
dtparam=i2c=on
dtparam=spi=on
hdmi_group=1
hdmi_mode=4
"""
    (boot_path / 'config.txt').write_bytes(content)
    current = store[Current]
    assert current.path == boot_path
    assert current.config_root == 'config.txt'
    d = datetime.fromtimestamp(
        (boot_path / 'config.txt').stat().st_mtime)
    d = d.replace(
        year=max(1980, d.year),
        second=d.second // 2 * 2, microsecond=0)
    assert current.timestamp == d
    assert current.hash == '5179ada9ed2534c0d228d950c65d4d58babef1cd'
    assert current.settings['i2c.enabled'].value
    assert current.settings['spi.enabled'].value
    assert not current.settings['audio.enabled'].value
    assert current.settings['video.hdmi0.group'].value == 1
    assert current.settings['video.hdmi0.mode'].value == 4
    assert current.settings['video.hdmi1.group'].value == 0
    assert current.settings['video.hdmi1.mode'].value == 0
    assert current.files['config.txt'].content == content


def test_store_getitem_with_includes(boot_path, store_path):
    store = Store(boot_path, store_path)
    config_txt = b"""\
[all]
dtparam=i2c=on
dtparam=spi=on
[none]
include inc.txt
"""
    inc_txt = b"""\
[all]
hdmi_group=1
hdmi_mode=4
"""
    (boot_path / 'config.txt').write_bytes(config_txt)
    (boot_path / 'inc.txt').write_bytes(inc_txt)
    current = store[Current]
    assert current.path == boot_path
    assert current.config_root == 'config.txt'
    d = datetime.fromtimestamp(
        (boot_path / 'inc.txt').stat().st_mtime)
    d = d.replace(
        year=max(1980, d.year),
        second=d.second // 2 * 2, microsecond=0)
    assert current.timestamp == d
    assert current.hash == 'e76f44e09c3e3e36022c248cb71924e2af76a18b'
    assert current.settings['i2c.enabled'].value
    assert current.settings['spi.enabled'].value
    assert not current.settings['audio.enabled'].value
    assert current.settings['video.hdmi0.group'].value == 0
    assert current.settings['video.hdmi0.mode'].value == 0
    assert current.settings['video.hdmi1.group'].value == 0
    assert current.settings['video.hdmi1.mode'].value == 0
    assert current.files['config.txt'].content == config_txt
    assert current.files['inc.txt'].content == inc_txt


def test_store_setitem(boot_path, store_path):
    store = Store(boot_path, store_path)
    content = [
        'dtparam=i2c=on\n',
        'dtparam=spi=on\n',
    ]
    (boot_path / 'config.txt').write_text(''.join(content))
    (boot_path / 'edid.dat').write_bytes(b'\x00\x00\x00\xFF')
    assert len(store) == 2
    assert 'foo' not in store
    store['foo'] = store[Current]
    assert store_path.is_dir()
    assert (store_path / 'foo.zip').is_file()
    assert len(store) == 3
    assert 'foo' in store
    assert store['foo'].hash == store[Current].hash
    assert store['foo'].files == store[Current].files
    (boot_path / 'config.txt').write_text('')
    assert store['foo'].hash != store[Current].hash
    assert store['foo'].files != store[Current].files
    store[Current] = store['foo']
    assert store['foo'].hash == store[Current].hash
    assert store['foo'].files == store[Current].files
    with pytest.raises(KeyError):
        store[Default] = store[Current]
    with pytest.raises(KeyError):
        store[''] = store[Current]


def test_store_delitem(boot_path, store_path):
    store = Store(boot_path, store_path)
    (boot_path / 'config.txt').write_text("""\
dtparam=i2c=on
dtparam=spi=on
""")
    store['foo'] = store[Current]
    assert len(store) == 3
    assert 'foo' in store
    del store['foo']
    assert len(store) == 2
    assert 'foo' not in store
    assert not (store_path / 'foo.zip').exists()
    with pytest.raises(KeyError):
        del store['bar']
    with pytest.raises(KeyError):
        del store[Current]
    with pytest.raises(KeyError):
        del store[Default]


def test_store_restore_default(boot_path, store_path):
    store = Store(boot_path, store_path)
    (boot_path / 'config.txt').write_text("""\
dtparam=i2c=on
dtparam=spi=on
""")
    store['foo'] = store[Current]
    store[Current] = store[Default]
    assert not (boot_path / 'config.txt').exists()
    store[Current] = store['foo']
    assert (boot_path / 'config.txt').exists()


def test_store_active(boot_path, store_path):
    store = Store(boot_path, store_path)
    (boot_path / 'config.txt').write_text("""\
dtparam=i2c=on
dtparam=spi=on
""")
    assert len(store) == 2
    assert store.active is None
    store_path.mkdir()
    with (store_path / 'foo.zip').open('wb') as f:
        with ZipFile(f, 'w') as z:
            z.comment = ('pibootctl:0:' + store[Current].hash).encode('ascii')
            store[Current].files['config.txt'].add_to_zip(z)
    assert len(store) == 3
    assert store.active == 'foo'


def test_store_mutable_update(boot_path, store_path):
    store = Store(boot_path, store_path,
                  mutable_files={'config.txt', 'syscfg.txt'})
    (boot_path / 'config.txt').write_text("""\
# Header goes here

include syscfg.txt
""")
    (boot_path / 'syscfg.txt').write_text("""\
dtparam=i2c=on
dtparam=spi=on
""")
    current = store[Current]
    mutable = current.mutable()
    mutable.update({'i2c.enabled': None, 'camera.enabled': True}, cond_all)
    assert mutable.files['config.txt'].content.decode('ascii') == """\
# Header goes here

include syscfg.txt
start_x=1
"""
    assert mutable.files['syscfg.txt'].content.decode('ascii') == """\
dtparam=spi=on
"""


def test_store_mutable_ineffective(boot_path, store_path):
    store = Store(boot_path, store_path,
                  mutable_files={'config.txt', 'syscfg.txt'})
    (boot_path / 'config.txt').write_text("""\
include syscfg.txt
include usercfg.txt
""")
    (boot_path / 'syscfg.txt').write_text("""\
dtparam=i2c=on
dtparam=spi=on
""")
    (boot_path / 'usercfg.txt').write_text("""\
dtparam=i2c=on
""")
    current = store[Current]
    mutable = current.mutable()
    with pytest.raises(IneffectiveConfiguration) as exc_info:
        mutable.update({'i2c.enabled': None}, cond_all)
    assert len(exc_info.value.diff) == 1
    assert str(exc_info.value) == "Failed to set 1 setting(s)"
    assert mutable.files['config.txt'].content.decode('ascii') == """\
include syscfg.txt
include usercfg.txt
"""
    assert mutable.files['syscfg.txt'].content.decode('ascii') == """\
dtparam=spi=on
"""


def test_settings_container():
    settings = Settings()
    assert len([s for s in settings]) == len(settings)
    assert 'video.hdmi0.mode' in settings
    assert isinstance(settings['video.hdmi0.mode'], CommandDisplayMode)


def test_default_config(boot_path, store_path):
    store = Store(boot_path, store_path)
    default = store[Default]
    assert default.files == {}
    assert default.hash == 'da39a3ee5e6b4b0d3255bfef95601890afd80709'
    assert default.timestamp == datetime(1970, 1, 1)


def test_settings_copy():
    settings = Settings()
    copy = settings.copy()
    assert len(settings) == len(copy)
    assert settings is not copy
    assert set(s for s in settings) == set(s for s in copy)
    assert all(settings[name] is not copy[name] for name in settings)


def test_settings_diff(boot_path, store_path):
    store = Store(boot_path, store_path)
    (boot_path / 'config.txt').write_text("""\
dtparam=i2c=on
dtparam=spi=on
hdmi_group=1
hdmi_mode=4
""")
    default = store[Default].settings
    current = store[Current].settings
    assert default.diff(current) == {
        (default[name], current[name])
        for name in (
            'i2c.enabled',
            'spi.enabled',
            'video.hdmi0.group',
            'video.hdmi0.mode',
        )
    }


def test_settings_filter(boot_path, store_path):
    store = Store(boot_path, store_path)
    (boot_path / 'config.txt').write_text("""\
dtparam=i2c=on
dtparam=spi=on
""")
    current = store[Current].settings
    assert 'i2c.enabled' in current
    assert 'video.hdmi0.group' in current
    modified = current.modified()
    assert modified is not current
    assert 'i2c.enabled' in modified
    assert 'video.hdmi0.group' not in modified
    with pytest.raises(KeyError):
        modified['video.hdmi0.group']
    assert len(modified) < len(current)
    filtered = modified.filter('spi.*')
    assert 'i2c.enabled' not in filtered
    assert 'video.hdmi0.group' not in filtered
    assert len(filtered) < len(modified)
