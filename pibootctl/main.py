"""
The :mod:`pibootctl.main` module defines the :class:`Application` class, and an
instance of this called :data:`main`. Instances of :class:`Application` are
callable and thus :data:`main` is the entry-point for the :doc:`pibootctl
<manual>` script.

This module is primarily useful for obtaining the necessary configuration for
constructing a :class:`~pibootctl.store.Store`::

    from pibootctl.main import Application
    from pibootctl.store import Store, Current, Default

    config = Application.get_config()
    store = Store(
        config.boot_path, config.store_path,
        config.config_read, config.config_write)
    store[Current] = store['foo']

Note that :meth:`Application.get_config` is static, so it can be called on the
:class:`Application` class or the :data:`main` instance.

.. data:: main

    The instance of :class:`Application` which is the entry-point for the
    :doc:`pibootctl <manual>` script.

.. autoclass:: Application
    :members:
"""

import io
import os
import sys
import gettext
import argparse
import subprocess
import configparser
from datetime import datetime

import pkg_resources

from .setting import Command
from .store import Store, Current, Default
from .term import ErrorHandler, pager
from .userstr import UserStr
from .output import Output

try:
    import argcomplete
except ImportError:
    argcomplete = None


_ = gettext.gettext


def permission_error(exc_type, exc_value, exc_tb):
    msg = [str(exc_value)]
    if os.geteuid() != 0:
        msg.append(_(
            "You need root permissions to modify the boot configuration or "
            "stored boot configurations"))
    return msg


