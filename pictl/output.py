import io
import json
import shlex
import locale
import gettext
import argparse
from operator import attrgetter
from collections import OrderedDict

import yaml

from .setting import Command, OverlayParam
from .formatter import TableWrapper, unicode_table, pretty_table, render
from .term import term_size

_ = gettext.gettext


def values(l, r):
    obj = {}
    if l is not None:
        obj['left'] = l.value
    if r is not None:
        obj['right'] = r.value
    return obj


class Namespace(argparse.Namespace):
    """
    A derivative of :class:`~argparse.Namespace` used by the main application,
    this class provides a variety of methods (:meth:`dump_store`,
    :meth:`dump_diff`, :meth:`load_settings`, etc.) for input and output of
    data.

    These methods change the format they work with based on the value of the
    :attr:`style` attribute which defaults to "user" (human-readable output),
    but can alternatively be "json", "yaml", or "shell", if the user specifies
    one of the style arguments which the :meth:`add_style_arg` can be used to
    create.
    """
    def __init__(self, default_style='user', use_unicode=None):
        self.style = default_style
        locale.setlocale(locale.LC_ALL, '')
        if use_unicode is None:
            use_unicode = locale.nl_langinfo(locale.CODESET) == 'UTF-8'
        if use_unicode:
            self._table_style = unicode_table
            self._check_mark = '✓'
        else:
            self._table_style = pretty_table
            self._check_mark = 'x'

    @classmethod
    def add_style_arg(cls, parser, *, required=False):
        """
        Create a mutually exclusive :mod:`argparse` group and add to it options
        for the various input and output styles supported by this class.
        """
        parser.set_defaults(style="user")
        fmt_group = parser.add_mutually_exclusive_group(required=required)
        fmt_group.add_argument(
            "--json", dest="style", action="store_const", const="json",
            help=_("Use JSON as the format"))
        fmt_group.add_argument(
            "--yaml", dest="style", action="store_const", const="yaml",
            help=_("Use YAML as the format"))
        fmt_group.add_argument(
            "--shell", dest="style", action="store_const", const="shell",
            help=_("Use a var=value or tab-delimited format suitable for the "
                   "shell"))
        return fmt_group

    def dump_store(self, store, fp):
        """
        Write the content of *store* (a sequence of (name, active, timestamp)
        triples) to the file-like object *fp*.
        """
        return {
            'user':  self._dump_store_user,
            'shell': self._dump_store_shell,
            'json':  self._dump_store_json,
            'yaml':  self._dump_store_yaml,
        }[self.style](store, fp)

    def _dump_store_user(self, store, fp):
        if not store:
            fp.write(_("No stored boot configurations found"))
            fp.write("\n")
        else:
            self._print_table([
                (_('Name'), _('Active'), _('Timestamp'))
            ] + [
                (name, self._check_mark if active else '',
                 timestamp.strftime('%Y-%m-%d %H:%M:%S'))
                for name, active, timestamp in store
            ], fp)

    def _dump_store_json(self, store, fp):
        json.dump([
            {'name': name, 'active': active, 'timestamp': timestamp.isoformat()}
            for name, active, timestamp in store
        ], fp)

    def _dump_store_yaml(self, store, fp):
        yaml.dump([
            {'name': name, 'active': active, 'timestamp': timestamp}
            for name, active, timestamp in store
        ], fp)

    def _dump_store_shell(self, store, fp):
        for name, active, timestamp in store:
            fp.write('\t'.join(
                (timestamp.isoformat(), ('inactive', 'active')[active], name)
            ))
            fp.write('\n')

    def dump_diff(self, left, right, diff, fp):
        """
        Write the *diff* (a sequence of (l, r) tuples in which l and r are
        either instances of :class:`Setting` or :data:`None`), of *left*
        and *right* (instances of :class:`Settings`) to the file-like object
        *fp*.
        """
        return {
            'user':  self._dump_diff_user,
            'shell': self._dump_diff_shell,
            'json':  self._dump_diff_json,
            'yaml':  self._dump_diff_yaml,
        }[self.style](left, right, diff, fp)

    def _dump_diff_user(self, left, right, diff, fp):
        if not diff:
            fp.write(
                _("No differences between {left} and {right}").format(
                    left=_('Current') if left is None else left,
                    right=right))
            fp.write("\n")
        else:
            self._print_table([
                (_('Name'), '<{}>'.format(_('Current')) if left is None else left, right)
            ] + sorted([
                (l.name if l is not None else r.name,
                 '-' if l is None else self._format_setting_user(l),
                 '-' if r is None else self._format_setting_user(r),
                 )
                for (l, r) in diff
            ]), fp)

    def _dump_diff_json(self, left, right, diff, fp):
        json.dump({
            (l.name if l is not None else r.name): values(l, r)
            for (l, r) in diff
        }, fp)

    def _dump_diff_yaml(self, left, right, diff, fp):
        yaml.dump({
            (l.name if l is not None else r.name): values(l, r)
            for (l, r) in diff
        }, fp)

    def _dump_diff_shell(self, left, right, diff, fp):
        for l, r in diff:
            fp.write('\t'.join(
                (l.name if l is not None else r.name,
                 '-' if l is None else self._format_value_shell(l.value),
                 '-' if r is None else self._format_value_shell(r.value)
                 )
            ))
            fp.write('\n')

    def dump_settings(self, settings, fp, mod=False):
        """
        Write the content of *settings* (a :class:`Settings` instance or just a
        mapping of settings names to :class:`Setting` objects) to the file-like
        object *fp*.
        """
        return {
            'user':  self._dump_settings_user,
            'shell': self._dump_settings_shell,
            'json':  self._dump_settings_json,
            'yaml':  self._dump_settings_yaml,
        }[self.style](settings, fp, mod=mod)

    def _dump_settings_json(self, settings, fp, mod=False):
        json.dump({
            name: setting.value for name, setting in settings.items()
        }, fp)

    def _dump_settings_yaml(self, settings, fp, mod=False):
        yaml.dump({
            name: setting.value for name, setting in settings.items()
        }, fp)

    def _dump_settings_shell(self, settings, fp, mod=False):
        for setting in settings.values():
            fp.write(self._format_setting_shell(setting))
            fp.write("\n")

    def _dump_settings_user(self, settings, fp, mod=False):
        if not settings:
            fp.write(_("No settings matching the pattern found"))
            fp.write("\n")
        else:
            data = [
                (_('Name'), _('Modified'), _('Value'))
            ] + [
                (
                    setting.name,
                    self._check_mark if setting.modified else '',
                    self._format_setting_user(setting),
                )
                for setting in sorted(
                    settings.values(), key=attrgetter('name'))
            ]
            if not mod:
                data = [(name, value) for (name, modified, value) in data]
            self._print_table(data, fp)

    def load_settings(self, fp):
        """
        Load a dictionary of settings values from the file-like object *fp*.
        """
        return {
            'user':  self._load_settings_user,
            'json':  self._load_settings_json,
            'yaml':  self._load_settings_yaml,
            'shell': self._load_settings_shell,
        }[self.style](fp)

    def _load_settings_json(self, fp):
        return json.load(fp)

    def _load_settings_yaml(self, fp):
        return yaml.load(fp, Loader=yaml.SafeLoader)

    def _load_settings_shell(self, fp):
        # TODO
        raise NotImplementedError

    def _load_settings_user(self, fp):
        raise NotImplementedError

    def format_value(self, value):
        """
        Return *value* (typically an :class:`int` or :class:`str`) formatted
        for output in the selected :attr:`style`.
        """
        return {
            'user':  self._format_value_user,
            'shell': self._format_value_shell,
            'json':  self._format_value_json,
            'yaml':  self._format_value_yaml,
        }[self.style](value)

    def _format_value_json(self, value):
        return json.dumps(value)

    def _format_value_yaml(self, value):
        with io.StringIO() as fp:
            yaml.dump(value, fp)
            return fp.getvalue()

    def _format_value_shell(self, value):
        if value is None:
            return 'auto'
        elif isinstance(value, bool):
            return ('off', 'on')[value]
        elif isinstance(value, list):
            return '({})'.format(' '.join(
                self._format_value_shell(e) for e in value
            ))
        else:
            return shlex.quote(str(value))

    def _format_value_user(self, value):
        if value is None:
            return _('auto')
        elif isinstance(value, bool):
            return (_('off'), _('on'))[value]
        elif isinstance(value, str):
            return repr(value)
        else:
            return str(value)

    def _print_table(self, table, fp):
        width = min(120, term_size()[0])
        renderer = TableWrapper(width=width, **self._table_style)
        for line in renderer.wrap(table):
            fp.write(line)
            fp.write('\n')

    def dump_setting(self, setting, fp):
        assert self.style == 'user'
        width = min(120, term_size()[0])
        fields = [
            (_('Name'), setting.name),
            (_('Default'), self._format_setting_user(setting)),
        ]
        if isinstance(setting, Command):
            fields += [
                (_('Command(s)'), ', '.join(setting.commands))
            ]
        elif isinstance(setting, OverlayParam):
            fields += [
                (_('Overlay'), setting.overlay),
                (_('Parameter'), setting.param),
            ]
        max_field_width = max(len(name) for name, value in fields)
        fp.write('{fields}\n\n{doc}\n'.format(
            fields='\n'.join(
                '{name:>{width}}: {value}'.format(
                    name=name, width=max_field_width, value=value)
                for name, value in fields
            ),
            doc=render(setting.doc, width=width, table_style=self._table_style),
        ))

    def _format_setting_shell(self, setting):
        return '{name}={value}'.format(
            name=setting.name.replace('.', '_'),
            value=self._format_value_shell(setting.value)
        )

    def _format_setting_user(self, setting):
        value = self._format_value_user(setting.value)
        return (
            '{value}' if setting.hint is None else
            '{value} ({setting.hint})'
        ).format(value=value, setting=setting)
