import io
import json
from datetime import datetime
from unittest import mock

import yaml
import pytest

from pictl.setting import *
from pictl.output import *


# Because pyyaml doesn't include these ... ?!
def yaml_dumps(o):
    with io.StringIO() as buf:
        yaml.dump(o, buf)
        return buf.getvalue()

def yaml_loads(s):
    with io.StringIO(s) as buf:
        return yaml.load(buf, Loader=yaml.SafeLoader)


@pytest.fixture()
def store(request):
    return [
        ('foo', False, datetime(2020, 1, 1, 12, 30)),
        ('bar', True, datetime(2020, 1, 2, 0, 0)),
        ('baz', False, datetime(2020, 1, 2, 1, 0)),
    ]


@pytest.fixture()
def left_right_diff(request):
    left = Settings()
    right = left.copy()
    right.update({'video.cec.name': 'Foo', 'boot.test.enabled': None})
    diff = [
        (left['video.cec.name'], right['video.cec.name']),
        (left['boot.test.enabled'], None),
    ]
    return left, right, diff


def test_dump_store_user(store):
    buf = io.StringIO()
    output = Namespace(use_unicode=False)
    output.dump_store(store, buf)
    assert buf.getvalue() == """\
+------+--------+---------------------+
| Name | Active | Timestamp           |
|------+--------+---------------------|
| foo  |        | 2020-01-01 12:30:00 |
| bar  | x      | 2020-01-02 00:00:00 |
| baz  |        | 2020-01-02 01:00:00 |
+------+--------+---------------------+
"""
    buf = io.StringIO()
    output.dump_store([], buf)
    assert buf.getvalue() == "No stored boot configurations found\n"


def test_dump_store_json(store):
    buf = io.StringIO()
    output = Namespace(default_style='json')
    output.dump_store(store, buf)
    assert json.loads(buf.getvalue()) == [
        {'name': n, 'active': a, 'timestamp': t.isoformat()}
        for n, a, t in store
    ]


def test_dump_store_yaml(store):
    buf = io.StringIO()
    output = Namespace(default_style='yaml')
    output.dump_store(store, buf)
    assert yaml_loads(buf.getvalue()) == [
        {'name': n, 'active': a, 'timestamp': t}
        for n, a, t in store
    ]


def test_dump_store_shell(store):
    buf = io.StringIO()
    output = Namespace(default_style='shell')
    output.dump_store(store, buf)
    assert buf.getvalue() == """\
2020-01-01T12:30:00\tinactive\tfoo
2020-01-02T00:00:00\tactive\tbar
2020-01-02T01:00:00\tinactive\tbaz
"""


def test_dump_diff_user(left_right_diff):
    left, right, diff = left_right_diff
    buf = io.StringIO()
    output = Namespace(use_unicode=False)
    output.dump_diff('left', 'right', diff, buf)
    assert buf.getvalue() == """\
+-------------------+----------------+-------+
| Name              | left           | right |
|-------------------+----------------+-------|
| boot.test.enabled | off            | -     |
| video.cec.name    | 'Raspberry Pi' | 'Foo' |
+-------------------+----------------+-------+
"""
    buf = io.StringIO()
    output.dump_diff('left', 'right', [], buf)
    assert buf.getvalue() == 'No differences between left and right\n'


def test_dump_diff_json(left_right_diff):
    left, right, diff = left_right_diff
    buf = io.StringIO()
    output = Namespace(default_style='json')
    output.dump_diff('left', 'right', diff, buf)
    assert json.loads(buf.getvalue()) == {
        'boot.test.enabled': {'left': False},
        'video.cec.name': {'left': 'Raspberry Pi', 'right': 'Foo'},
    }


def test_dump_diff_yaml(left_right_diff):
    left, right, diff = left_right_diff
    buf = io.StringIO()
    output = Namespace(default_style='yaml')
    output.dump_diff('left', 'right', diff, buf)
    assert yaml_loads(buf.getvalue()) == {
        'boot.test.enabled': {'left': False},
        'video.cec.name': {'left': 'Raspberry Pi', 'right': 'Foo'},
    }


def test_dump_diff_shell(left_right_diff):
    left, right, diff = left_right_diff
    buf = io.StringIO()
    output = Namespace(default_style='shell')
    output.dump_diff('left', 'right', diff, buf)
    assert buf.getvalue() == """\
video.cec.name\t'Raspberry Pi'\tFoo
boot.test.enabled\toff\t-
"""


def test_dump_settings_user():
    # Cut down the settings to something manageable for this test
    default = Settings().filter('video.cec.*')
    default.update({'video.cec.name': 'Foo'})
    buf = io.StringIO()
    output = Namespace(use_unicode=False)
    output.dump_settings(default, buf)
    assert buf.getvalue() == """\
+-------------------+-------+
| Name              | Value |
|-------------------+-------|
| video.cec.enabled | on    |
| video.cec.init    | on    |
| video.cec.name    | 'Foo' |
+-------------------+-------+
"""
    buf = io.StringIO()
    output.dump_settings(default, buf, mod=True)
    assert buf.getvalue() == """\
+-------------------+----------+-------+
| Name              | Modified | Value |
|-------------------+----------+-------|
| video.cec.enabled |          | on    |
| video.cec.init    |          | on    |
| video.cec.name    | x        | 'Foo' |
+-------------------+----------+-------+
"""
    buf = io.StringIO()
    output.dump_settings(set(), buf)
    assert buf.getvalue() == "No settings matching the pattern found\n"


