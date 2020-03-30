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
import io
import sys
import json
import yaml
from datetime import datetime
from unittest import mock
from pathlib import Path
from operator import itemgetter

import pytest

from pibootctl.store import Store, Current, Default
from pibootctl.term import ErrorHandler
from pibootctl.main import Application


@pytest.fixture()
def store(request, tmpdir):
    boot_path = Path(str(tmpdir))
    store_path = boot_path / 'pibootctl'
    store_path.mkdir()
    def my_read(self, *args, **kwargs):
        self['defaults']['boot_path'] = str(boot_path)
        self['defaults']['store_path'] = str(store_path)
        self['defaults']['reboot_required'] = ''
        self['defaults']['reboot_required_pkgs'] = ''
        return []
    with mock.patch('configparser.ConfigParser.read', my_read):
        yield Store(boot_path, store_path)


@pytest.fixture()
def distro(request):
    # Fake pkg_resources.require; this is only required when running tests in
    # an environment in which the package isn't actually installed (such as
    # when building a deb)
    with mock.patch('pibootctl.main.pkg_resources.require') as require:
        require.return_value = (mock.Mock(version='0.1'),)
        yield


@pytest.fixture()
def main(request):
    return Application()


def test_help(main, capsys, distro):
    with pytest.raises(SystemExit) as exc_info:
        main(['-h'])
    assert exc_info.value.args[0] == 0
    captured = capsys.readouterr()
    assert captured.out.lstrip().startswith('usage: ')
    # Make sure all the expected commands exist in the help text (these aren't
    # localizable so it's safe to test for them)
    assert {'status', 'get', 'set', 'load', 'save', 'diff'} <= set(captured.out.split())

    with pytest.raises(SystemExit) as exc_info:
        main(['help'])
    assert exc_info.value.args[0] == 0
    captured = capsys.readouterr()
    assert captured.out.lstrip().startswith('usage: ')
    assert {'status', 'get', 'set', 'load', 'save', 'diff'} <= set(captured.out.split())


def test_help_command(main, capsys, distro):
    with pytest.raises(SystemExit) as exc_info:
        main(['help', 'status'])
    assert exc_info.value.args[0] == 0
    captured = capsys.readouterr()
    assert captured.out.lstrip().startswith('usage: ')
    assert {'--all', '--json', '--yaml', '--shell'} <= set(captured.out.split())


def test_help_setting(main, capsys, distro):
    with pytest.raises(SystemExit) as exc_info:
        main(['help', 'camera.enabled'])
    assert exc_info.value.args[0] == 0
    captured = capsys.readouterr()
    assert captured.out.lstrip().startswith('Name: camera.enabled')
    assert {'start_x', 'start_debug', 'start_file', 'fixup_file'} <= set(
        captured.out.replace(',', '').split())

    with pytest.raises(ValueError):
        main(['help', 'foo.bar'])


def test_help_config_command(main, capsys, distro):
    with pytest.raises(SystemExit) as exc_info:
        main(['help', 'start_x'])
    assert exc_info.value.args[0] == 0
    captured = capsys.readouterr()
    assert captured.out.lstrip().startswith('Name: camera.enabled')
    assert {'start_x', 'start_debug', 'start_file', 'fixup_file'} <= set(
        captured.out.replace(',', '').split())


def test_help_config_multi(main, capsys, distro):
    with pytest.raises(SystemExit) as exc_info:
        main(['help', 'start_file'])
    assert exc_info.value.args[0] == 0
    captured = capsys.readouterr()
    assert captured.out.lstrip().startswith('start_file is affected by')


def test_dump_show(main, capsys, store, distro):
    current = store[Current].mutable()
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store[Current] = current

    main(['status', '--json'])
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        'video.hdmi0.group': 1, 'video.hdmi0.mode': 4}


def test_dump_show_name(main, capsys, store, distro):
    current = store[Current].mutable()
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store[Current] = current
    current.update({'camera.enabled': True, 'gpu.mem': 128})
    store['cam'] = current

    main(['show', '--json', 'cam'])
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        'video.hdmi0.group': 1, 'video.hdmi0.mode': 4,
        'camera.enabled': True, 'gpu.mem': 128}


