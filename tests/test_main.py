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
