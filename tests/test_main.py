import io
import sys
import json
import yaml
from datetime import datetime
from unittest import mock
from pathlib import Path
from operator import itemgetter

import pytest

from pictl import *


@pytest.fixture()
def store(request, tmpdir):
    boot_path = Path(str(tmpdir))
    store_path = boot_path / 'pictl'
    store_path.mkdir()
    def my_read(self, *args, **kwargs):
        self['defaults']['boot_path'] = str(boot_path)
        self['defaults']['store_path'] = str(store_path)
        self['defaults']['reboot_required'] = ''
        self['defaults']['reboot_required_pkgs'] = ''
    with mock.patch('configparser.ConfigParser.read', my_read):
        yield Store(mock.Mock(
            boot_path=boot_path, store_path=store_path,
            config_read='config.txt', config_write='config.txt'))


def test_help(capsys):
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


def test_help_command(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(['help', 'status'])
    assert exc_info.value.args[0] == 0
    captured = capsys.readouterr()
    assert captured.out.lstrip().startswith('usage: ')
    assert {'--all', '--json', '--yaml', '--shell'} <= set(captured.out.split())


def test_help_setting(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(['help', 'camera.enabled'])
    assert exc_info.value.args[0] == 0
    captured = capsys.readouterr()
    assert captured.out.lstrip().startswith('Name: camera.enabled')
    assert {'start_x', 'start_debug', 'start_file', 'fixup_file'} <= set(
        captured.out.replace(',', '').split())

    with pytest.raises(ValueError):
        main(['help', 'foo.bar'])


def test_help_config_command(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(['help', 'start_x'])
    assert exc_info.value.args[0] == 0
    captured = capsys.readouterr()
    assert captured.out.lstrip().startswith('Name: camera.enabled')
    assert {'start_x', 'start_debug', 'start_file', 'fixup_file'} <= set(
        captured.out.replace(',', '').split())


def test_help_config_multi(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(['help', 'start_file'])
    assert exc_info.value.args[0] == 0
    captured = capsys.readouterr()
    assert captured.out.lstrip().startswith('start_file is affected by')


def test_dump_show(capsys, store):
    current = store[Current].mutable("config.txt")
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store[Current] = current

    main(['status', '--json'])
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        'video.hdmi0.group': 1, 'video.hdmi0.mode': 4}


def test_dump_show_name(capsys, store):
    current = store[Current].mutable("config.txt")
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store[Current] = current
    current.update({'camera.enabled': True, 'gpu.mem': 128})
    store["cam"] = current

    main(['show', '--json', 'cam'])
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        'video.hdmi0.group': 1, 'video.hdmi0.mode': 4,
        'camera.enabled': True, 'gpu.mem': 128}


def test_dump_show_filters(capsys, store):
    current = store[Current].mutable("config.txt")
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store[Current] = current

    main(['status', '--json', '--all'])
    captured = capsys.readouterr()
    assert json.loads(captured.out).keys() == current.settings.keys()

    main(['status', '--json', '*.group'])
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {'video.hdmi0.group': 1}


def test_get(capsys, store):
    current = store[Current].mutable("config.txt")
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store[Current] = current

    main(['get', 'video.hdmi0.group'])
    captured = capsys.readouterr()
    assert captured.out == '1\n'

    with pytest.raises(ValueError):
        main(['get', 'foo.bar'])


def test_get_multi(capsys, store):
    current = store[Current].mutable("config.txt")
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store[Current] = current

    main(['get', '--json', 'video.hdmi0.group', 'spi.enabled'])
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {'video.hdmi0.group': 1, 'spi.enabled': False}

    with pytest.raises(ValueError):
        main(['get', '--json', 'video.hdmi0.group', 'foo.bar'])


def test_set(store):
    current = store[Current].mutable("config.txt")
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store[Current] = current

    changes = {'video.hdmi0.mode': 3}
    with mock.patch('sys.stdin', io.StringIO(json.dumps(changes))):
        main(['set', '--json'])
    current = store[Current]
    assert current.settings['video.hdmi0.group'].value == 1
    assert current.settings['video.hdmi0.mode'].value == 3


def test_set_user(store):
    current = store[Current].mutable("config.txt")
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


def test_save(store):
    current = store[Current].mutable("config.txt")
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store[Current] = current

    assert 'foo' not in store
    main(['save', 'foo'])
    assert 'foo' in store
    with pytest.raises(FileExistsError):
        main(['save', 'foo'])
    main(['save', 'foo', '--force'])
    assert 'foo' in store


def test_load(store):
    current = store[Current].mutable("config.txt")
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store['foo'] = current

    assert not store[Current].settings['video.hdmi0.group'].modified
    with mock.patch('pictl.datetime') as dt:
        dt.now.return_value = datetime(2000, 1, 1)
        main(['load', 'foo'])
    assert store[Current].settings['video.hdmi0.group'].modified
    assert store.keys() == {Current, Default, 'foo', 'backup-20000101-000000'}


def test_load_no_backup(store):
    current = store[Current].mutable("config.txt")
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store['foo'] = current

    assert not store[Current].settings['video.hdmi0.group'].modified
    main(['load', 'foo', '--no-backup'])
    assert store[Current].settings['video.hdmi0.group'].modified
    assert store.keys() == {Current, Default, 'foo'}


def test_diff(capsys, store):
    current = store[Current].mutable("config.txt")
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


def test_list(capsys, store):
    with mock.patch('pictl.store.datetime') as dt:
        dt.now.return_value = datetime(2000, 1, 1)
        current = store[Current].mutable("config.txt")
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


def test_remove(store):
    current = store[Current].mutable("config.txt")
    current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
    store['foo'] = current

    assert store.keys() == {Current, Default, 'foo'}
    main(['rm', 'foo'])
    assert store.keys() == {Current, Default}
    with pytest.raises(FileNotFoundError):
        main(['rm', 'bar'])
    main(['rm', '-f', 'bar'])


def test_rename(store):
    current = store[Current].mutable("config.txt")
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


def test_backup_fallback(store):
    with mock.patch('pictl.datetime') as dt:
        dt.now.return_value = datetime(2000, 1, 1)

        current = store[Current].mutable("config.txt")
        current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
        store['foo'] = current

        # Causes a backup to be taken with timestamp 2000-01-01
        main(['load', 'foo'])
        assert set(store.keys()) == {
            Current, Default, 'foo', 'backup-20000101-000000'}

        # Modify the current and cause another backup to be taken without
        # advancing our fake timestamp
        current = store[Current].mutable("config.txt")
        current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 5})
        store[Current] = current
        main(['load', 'foo'])
        assert store.keys() == {
            Current, Default, 'foo', 'backup-20000101-000000',
            'backup-20000101-000000-1'}