def test_dump_show_filters(main, capsys, store, distro):
    current = store[Current].mutable()
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store[Current] = current

    main(['status', '--json', '--all'])
    captured = capsys.readouterr()
    assert json.loads(captured.out).keys() == current.settings.keys()

    main(['status', '--json', '*.group'])
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {'video.hdmi0.group': 1}


def test_get(main, capsys, store, distro):
    current = store[Current].mutable()
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store[Current] = current

    main(['get', 'video.hdmi0.group'])
    captured = capsys.readouterr()
    assert captured.out == '1\n'

    with pytest.raises(ValueError):
        main(['get', 'foo.bar'])


def test_get_multi(main, capsys, store, distro):
    current = store[Current].mutable()
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store[Current] = current

    main(['get', '--json', 'video.hdmi0.group', 'spi.enabled'])
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {'video.hdmi0.group': 1, 'spi.enabled': False}

    with pytest.raises(ValueError):
        main(['get', '--json', 'video.hdmi0.group', 'foo.bar'])


def test_set(main, store, distro):
    current = store[Current].mutable()
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store[Current] = current

    changes = {'video.hdmi0.mode': 3}
    with mock.patch('sys.stdin', io.StringIO(json.dumps(changes))):
        main(['set', '--json'])
    current = store[Current]
    assert current.settings['video.hdmi0.group'].value == 1
    assert current.settings['video.hdmi0.mode'].value == 3


def test_set_user(main, store, distro):
    current = store[Current].mutable()
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store[Current] = current

    main(['set', 'video.hdmi0.mode=3'])
    current = store[Current]
    assert current.settings['video.hdmi0.group'].value == 1
    assert current.settings['video.hdmi0.mode'].value == 3

    main(['set', 'video.hdmi0.group=', 'video.hdmi0.mode='])
    current = store[Current]
    assert not current.settings['video.hdmi0.group'].modified
    assert not current.settings['video.hdmi0.mode'].modified

    with pytest.raises(ValueError):
        main(['set', 'video.hdmi0.mode'])


def test_save(main, store, distro):
    current = store[Current].mutable()
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store[Current] = current

    assert 'foo' not in store
    main(['save', 'foo'])
    assert 'foo' in store
    with pytest.raises(FileExistsError):
        main(['save', 'foo'])
    main(['save', 'foo', '--force'])
    assert 'foo' in store


def test_load(main, store, distro):
    current = store[Current].mutable()
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store['foo'] = current

    assert not store[Current].settings['video.hdmi0.group'].modified
    with mock.patch('pibootctl.main.datetime') as dt:
        dt.now.return_value = datetime(2000, 1, 1)
        main(['load', 'foo'])
    assert store[Current].settings['video.hdmi0.group'].modified
    assert store.keys() == {Current, Default, 'foo', 'backup-20000101-000000'}


def test_load_no_backup(main, store, distro):
    current = store[Current].mutable()
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store['foo'] = current

    assert not store[Current].settings['video.hdmi0.group'].modified
    main(['load', 'foo', '--no-backup'])
    assert store[Current].settings['video.hdmi0.group'].modified
    assert set(store.keys()) == {Current, Default, 'foo'}


def test_diff(main, capsys, store, distro):
    current = store[Current].mutable()
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store['foo'] = current
    current.update({'video.hdmi0.mode': 5, 'spi.enabled': True})
    store['bar'] = current

    main(['diff', 'foo', 'bar', '--json'])
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        'video.hdmi0.mode': {'left': 4, 'right': 5},
        'spi.enabled':      {'left': False, 'right': True},
    }


def test_list(main, capsys, store, distro):
    with mock.patch('pibootctl.store.datetime') as dt:
        dt.now.return_value = datetime(2000, 1, 1)
        current = store[Current].mutable()
        current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
        store['foo'] = current
        current.update({'video.hdmi0.mode': 5, 'spi.enabled': True})
        store['bar'] = current
        store[Current] = store['bar']

    main(['ls', '--json'])
    captured = capsys.readouterr()
    assert sorted(json.loads(captured.out), key=itemgetter('name')) == sorted([
        {'name': 'foo', 'active': False, 'timestamp': '2000-01-01T00:00:00'},
        {'name': 'bar', 'active': True,  'timestamp': '2000-01-01T00:00:00'},
    ], key=itemgetter('name'))