class Application:
    """
    An instance of this class (:data:`main`) is the entry point for the
    application. The instance is callable, accepting the command line arguments
    as its single (optional) argument. The arguments will be derived from
    :data:`sys.argv` if not provided::

        >>> from pibootctl.main import main
        >>> try:
        ...     main(['-h'])
        ... except SystemExit:
        ...     pass
        usage:  [-h] [--version]
        {help,?,status,dump,get,set,save,load,diff,show,cat,list,ls,remove,rm,rename,mv}
        ...

    .. warning::

        Calling :data:`main` will raise :exc:`SystemExit` in several cases
        (usually when requesting help output). It will also replace the system
        exception hook (:func:`sys.excepthook`).

        This is intended and by design. If you wish to use :doc:`pibootctl
        <manual>` as an API, you are better off investigating the
        :class:`~pibootctl.store.Store` class, or treating :doc:`pibootctl
        <manual>` as a self-contained script and calling it with
        :mod:`subprocess`.
    """
    def __call__(self, args=None):
        if not int(os.environ.get('DEBUG', '0')):
            sys.excepthook = ErrorHandler()
            sys.excepthook[PermissionError] = (permission_error, 1)
            sys.excepthook[Exception] = (sys.excepthook.exc_message, 1)
        with pager():
            self.parser = self.get_parser()
            self.config = self.parser.parse_args(args)
            self.output = Output(
                self.config.style if 'style' in self.config else 'user')
            self.store = Store(
                self.config.boot_path, self.config.store_path,
                self.config.config_read, self.config.config_write)
            self.config.func()

    @staticmethod
    def get_config():
        """
        Constructs a configuration parser, and attempts to read the script's
        configuration from the three pre-defined locations. Returns the content
        of the ``[defaults]`` section.
        """
        config = configparser.ConfigParser(
            defaults={
                'boot_path':             '/boot',
                'store_path':            'pibootctl',
                'config_read':           'config.txt',
                'config_write':          'config.txt',
                'backup':                'on',
                'package_name':          'pibootctl',
                'reboot_required':       '/var/run/reboot-required',
                'reboot_required_pkgs':  '/var/run/reboot-required.pkgs',
            },
            default_section='defaults',
            delimiters=('=',),
            comment_prefixes=('#',),
            interpolation=None)
        config.read(
            [
                '/lib/pibootctl/pibootctl.conf',
                '/etc/pibootctl.conf',
                '{xdg_config}/pibootctl.conf'.format(
                    xdg_config=os.environ.get(
                        'XDG_CONFIG_HOME', os.path.expanduser('~/.config'))),
            ],
            encoding='ascii')
        return config['defaults']

    def get_parser(self):
        """
        Returns a parser for all the sub-commands that the script accepts.

        This also implicitly constructs a configuration parser (to provide
        defaults for the various command line options). Returns the newly
        constructed argument parser.
        """
        pkg = pkg_resources.require('pibootctl')[0]
        config = self.get_config()

        parser = argparse.ArgumentParser(
            description=_(
                "%(prog)s is a tool for querying and modifying the boot "
                "configuration of the Raspberry Pi."))
        parser.add_argument(
            '--version', action='version', version=pkg.version)
        parser.set_defaults(
            func=self.do_help,
            boot_path=config['boot_path'],
            store_path=config['store_path'],
            config_read=config['config_read'],
            config_write=config['config_write'],
            backup=config.getboolean('backup'),
            package_name=config['package_name'],
            reboot_required=config['reboot_required'],
            reboot_required_pkgs=config['reboot_required_pkgs'])
        commands = parser.add_subparsers(title=_("commands"))

        help_cmd = commands.add_parser(
            "help", aliases=["?"],
            description=_(
                "With no arguments, displays the list of pibootctl commands. "
                "If a command name is given, displays the description and "
                "options for the named command. If a setting name is given, "
                "displays the description and default value for that "
                "setting."),
            help=_("Displays help about the specified command or setting"))
        help_cmd.add_argument(
            "cmd", metavar="command-or-setting", nargs='?',
            help=_(
                "The name of the command or setting to output help for"))
        help_cmd.set_defaults(func=self.do_help)

        dump_cmd = commands.add_parser(
            "status", aliases=["dump"],
            description=_(
                "Output the current value of modified boot time settings that "
                "match the specified pattern (or all if no pattern is "
                "provided)."),
            help=_("Output the current boot time configuration"))
        dump_cmd.add_argument(
            "vars", nargs="?", metavar="pattern",
            help=_(
                "If specified, only displays settings with names that match "
                "the specified pattern which may include shell globbing "
                "characters (e.g. *, ?, and simple [classes])"))
        dump_cmd.add_argument(
            "-a", "--all", action="store_true",
            help=_(
                "Include all settings, regardless of modification, in the "
                "output; by default, only settings which have been modified "
                "are included"))
        Output.add_style_arg(dump_cmd)
        dump_cmd.set_defaults(func=self.do_status)

        get_cmd = commands.add_parser(
            "get",
            description=_(
                "Query the status of one or more boot configuration settings. "
                "If a single setting is requested then just that value is "
                "output. If multiple values are requested then both setting "
                "names and values are output. This applies whether output is "
                "in the default, JSON, YAML, or shell-friendly styles."),
            help=_("Query the state of one or more boot settings"))
        get_cmd.add_argument(
            "get_vars", nargs="+", metavar="setting",
            help=_(
                "The name(s) of the setting(s) to query; if a single setting "
                "is given its value alone is output, if multiple settings "
                "are queried the names and values of the settings are "
                "output"))
        Output.add_style_arg(get_cmd)
        get_cmd.set_defaults(func=self.do_get)

        set_cmd = commands.add_parser(
            "set",
            description=_(
                "Change the value of one or more boot configuration settings. "
                "To reset the value of a setting to its default, simply omit "
                "the new value."),
            help=_("Change the state of one or more boot settings"))
        set_cmd.add_argument(
            "--no-backup", action="store_false", dest="backup",
            help=_(
                "Don't take an automatic backup of the current boot "
                "configuration if one doesn't exist"))
        group = Output.add_style_arg(set_cmd, required=True)
        group.add_argument(
            "set_vars", nargs="*", metavar="name=[value]", default=[],
            help=_(
                "Specify one or more settings to change on the command line; "
                "to reset a setting to its default omit the value"))
        set_cmd.set_defaults(func=self.do_set)

        save_cmd = commands.add_parser(
            "save",
            description=_(
                "Store the current boot configuration under a given name."),
            help=_("Store the current boot configuration for later use"))
        save_cmd.add_argument(
            "name",
            help=_(
                "The name to save the current boot configuration under; can "
                "include any characters legal in a filename"))
        save_cmd.add_argument(
            "-f", "--force", action="store_true",
            help=_(
                "Overwrite an existing configuration, if one exists"))
        save_cmd.set_defaults(func=self.do_save)

        load_cmd = commands.add_parser(
            "load",
            description=_(
                "Overwrite the current boot configuration with a stored one."),
            help=_("Replace the boot configuration with a saved one"))
        load_cmd.add_argument(
            "name",
            help=_("The name of the boot configuration to restore"))
        load_cmd.add_argument(
            "--no-backup", action="store_false", dest="backup",
            help=_(
                "Don't take an automatic backup of the current boot "
                "configuration if one doesn't exist"))
        load_cmd.set_defaults(func=self.do_load)

        diff_cmd = commands.add_parser(
            "diff",
            description=_(
                "Display the settings that differ between two stored boot "
                "configurations, or between one stored boot configuration and "
                "the current configuration."),
            help=_("Show the differences between boot configurations"))
        diff_cmd.add_argument(
            "left", nargs="?", default=Current,
            help=_(
                "The boot configuration to compare from, or the current "
                "configuration if omitted"))
        diff_cmd.add_argument(
            "right",
            help=_("The boot configuration to compare against"))
        Output.add_style_arg(diff_cmd)
        diff_cmd.set_defaults(func=self.do_diff)

        show_cmd = commands.add_parser(
            "show", aliases=["cat"],
            description=_(
                "Display the specified stored boot configuration, or the "
                "sub-set of its settings that match the specified pattern."),
            help=_("Show the specified stored configuration"))
        show_cmd.add_argument(
            "name",
            help=_("The name of the boot configuration to display"))
        show_cmd.add_argument(
            "vars", nargs="?", metavar="pattern",
            help=_(
                "If specified, only displays settings with names that match "
                "the specified pattern which may include shell globbing "
                "characters (e.g. *, ?, and simple [classes])"))
        show_cmd.add_argument(
            "-a", "--all", action="store_true",
            help=_(
                "Include all settings, regardless of modification, in the "
                "output; by default, only settings which have been modified "
                "are included"))
        Output.add_style_arg(show_cmd)
        show_cmd.set_defaults(func=self.do_show)

        ls_cmd = commands.add_parser(
            "list", aliases=["ls"],
            description=_("List all stored boot configurations."),
            help=_("List the stored boot configurations"))
        Output.add_style_arg(ls_cmd)
        ls_cmd.set_defaults(func=self.do_list)

        rm_cmd = commands.add_parser(
            "remove", aliases=["rm"],
            description=_("Remove a stored boot configuration."),
            help=_("Remove a stored boot configuration"))
        rm_cmd.add_argument(
            "name",
            help=_("The name of the boot configuration to remove"))
        rm_cmd.add_argument(
            "-f", "--force", action="store_true",
            help=_(
                "Ignore errors if the named configuration does not exist"))
        rm_cmd.set_defaults(func=self.do_remove)

        mv_cmd = commands.add_parser(
            "rename", aliases=["mv"],
            description=_("Rename a stored boot configuration."),
            help=_("Rename a stored boot configuration"))
        mv_cmd.add_argument(
            "name",
            help=_("The name of the boot configuration to rename"))
        mv_cmd.add_argument(
            "to",
            help=_("The new name of the boot configuration"))
        mv_cmd.add_argument(
            "-f", "--force", action="store_true",
            help=_(
                "Overwrite the target configuration, if it exists"))
        mv_cmd.set_defaults(func=self.do_rename)

        return parser

    def do_help(self):
        """
        Implementation of the :doc:`help` command.
        """
        default = self.store[Default].settings
        if 'cmd' in self.config and self.config.cmd is not None:
            if self.config.cmd in default:
                self.output.dump_setting(default[self.config.cmd],
                                         fp=sys.stdout)
                raise SystemExit(0)
            elif '.' in self.config.cmd:
                # TODO Mis-spelled setting; use something like levenshtein to
                # detect "close" but incorrect setting names
                raise ValueError(_(
                    'Unknown setting "{self.config.cmd}"').format(self=self))
            elif '_' in self.config.cmd:
                # Old-style command
                commands = [
                    setting
                    for setting in default.values()
                    if isinstance(setting, Command)
                    and self.config.cmd in setting.commands
                ]
                if len(commands) == 1:
                    self.output.dump_setting(commands[0], fp=sys.stdout)
                else:
                    print(_(
                        '{self.config.cmd} is affected by the following '
                        'settings:\n\n'
                        '{settings}').format(
                            self=self, settings='\n'.join(
                                setting.name for setting in commands)))
                raise SystemExit(0)
            else:
                self.parser.parse_args([self.config.cmd, '-h'])
        else:
            self.parser.parse_args(['-h'])

    def do_status(self):
        """
        Implementation of the :doc:`status` command.
        """
        self.config.name = Current
        self.do_show()

    def do_show(self):
        """
        Implementation of the :doc:`show` command.
        """
        settings = self.store[self.config.name].settings
        if self.config.vars:
            settings = settings.filter(self.config.vars)
        if not self.config.all:
            settings = settings.modified()
        self.output.dump_settings(settings, fp=sys.stdout, mod=self.config.all)

    def do_get(self):
        """
        Implementation of the :doc:`get` command.
        """
        current = self.store[Current]
        if len(self.config.get_vars) == 1:
            try:
                print(self.output.format_value(
                    current.settings[self.config.get_vars[0]].value))
            except KeyError:
                raise ValueError(_(
                    'unknown setting: {}').format(self.config.get_vars[0]))
        else:
            settings = {}
            for var in self.config.get_vars:
                try:
                    settings[var] = current.settings[var]
                except KeyError:
                    raise ValueError(_('unknown setting: {}').format(var))
            self.output.dump_settings(settings, fp=sys.stdout)

    def do_set(self):
        """
        Implementation of the :doc:`set` command.
        """
        mutable = self.store[Current].mutable()
        if self.config.style == 'user':
            settings = {}
            for var in self.config.set_vars:
                if not '=' in var:
                    raise ValueError(_('expected "=" in {}').format(var))
                name, value = var.split('=', 1)
                settings[name] = UserStr(value)
        else:
            settings = self.output.load_settings(sys.stdin)
        mutable.update(settings)
        self.backup_if_needed()
        self.store[Current] = mutable
        self.mark_reboot_required()

    def do_save(self):
        """
        Implementation of the :doc:`save` command.
        """
        try:
            self.store[self.config.name] = self.store[Current]
        except FileExistsError:
            if not self.config.force:
                raise
            del self.store[self.config.name]
            self.store[self.config.name] = self.store[Current]

    def do_load(self):
        """
        Implementation of the :doc:`load` command.
        """
        # Look up the config to load before we do any backups, just in case the
        # user's made a mistake and the config doesn't exist
        to_load = self.store[self.config.name]
        self.backup_if_needed()
        self.store[Current] = to_load
        self.mark_reboot_required()

    def do_diff(self):
        """
        Implementation of the :doc:`diff` command.
        """
        # Keep references to the settings lying around while we dump the diff
        # as otherwise the settings lose their weak-ref during the dump
        left = self.store[self.config.left].settings
        right = self.store[self.config.right].settings
        self.output.dump_diff(
            self.config.left, self.config.right, left.diff(right),
            fp=sys.stdout)

    def do_list(self):
        """
        Implementation of the :doc:`list` command.
        """
        current = self.store[Current]
        table = [
            (key, value.hash == current.hash, value.timestamp)
            for key, value in self.store.items()
            if key not in (Current, Default)
        ]
        self.output.dump_store(table, fp=sys.stdout)

    def do_remove(self):
        """
        Implementation of the :doc:`remove` command.
        """
        try:
            del self.store[self.config.name]
        except KeyError:
            if not self.config.force:
                raise FileNotFoundError(_(
                    'unknown configuration {}').format(self.config.name))

    def do_rename(self):
        """
        Implementation of the :doc:`rename` command.
        """
        try:
            self.store[self.config.to] = self.store[self.config.name]
        except FileExistsError:
            if not self.config.force:
                raise
            del self.store[self.config.to]
            self.store[self.config.to] = self.store[self.config.name]
        del self.store[self.config.name]

    def backup_if_needed(self):
        """
        Tests whether the active boot configuration is also present in the
        store (by checking for the calculated hash). If it isn't, constructs
        a unique filename (backup-<timestamp>) and saves a copy of the active
        boot configuration under it.
        """
        if self.config.backup and self.store.active is None:
            name = 'backup-{now:%Y%m%d-%H%M%S}'.format(now=datetime.now())
            suffix = 0
            while True:
                try:
                    self.store[name] = self.store[Current]
                except FileExistsError:
                    # Pi's clocks can be very wrong when there's no network;
                    # this just exists to guarantee that we won't try and
                    # clobber an existing backup
                    suffix += 1
                    name = 'backup-{now:%Y%m%d-%H%M%S}-{suffix}'.format(
                        now=datetime.now(), suffix=suffix)
                else:
                    print(_(
                        'Backed up current configuration in {name}').format(
                            name=name), file=sys.stderr)
                    break

    def mark_reboot_required(self):
        """
        Writes the necessary files to indicate that the system requires a
        reboot.
        """
        if self.config.reboot_required:
            with io.open(self.config.reboot_required, 'w') as f:
                f.write('*** ')
                f.write(_('System restart required'))
                f.write(' ***\n')
        if self.config.reboot_required_pkgs and self.config.package_name:
            with io.open(self.config.reboot_required_pkgs, 'a') as f:
                f.write(self.config.package_name)
                f.write('\n')


main = Application()