def test_reboot_required(tmpdir):
    boot_path = Path(str(tmpdir))
    store_path = boot_path / 'pictl'
    var_run_path = boot_path / 'run'
    store_path.mkdir()
    var_run_path.mkdir()
    def my_read(self, *args, **kwargs):
        self['defaults']['boot_path'] = str(boot_path)
        self['defaults']['store_path'] = str(store_path)
        self['defaults']['reboot_required'] = str(var_run_path / 'reboot-required')
        self['defaults']['reboot_required_pkgs'] = str(var_run_path / 'reboot-required.pkgs')
    with mock.patch('configparser.ConfigParser.read', my_read):
        store = Store(mock.Mock(
            boot_path=boot_path, store_path=store_path,
            config_read='config.txt', config_write='config.txt'))
        current = store[Current].mutable("config.txt")
        current.update({'video.hdmi0.group': 1, 'video.hdmi0.mode': 4})
        store['foo'] = current

        assert not (var_run_path / 'reboot-required').exists()
        assert not (var_run_path / 'reboot-required.pkgs').exists()
        main(['load', 'foo'])
        assert (var_run_path / 'reboot-required').read_text() != ''
        assert main.config.package_name in (var_run_path / 'reboot-required.pkgs').read_text()


def test_permission_error(store):
    with mock.patch('pictl.os.geteuid') as geteuid:
        geteuid.return_value = 1000
        try:
            raise PermissionError('permission denied')
        except PermissionError:
            msg = permission_error(*sys.exc_info())
            assert len(msg) == 2
            assert msg[0] == 'permission denied'