def test_remove(main, store, distro):
    current = store[Current].mutable()
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store['foo'] = current

    assert store.keys() == {Current, Default, 'foo'}
    main(['rm', 'foo'])
    assert store.keys() == {Current, Default}
    with pytest.raises(FileNotFoundError):
        main(['rm', 'bar'])
    main(['rm', '-f', 'bar'])


def test_rename(main, store, distro):
    current = store[Current].mutable()
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store['foo'] = current
    store['bar'] = current

    assert store.keys() == {Current, Default, 'foo', 'bar'}
    main(['mv', 'foo', 'baz'])
    assert store.keys() == {Current, Default, 'baz', 'bar'}
    with pytest.raises(FileExistsError):
        main(['mv', 'bar', 'baz'])
    assert store.keys() == {Current, Default, 'baz', 'bar'}
    main(['mv', '-f', 'bar', 'baz'])
    assert store.keys() == {Current, Default, 'baz'}


def test_backup_fallback(main, store, distro):
    with mock.patch('pibootctl.main.datetime') as dt:
        dt.now.return_value = datetime(2000, 1, 1)

        current = store[Current].mutable()
        current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
        store['foo'] = current

        # Causes a backup to be taken with timestamp 2000-01-01
        main(['load', 'foo'])
        assert set(store.keys()) == {
            Current, Default, 'foo', 'backup-20000101-000000'}

        # Modify the current and cause another backup to be taken without
        # advancing our fake timestamp
        current = store[Current].mutable()
        current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 5})
        store[Current] = current
        main(['load', 'foo'])
        assert store.keys() == {
            Current, Default, 'foo', 'backup-20000101-000000',
            'backup-20000101-000000-1'}


def test_reboot_required(main, tmpdir, distro):
    boot_path = Path(str(tmpdir))
    store_path = boot_path / 'store'
    var_run_path = boot_path / 'run'
    store_path.mkdir()
    var_run_path.mkdir()
    def my_read(self, *args, **kwargs):
        self['defaults']['boot_path'] = str(boot_path)
        self['defaults']['store_path'] = str(store_path)
        self['defaults']['reboot_required'] = str(var_run_path / 'reboot-required')
        self['defaults']['reboot_required_pkgs'] = str(var_run_path / 'reboot-required.pkgs')
        return []
    with mock.patch('configparser.ConfigParser.read', my_read):
        store = Store(boot_path, store_path)
        current = store[Current].mutable()
        current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
        store['foo'] = current

        assert not (var_run_path / 'reboot-required').exists()
        assert not (var_run_path / 'reboot-required.pkgs').exists()
        main(['load', 'foo'])
        assert (var_run_path / 'reboot-required').read_text() != ''
        assert main.config.package_name in (var_run_path / 'reboot-required.pkgs').read_text()


def test_permission_error(store):
    with mock.patch('pibootctl.main.os.geteuid') as geteuid:
        geteuid.return_value = 1000
        try:
            raise PermissionError('permission denied')
        except PermissionError:
            msg = Application.permission_error(*sys.exc_info())
            assert len(msg) == 2
            assert msg[0] == 'permission denied'
            assert 'root' in msg[1]

        geteuid.return_value = 0
        try:
            raise PermissionError('permission denied')
        except PermissionError:
            msg = Application.permission_error(*sys.exc_info())
            assert len(msg) == 1
            assert msg[0] == 'permission denied'


def test_invalid_config(main, tmpdir, distro):
    boot_path = Path(str(tmpdir))
    (boot_path / 'config.txt').write_text('include syscfg.txt\n')
    store_path = boot_path / 'store'
    store_path.mkdir()
    def my_read(self, *args, **kwargs):
        self['defaults']['boot_path'] = str(boot_path)
        self['defaults']['store_path'] = str(store_path)
        self['defaults']['config_read'] = 'config.txt'
        self['defaults']['config_write'] = 'syscfg.txt'
        return []
    with mock.patch('configparser.ConfigParser.read', my_read):
        try:
            main(['set', 'video.hdmi0.group=1'])
        except:
            msg = Application.invalid_config(*sys.exc_info())
            assert len(msg) == 2
            assert msg == [
                "Configuration failed to validate with 1 error(s)",
                "video.hdmi0.mode must be between 1 and 59 when "
                "video.hdmi0.group is 1",
            ]


