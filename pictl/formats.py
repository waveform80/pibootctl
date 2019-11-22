import io
import json
import shlex
import gettext
from operator import attrgetter

import yaml

from .formatter import TableWrapper, unicode_table, render
from .term import term_size

_ = gettext.gettext


def dump_settings(style, settings, fp):
    {
        'user':  dump_settings_user,
        'shell': dump_settings_shell,
        'json':  dump_settings_json,
        'yaml':  dump_settings_yaml,
    }[style](settings, fp)


def dump_settings_json(settings, fp):
    json.dump({setting.name: setting.value for setting in settings}, fp)


def dump_settings_yaml(settings, fp):
    yaml.dump({setting.name: setting.value for setting in settings}, fp)


def dump_settings_shell(settings, fp):
    for setting in settings:
        fp.write('{}\n'.format(format_setting_shell(setting)))


def dump_settings_user(settings, fp):
    width = min(120, term_size()[0])
    renderer = TableWrapper(width=width, **unicode_table)
    data = [
        (_('Name'), _('Mod'), _('Value'))
    ] + [
        (
            setting.name,
            '✓' if setting.value != setting.default else '',
            format_setting_user(setting),
        )
        for setting in sorted(settings, key=attrgetter('name'))
    ]
    for line in renderer.wrap(data):
        fp.write(line)
        fp.write('\n')


def dump_setting_user(setting, fp):
    width = min(120, term_size()[0])
    print(_("""\
   Name: {name}
Default: {default}

{doc}""").format(
        name=setting.name,
        default=format_setting_user(setting),
        doc=render(setting.doc, width=width, table_style=unicode_table),
    ))


def load_settings(style, fp):
    return {
        'json':  load_settings_json,
        'yaml':  load_settings_yaml,
        'shell': load_settings_shell,
    }[style](fp)


def load_settings_json(fp):
    return json.load(fp)


def load_settings_yaml(fp):
    return yaml.load(fp)


def load_settings_shell(fp):
    # TODO
    raise NotImplementedError


def format_setting_shell(setting):
    return '{name}={value}'.format(
        name=setting.name.replace('.', '_'),
        value=format_value_shell(setting.value)
    )


def format_setting_user(setting):
    value = format_value_user(setting.value)
    explanation = setting.explain()
    return (
        '{value}' if explanation is None else
        '{value} ({explanation})'
    ).format(value=value, explanation=explanation)


def format_value(style, value):
    return {
        'user':  format_value_user,
        'shell': format_value_shell,
        'json':  format_value_json,
        'yaml':  format_value_yaml,
    }[style](value)


def format_value_json(value):
    return json.dumps(value)


def format_value_yaml(value):
    with io.StringIO() as fp:
        yaml.dump(value, fp)
        return fp.getvalue()


def format_value_shell(value):
    if value is None:
        return 'auto'
    elif isinstance(value, bool):
        return ('off', 'on')[value]
    elif isinstance(value, list):
        return '({})'.format(' '.join(format_value_shell(e) for e in value))
    else:
        return shlex.quote(str(value))


def format_value_user(value):
    if value is None:
        return _('auto')
    elif isinstance(value, bool):
        return (_('off'), _('on'))[value]
    elif isinstance(value, str):
        return repr(value)
    else:
        return str(value)