def test_dump_settings_json():
    default = Settings()
    buf = io.StringIO()
    output = Namespace(default_style='json')
    output.dump_settings(default, buf)
    assert json.loads(buf.getvalue()) == {
        setting.name: setting.value for setting in default.values()
    }


def test_dump_settings_yaml():
    default = Settings()
    buf = io.StringIO()
    output = Namespace(default_style='yaml')
    output.dump_settings(default, buf)
    assert yaml_loads(buf.getvalue()) == {
        setting.name: setting.value for setting in default.values()
    }


def test_dump_settings_shell():
    # Cut down the settings to something manageable for this test
    default = Settings().filter('video.cec.*')
    buf = io.StringIO()
    output = Namespace(default_style='shell')
    output.dump_settings(default, buf)
    # Sets because there's no guarantee of order in the output
    assert set(buf.getvalue().splitlines()) == {
        "video_cec_enabled=on",
        "video_cec_init=on",
        "video_cec_name='Raspberry Pi'",
    }


def test_load_settings_user():
    output = Namespace()
    with pytest.raises(NotImplementedError):
        output.load_settings(io.StringIO())


def test_load_settings_json():
    settings = {
        'video.cec.enabled': True,
        'video.cec.init': False,
        'video.cec.name': 'Raspberry Pi',
    }
    buf = io.StringIO()
    json.dump(settings, buf)
    buf.seek(0)
    output = Namespace(default_style='json')
    assert output.load_settings(buf) == settings


def test_load_settings_yaml():
    settings = {
        'video.cec.enabled': True,
        'video.cec.init': False,
        'video.cec.name': 'Raspberry Pi',
    }
    buf = io.StringIO()
    yaml.dump(settings, buf)
    buf.seek(0)
    output = Namespace(default_style='yaml')
    assert output.load_settings(buf) == settings


@pytest.mark.xfail(raises=NotImplementedError)
def test_load_settings_shell():
    settings = {
        'video.cec.enabled': True,
        'video.cec.init': False,
        'video.cec.name': 'Raspberry Pi',
    }
    buf = io.StringIO("""\
video_cec_enabled=on
video_cec_init=off
video_cec_name='Raspberry Pi'
""")
    output = Namespace(default_style='shell')
    assert output.load_settings(buf) == settings


def test_format_value_user():
    output = Namespace(use_unicode=False)
    assert output.format_value(1) == '1'
    assert output.format_value(None) == 'auto'
    assert output.format_value(True) == 'on'
    assert output.format_value(False) == 'off'
    assert output.format_value([1, 2, 3]) == repr([1, 2, 3])
    assert output.format_value('Foo') == repr('Foo')
    assert output.format_value('Foo Bar') == repr('Foo Bar')


def test_format_value_json():
    output = Namespace(default_style='json')
    assert output.format_value(1) == json.dumps(1)
    assert output.format_value(None) == json.dumps(None)
    assert output.format_value(True) == json.dumps(True)
    assert output.format_value(False) == json.dumps(False)
    assert output.format_value([1, 2, 3]) == json.dumps([1, 2, 3])
    assert output.format_value('Foo') == json.dumps('Foo')
    assert output.format_value('Foo Bar') == json.dumps('Foo Bar')


def test_format_value_yaml():
    output = Namespace(default_style='yaml')
    assert output.format_value(1) == yaml_dumps(1)
    assert output.format_value(None) == yaml_dumps(None)
    assert output.format_value(True) == yaml_dumps(True)
    assert output.format_value(False) == yaml_dumps(False)
    assert output.format_value([1, 2, 3]) == yaml_dumps([1, 2, 3])
    assert output.format_value('Foo') == yaml_dumps('Foo')
    assert output.format_value('Foo Bar') == yaml_dumps('Foo Bar')


def test_format_value_shell():
    output = Namespace(default_style='shell')
    assert output.format_value(1) == '1'
    assert output.format_value(None) == 'auto'
    assert output.format_value(True) == 'on'
    assert output.format_value(False) == 'off'
    assert output.format_value([1, 2, 3]) == '(1 2 3)'
    assert output.format_value('Foo') == 'Foo'
    assert output.format_value('Foo Bar') == "'Foo Bar'"


def test_dump_setting_user():
    with mock.patch('pictl.output.term_size') as term_size:
        term_size.return_value = (80, 24)
        default = Settings()
        buf = io.StringIO()
        output = Namespace(use_unicode=False)
        output.dump_setting(default['video.cec.name'], buf)
        assert buf.getvalue() == """\
      Name: video.cec.name
   Default: 'Raspberry Pi'
Command(s): cec_osd_name

The name the Pi (as a CEC device) should provide to the connected display;
defaults to "Raspberry Pi".
"""
        buf = io.StringIO()
        output = Namespace(use_unicode=False)
        output.dump_setting(default['i2c.baud'], buf)
        assert buf.getvalue() == """\
     Name: i2c.baud
  Default: 100000
  Overlay: base
Parameter: i2c_arm_baudrate

The baud-rate of the ARM I2C bus.
"""