def test_overridden_config(main, tmpdir, distro):
    boot_path = Path(str(tmpdir))
    (boot_path / 'config.txt').write_text(
        'include syscfg.txt\ninclude usercfg.txt\n')
    (boot_path / 'usercfg.txt').write_text(
        'dtparam=spi=on\n')
    store_path = boot_path / 'store'
    store_path.mkdir()
    def my_read(self, *args, **kwargs):
        self['defaults']['boot_path'] = str(boot_path)
        self['defaults']['store_path'] = str(store_path)
        self['defaults']['config_read'] = 'config.txt'
        self['defaults']['config_write'] = 'syscfg.txt'
        return []
    with mock.patch('configparser.ConfigParser.read', my_read):
        try:
            main(['set', 'spi.enabled='])
        except:
            msg = Application.overridden_config(*sys.exc_info())
            assert len(msg) == 2
            assert msg == [
                "Failed to set 1 setting(s)",
                "Expected spi.enabled to be False, but was True after being "
                "overridden by usercfg.txt line 1",
            ]


def test_debug_run(main, capsys, distro):
    sys.excepthook = sys.__excepthook__
    os.environ['DEBUG'] = '1'
    with pytest.raises(SystemExit):
        main(['help'])
    assert not isinstance(sys.excepthook, ErrorHandler)
    del os.environ['DEBUG']
    with pytest.raises(SystemExit):
        main(['help'])
    assert isinstance(sys.excepthook, ErrorHandler)


def test_complete_help(main, distro):
    assert set(main._complete_help('he')) == {'help'}
    assert set(main._complete_help('cam')) == {
        'camera.enabled', 'camera.led.enabled'}


def test_complete_status(main):
    assert set(main._complete_status('he')) == set()
    assert set(main._complete_status('cam')) == {
        'camera.enabled', 'camera.led.enabled'}


def test_complete_show(main, store):
    assert set(main._complete_show_name('ca')) == set()
    store['cam'] = store[Current]
    store['default'] = store[Default]
    assert set(main._complete_show_name('ca')) == {'cam'}
    parsed_args = mock.Mock()
    parsed_args.name = 'cam'
    assert set(main._complete_show_vars('camera.', parsed_args)) == {
        'camera.enabled', 'camera.led.enabled'}


def test_complete_get(main):
    assert set(main._complete_get_vars('boot.kernel.a')) == {
        'boot.kernel.address', 'boot.kernel.atags'}


def test_complete_set(main):
    assert set(main._complete_set_vars('bluetooth.e')) == {
        'bluetooth.enabled='}
    assert set(main._complete_set_vars('bluetooth.enabled=o')) == set()


def test_complete_save(main, store):
    store['cam'] = store[Current]
    store['default'] = store[Default]
    parsed_args = mock.Mock()
    parsed_args.force = False
    assert set(main._complete_save_name('', parsed_args)) == set()
    parsed_args.force = True
    assert set(main._complete_save_name('', parsed_args)) == {'cam', 'default'}


def test_complete_load(main, store):
    store['cam'] = store[Current]
    store['default'] = store[Default]
    assert set(main._complete_load_name('c')) == {'cam'}


def test_complete_diff(main, store):
    store['cam'] = store[Current]
    store['default'] = store[Default]
    assert set(main._complete_diff_left('c')) == {'cam'}
    parsed_args = mock.Mock()
    parsed_args.left = 'cam'
    assert set(main._complete_diff_right('c', parsed_args)) == set()
    assert set(main._complete_diff_right('', parsed_args)) == {'default'}


def test_complete_remove(main, store):
    store['cam'] = store[Current]
    store['default'] = store[Default]
    assert set(main._complete_remove_name('')) == {'default', 'cam'}


def test_complete_rename(main, store):
    store['cam'] = store[Current]
    store['default'] = store[Default]
    assert set(main._complete_rename_name('')) == {'default', 'cam'}
    parsed_args = mock.Mock()
    parsed_args.force = False
    parsed_args.name = 'cam'
    assert set(main._complete_rename_to('', parsed_args)) == set()
    parsed_args.force = True
    assert set(main._complete_rename_to('', parsed_args)) == {'default'}
