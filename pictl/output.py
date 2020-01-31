import io
import json
import shlex
import locale
import gettext
from operator import attrgetter

import yaml

from .settings import Missing
from .formatter import TableWrapper, unicode_table, pretty_table, render
from .term import term_size

_ = gettext.gettext


def print_table(table, fp):
    width = min(120, term_size()[0])
    if locale.nl_langinfo(locale.CODESET) == 'UTF-8':
        style = unicode_table
    else:
        style = pretty_table
    renderer = TableWrapper(width=width, **style)
    for line in renderer.wrap(table):
        fp.write(line)
        fp.write('\n')


def dump_store(style, store, fp):
    {
        'user':  dump_store_user,
        'shell': dump_store_shell,
        'json':  dump_store_json,
        'yaml':  dump_store_yaml,
    }[style](store, fp)

def dump_store_user(store, fp):
    if locale.nl_langinfo(locale.CODESET) == 'UTF-8':
        check = '✓'
    else:
        check = 'x'
    if not store:
        fp.write(_("No stored boot configurations found"))
        fp.write("\n")
    else:
        print_table([
            (_('Name'), _('Active'), _('Timestamp'))
        ] + [
            (name, check if active else '',
             timestamp.strftime('%Y-%m-%d %H:%M:%S'))
            for name, active, timestamp in store
        ], fp)

def dump_store_json(store, fp):
    json.dump([
        {'name': name, 'active': active, 'timestamp': timestamp.isoformat()}
        for name, active, timestamp in store
    ], fp)

def dump_store_yaml(store, fp):
    yaml.dump([
        {'name': name, 'active': active, 'timestamp': timestamp}
        for name, active, timestamp in store
    ], fp)

def dump_store_shell(store, fp):
    for name, active, timestamp in store:
        fp.write(':'.join(
            (timestamp.isoformat(), ('inactive', 'active')[active], name)
        ))
        fp.write('\n')


def dump_diff(style, left, right, diff, fp):
    {
        'user':  dump_diff_user,
        'shell': dump_diff_shell,
        'json':  dump_diff_json,
        'yaml':  dump_diff_yaml,
    }[style](left, right, diff, fp)

def dump_diff_user(left, right, diff, fp):
    if not diff:
        fp.write(
            _("No differences between {left} and {right}").format(
                left=_('Current') if left is None else left,
                right=right))
        fp.write("\n")
    else:
        print_table([
            (_('Name'), '<{}>'.format(_('Current')) if left is None else left, right)
        ] + sorted([
            (l.name if l is not Missing else r.name,
             '-' if l is Missing else format_setting_user(l),
             '-' if r is Missing else format_setting_user(r),
             )
            for (l, r) in diff
        ]), fp)

def values(l, r):
    obj = {}
    if l is not Missing:
        obj['left'] = l.value
    if r is not Missing:
        obj['right'] = r.value
    return obj

def dump_diff_json(left, right, diff, fp):
    json.dump({
        (l.name if l is not Missing else r.name): values(l, r)
        for (l, r) in diff
    }, fp)

def dump_diff_yaml(left, right, diff, fp):
    yaml.dump({
        (l.name if l is not Missing else r.name): values(l, r)
        for (l, r) in diff
    }, fp)

def dump_diff_shell(left, right, diff, fp):
    for l, r in diff:
        fp.write(':'.join(
            (l.name if l is not Missing else r.name,
             '' if l is Missing else str(l.value),
             '' if r is Missing else str(r.value)
             )
        ))
        fp.write('\n')


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
    if not settings:
        fp.write(_("No settings matching the pattern found"))
        fp.write("\n")
    else:
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
        print_table(data, fp)


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
