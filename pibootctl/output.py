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

"""
The :mod:`pibootctl.output` module defines the :class:`Output` class which is
responsible for rendering various structures (the store list, diff output,
etc.) in a selected style (JSON, YAML, user-friendly, etc.); it also provides a
class method to add the supported styles to an
:class:`~argparse.ArgumentParser`.

.. autoclass:: Output
    :members:
"""

import io
import json
import shlex
import gettext
from operator import attrgetter, itemgetter

import yaml

from .store import Current
from .setting import Command, OverlayParam
from .formatter import TableWrapper, unicode_table, pretty_table, render
from .term import term_size, term_is_utf8

_ = gettext.gettext


def values(left, right):
    """
    Utility function for JSON/YAML output; generates a dict containing *left*
    and *right* for non-:data:`None` values.
    """
    obj = {}
    if left is not None:
        obj['left'] = left.value
    if right is not None:
        obj['right'] = right.value
    return obj


class Output:
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
    def __init__(self, style='user', use_unicode=None):
        self.style = style
        if use_unicode is None:
            use_unicode = term_is_utf8()
        if use_unicode:
            self._table_style = unicode_table
            self._check_mark = '✓'
        else:
            self._table_style = pretty_table
            self._check_mark = 'x'

    @staticmethod
    def add_style_arg(parser, *, required=False):
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

    def dump_store(self, store, file):
        """
        Write the content of *store* (a sequence of (name, active, timestamp)
        triples) to the file-like object *file*.
        """
        return {
            'user':  self._dump_store_user,
            'shell': self._dump_store_shell,
            'json':  self._dump_store_json,
            'yaml':  self._dump_store_yaml,
        }[self.style](store, file)

    def _dump_store_user(self, store, file):
        if not store:
            file.write(_("No stored boot configurations found"))
            file.write("\n")
        else:
            self._print_table([
                (_('Name'), _('Active'), _('Timestamp'))
            ] + [
                (name, self._check_mark if active else '',
                 timestamp.strftime('%Y-%m-%d %H:%M:%S'))
                for name, active, timestamp in sorted(store, key=itemgetter(0))
            ], file)

    @staticmethod
    def _dump_store_json(store, file):
        json.dump([
            {'name': name, 'active': active, 'timestamp': timestamp.isoformat()}
            for name, active, timestamp in store
        ], file)

    @staticmethod
    def _dump_store_yaml(store, file):
        yaml.dump([
            {'name': name, 'active': active, 'timestamp': timestamp}
            for name, active, timestamp in store
        ], file)

    @staticmethod
    def _dump_store_shell(store, file):
        for name, active, timestamp in store:
            file.write('\t'.join(
                (timestamp.isoformat(), ('inactive', 'active')[active], name)
            ))
            file.write('\n')

    def dump_diff(self, left, right, diff, file):
        """
        Write the *diff* (a sequence of (l, r) tuples in which l and r are
        either instances of :class:`Setting` or :data:`None`), of *left*
        and *right* (instances of :class:`Settings`) to the file-like object
        *file*.
        """
        return {
            'user':  self._dump_diff_user,
            'shell': self._dump_diff_shell,
            'json':  self._dump_diff_json,
            'yaml':  self._dump_diff_yaml,
        }[self.style](left, right, diff, file)

    def _dump_diff_user(self, left, right, diff, file):
        if not diff:
            file.write(_(
                "No differences between {left} and {right}").format(
                    left='<{}>'.format(_('Current')) if left is Current else left,
                    right=right))
            file.write("\n")
        else:
            self._print_table([
                (_('Name'),
                 '<{}>'.format(_('Current')) if left is Current else left,
                 right,
                 )
            ] + sorted([
                (l.name if l is not None else r.name,
                 '-' if l is None else self.format_setting_user(l),
                 '-' if r is None else self.format_setting_user(r),
                 )
                for (l, r) in diff
            ]), file)

    @staticmethod
    def _dump_diff_json(left, right, diff, file):
        json.dump({
            (l.name if l is not None else r.name): values(l, r)
            for (l, r) in diff
        }, file)

    @staticmethod
    def _dump_diff_yaml(left, right, diff, file):
        yaml.dump({
            (l.name if l is not None else r.name): values(l, r)
            for (l, r) in diff
        }, file)

    @staticmethod
    def _dump_diff_shell(left, right, diff, file):
        file.write(
            ''.join(
                '\t'.join(
                    (l.name if l is not None else r.name,
                     '-' if l is None else Output._format_value_shell(l.value),
                     '-' if r is None else Output._format_value_shell(r.value)
                     )
                ) + '\n'
                for l, r in diff
            ))

    def dump_settings(self, settings, file, mod_only=True):
        """
        Write the content of *settings* (a :class:`Settings` instance or just a
        mapping of settings names to :class:`Setting` objects) to the file-like
        object *file*.
        """
        return {
            'user':  self._dump_settings_user,
            'shell': self._dump_settings_shell,
            'json':  self._dump_settings_json,
            'yaml':  self._dump_settings_yaml,
        }[self.style](settings, file, mod_only=mod_only)

    @staticmethod
    def _dump_settings_json(settings, file, mod_only=True):
        json.dump({
            name: setting.value for name, setting in settings.items()
        }, file)

    @staticmethod
    def _dump_settings_yaml(settings, file, mod_only=True):
        yaml.dump({
            name: setting.value for name, setting in settings.items()
        }, file)

    def _dump_settings_shell(self, settings, file, mod_only=True):
        for setting in settings.values():
            file.write(self._format_setting_shell(setting))
            file.write("\n")

    def _dump_settings_user(self, settings, file, mod_only=True):
        if not settings:
            file.write(_(
                "No modified settings matching the pattern found.\n"))
            if mod_only:
                file.write(_("Try --all to include unmodified settings.\n"))
        else:
            data = [
                (_('Name'), _('Modified'), _('Value'))
            ] + [
                (
                    setting.name,
                    self._check_mark if setting.modified else '',
                    self.format_setting_user(setting),
                )
                for setting in sorted(
                    settings.values(), key=attrgetter('name'))
            ]
            if mod_only:
                data = [(name, value) for (name, modified, value) in data]
            self._print_table(data, file)

    def load_settings(self, file):
        """
        Load a dictionary of settings values from the file-like object *file*.
        """
        return {
            'user':  self._load_settings_user,
            'json':  self._load_settings_json,
            'yaml':  self._load_settings_yaml,
            'shell': self._load_settings_shell,
        }[self.style](file)

    @staticmethod
    def _load_settings_json(file):
        return json.load(file)

    @staticmethod
    def _load_settings_yaml(file):
        return yaml.load(file, Loader=yaml.SafeLoader)

    @staticmethod
    def _load_settings_shell(file):
        def parse(value):
            if value in {'false', 'true'}:
                return value == 'true'
            elif value.isdigit():
                return int(value)
            elif value.startswith('(') and value.endswith(')'):
                return [
                    parse(shlex.quote(item))
                    for item in shlex.split(value[1:-1])
                ]
            else:
                return shlex.split(value)[0]

        data = file.read().splitlines()
        if len(data) == 1:
            if '=' not in data[0]:
                return parse(data[0])
        return {
            key.replace('_', '.'): parse(value)
            for line in data
            for key, value in (line.split('=', 1),)
        }

    @staticmethod
    def _load_settings_user(file):
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

    @staticmethod
    def _format_value_json(value):
        return json.dumps(value)

    @staticmethod
    def _format_value_yaml(value):
        with io.StringIO() as file:
            yaml.dump(value, file)
            return file.getvalue()

    @staticmethod
    def _format_value_shell(value):
        if value is None:
            return 'auto'
        elif isinstance(value, bool):
            return ('false', 'true')[value]
        elif isinstance(value, list):
            return '({})'.format(' '.join(
                Output._format_value_shell(e) for e in value
            ))
        else:
            return shlex.quote(str(value))

    @staticmethod
    def _format_value_user(value):
        if value is None:
            return _('auto')
        elif isinstance(value, bool):
            return (_('off'), _('on'))[value]
        elif isinstance(value, str):
            return repr(value)
        else:
            return str(value)

    def _print_table(self, table, file):
        width = min(120, term_size()[0])
        renderer = TableWrapper(width=width, **self._table_style)
        for line in renderer.wrap(table):
            file.write(line)
            file.write('\n')

    def dump_setting(self, setting, file):
        """
        Output a help page describing the *setting* with information on the
        underlying configuration command or overlay, the default value, and
        a verbose description.
        """
        assert self.style == 'user'
        width = min(120, term_size()[0])
        fields = [
            (_('Name'), setting.name),
            (_('Default'), self.format_setting_user(setting)),
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
        file.write('{fields}\n\n{doc}\n'.format(
            fields='\n'.join(
                '{name:>{width}}: {value}'.format(
                    name=name, width=max_field_width, value=value)
                for name, value in fields
            ),
            doc=render(setting.doc, width=width, table_style=self._table_style),
        ))

    @staticmethod
    def _format_setting_shell(setting):
        return '{name}={value}'.format(
            name=setting.name.replace('.', '_'),
            value=Output._format_value_shell(setting.value)
        )

    @staticmethod
    def format_setting_user(setting):
        """
        Output the value of *setting* in "human readable" style, with the
        optional :attr:`~Setting.hint` in parentheses.
        """
        value = Output._format_value_user(setting.value)
        return (
            '{value}' if setting.hint is None else
            '{value} ({setting.hint})'
        ).format(value=value, setting=setting)
