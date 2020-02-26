import io
import os
import sys
import errno
import gettext
import argparse
import configparser
from pathlib import Path
from datetime import datetime

from .setting import Command
from .store import Store, Current, Default
from .term import ErrorHandler
from .userstr import UserStr
from .output import OutputNamespace

try:
    import argcomplete
except ImportError:
    argcomplete = None


_ = gettext.gettext


def main(args=None):
    if not int(os.environ.get('DEBUG', '0')):
        sys.excepthook = ErrorHandler()
        sys.excepthook[PermissionError] = (permission_error, 1)
        sys.excepthook[Exception] = (sys.excepthook.exc_message, 1)
    app = ApplicationNamespace()
    parser = app.get_parser()
    parser.parse_args(args, namespace=app)
    app.run()


def permission_error(exc_type, exc_value, exc_tb):
    msg = [exc_value]
    if os.geteuid() != 0:
        msg.append(_(
            "You need root permissions to modify the boot configuration or "
            "stored boot configurations"))
    return msg


class ApplicationNamespace(OutputNamespace):
    def get_parser(self):
        config = configparser.ConfigParser(
            defaults={
                'boot_path':             '/boot',
                'store_path':            '/boot/pictl',
                'config_read':           'config.txt',
                'config_write':          'config.txt',
                'backup':                'on',
                'package_name':          'pictl',
                'reboot_required':       '/var/run/reboot-required',
                'reboot_required_pkgs':  '/var/run/reboot-required.pkgs',
            },
            default_section='defaults',
            delimiters=('=',),
            comment_prefixes=('#',),
            interpolation=None)
        config.read(
            [
                '/etc/pictl.conf',
                '{xdg_config}/pictl.conf'.format(
                    xdg_config=os.environ.get(
                        'XDG_CONFIG_HOME', os.path.expanduser('~/.config'))),
            ],
            encoding='ascii')
        section = config['defaults']

        parser = argparse.ArgumentParser(
            description=_(
                "pictl is a tool for querying and modifying the boot "
                "configuration of the Raspberry Pi"))
        parser.add_argument(
            '--version', action='version', version='0.1')
        parser.add_argument(
            '-B', '--boot-path', metavar='DIR', type=Path,
            default=section['boot_path'],
            help=_(
                "The path on which the boot partition is mounted. Defaults to "
                "%(default)r."))
        parser.add_argument(
            '-r', '--config-read', metavar='FILE', type=Path,
            default=section['config_read'],
            help=_(
                "The name of the config.txt file read by the bootloader, "
                "relative to --boot-path. Defaults to %(default)r."))
        parser.add_argument(
            '-w', '--config-write', metavar='FILE', type=Path,
            default=section['config_write'],
            help=_(
                "The name of the config.txt file written by this tool, "
                "relative to --boot-path. Defaults to %(default)r."))
        parser.add_argument(
            '-s', '--store-path', metavar='DIR', type=Path,
            default=section['store_path'],
            help=_(
                "The path in which to store saved boot configurations. "
                "Defaults to %(default)r."))
        parser.set_defaults(
            func=self.do_help,
            backup=section.getboolean('backup'),
            package_name=section['package_name'],
            reboot_required=section['reboot_required'],
            reboot_required_pkgs=section['reboot_required_pkgs'])
        commands = parser.add_subparsers(title=_("commands"))

        help_cmd = commands.add_parser(
            "help", aliases=["?"],
            description=_(
                "Displays help about the specified command or setting, or "
                "about all commands if none is given."),
            help=_("Displays help about the specified command or setting"))
        help_cmd.add_argument("cmd", nargs='?')
        help_cmd.set_defaults(func=self.do_help)

        dump_cmd = commands.add_parser(
            "status", aliases=["dump"],
            description=_(
                "Output the current value of modified boot time settings that "
                "match the specified pattern (or all if no pattern is "
                "provided)"),
            help=_("Output the current boot time configuration"))
        dump_cmd.add_argument("vars", nargs="?", metavar="pattern")
        dump_cmd.add_argument(
            "-a", "--all", action="store_true",
            help=_(
                "Include all settings, regardless of modification, in the "
                "output"))
        self.add_style_arg(dump_cmd)
        dump_cmd.set_defaults(func=self.do_dump)

        get_cmd = commands.add_parser(
            "get",
            description=_(
                "Query the status of one or more boot configuration values. "
                "When outputting in JSON, YAML, or shell format, if a single "
                "value is requested then just the value is produced. If "
                "multiple values are requested then a JSON object, YAML "
                "mapping, or list of shell vars is output."),
            help=_("Query the state of one or more boot settings"))
        get_cmd.add_argument("get_vars", nargs="+", metavar="setting")
        self.add_style_arg(get_cmd)
        get_cmd.set_defaults(func=self.do_get)

        set_cmd = commands.add_parser(
            "set",
            description=_(
                "Update one or more boot configuration values."),
            help=_("Change the state of one or more boot settings"))
        set_cmd.add_argument(
            "--no-backup", action="store_false", dest="backup",
            help=_(
                "Don't take an automatic backup of the current boot "
                "configuration if one doesn't exist"))
        group = self.add_style_arg(set_cmd, required=True)
        group.add_argument(
            "set_vars", nargs="*", metavar="name=value", default=[],
            help=_(
                "Specify one or more settings to change on the command line"))
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
        self.add_style_arg(diff_cmd)
        diff_cmd.set_defaults(func=self.do_diff)

        show_cmd = commands.add_parser(
            "show", aliases=["cat"],
            description=_(
                "Display the specified stored boot configuration, or the "
                "sub-set of settings that match the specified pattern."),
            help=_("Show the specified stored configuration"))
        show_cmd.add_argument(
            "name",
            help=_("The name of the boot configuration to display"))
        show_cmd.add_argument("vars", nargs="?", metavar="pattern")
        show_cmd.add_argument(
            "-a", "--all", action="store_true",
            help=_(
                "Include all settings, not just those modified, in the "
                "output"))
        self.add_style_arg(show_cmd)
        show_cmd.set_defaults(func=self.do_show)

        ls_cmd = commands.add_parser(
            "list", aliases=["ls"],
            description=_("List all stored boot configurations."),
            help=_("List the stored boot configurations"))
        self.add_style_arg(ls_cmd)
        ls_cmd.set_defaults(func=self.do_list)

        rm_cmd = commands.add_parser(
            "remove", aliases=["rm"],
            description=_("Remove a stored boot configuration."),
            help=_("Remove a stored boot configuration"))
        rm_cmd.add_argument(
            "name",
            help=_("The name of the boot configuration to remove"))
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
        mv_cmd.set_defaults(func=self.do_rename)

        return parser

    def run(self):
        self.store = Store(self)
        self.func()

    def do_help(self):
        default = self.store[Default].settings
        if 'cmd' in self and self.cmd is not None:
            if self.cmd in default:
                self.dump_setting(default[self.cmd], fp=sys.stdout)
            elif '.' in self.cmd:
                # TODO Mis-spelled setting; use something like levenshtein to
                # detect "close" but incorrect setting names
                raise ValueError(_(
                    'Unknown setting "{self.cmd}"').format(self=self))
            elif '_' in self.cmd:
                # Old-style command
                commands = [
                    setting
                    for setting in default.values()
                    if isinstance(setting, Command)
                    and self.cmd in setting.commands
                ]
                if len(commands) == 1:
                    self.dump_setting(commands[0], fp=sys.stdout)
                else:
                    print(_(
                        '{self.cmd} is controlled by the following settings:'
                        '\n\n'
                        '{settings}').format(
                            self=self, settings='\n'.join(
                                setting.name for setting in commands)))
            else:
                parser = self.get_parser()
                parser.parse_args([self.cmd, '-h'])
        else:
            parser = self.get_parser()
            parser.parse_args(['-h'])

    def do_dump(self):
        self.name = Current
        self.do_show()

    def do_show(self):
        settings = self.store[self.name].settings
        if self.vars:
            settings = settings.filter(self.vars)
        if not self.all:
            settings = settings.modified()
        self.dump_settings(settings, fp=sys.stdout, mod=self.all)

    def do_get(self):
        current = self.store[Current]
        if len(self.get_vars) == 1:
            try:
                print(self.format_value(current[self.get_vars[0]].value))
            except KeyError:
                raise ValueError(_(
                    'unknown setting: {}').format(self.get_vars[0]))
        else:
            settings = set()
            for var in self.get_vars:
                try:
                    settings.add(current[var])
                except KeyError:
                    raise ValueError(_('unknown setting: {}').format(var))
            self.dump_settings(settings, fp=sys.stdout)

    def do_set(self):
        current = self.store[Current]
        mutable = current.mutable(self.config_write)
        if self.style == 'user':
            settings = {}
            for var in self.set_vars:
                if not '=' in var:
                    raise ValueError(_('expected "=" in {}').format(var))
                name, value = var.split('=', 1)
                settings[name] = UserStr(value)
        else:
            settings = self.load_settings()
        mutable.update(settings)
        self.backup_if_needed()
        self.store[Current] = mutable
        self.mark_reboot_required()

    def do_save(self):
        self.store[self.name] = self.store[Current]

    def do_load(self):
        # Look up the config to load before we do any backups, just in case the
        # user's made a mistake and the config doesn't exist
        to_load = self.store[self.name]
        self.backup_if_needed()
        self.store[Current] = to_load
        self.mark_reboot_required()

    def do_diff(self):
        # Keep references to the settings lying around while we dump the diff
        # as otherwise the settings lose their weak-ref during the dump
        left = self.store[self.left].settings
        right = self.store[self.right].settings
        self.dump_diff(self.left, self.right, left.diff(right), fp=sys.stdout)

    def do_list(self):
        current = self.store[Current]
        table = [
            (key, value.hash == current.hash, value.timestamp)
            for key, value in self.store.items()
            if key not in (Current, Default)
        ]
        self.dump_store(table, fp=sys.stdout)

    def do_remove(self):
        del self.store[self.name]

    def do_rename(self):
        self.store[self.to] = self.store[self.name]
        del self.store[self.name]

    def backup_if_needed(self):
        if self.backup and self.store.active is None:
            name = 'backup-{now:%Y%m%d-%H%M%S}'.format(now=datetime.now())
            suffix = 0
            while True:
                try:
                    self.store[name] = self.store[Current]
                except OSError as exc:
                    if exc.errno != errno.EEXIST:
                        raise
                    suffix += 1
                    name = 'backup-{now:%Y%m%d-%H%M%S}-{suffix}'.format(
                        now=datetime.now(), suffix=suffix)
                else:
                    print(_(
                        'Backed up current configuration in {name}').format(
                            name=name), file=sys.stderr)
                    break

    def mark_reboot_required(self):
        if self.reboot_required:
            with io.open(self.reboot_required, 'w') as f:
                f.write('*** ')
                f.write(_('System restart required'))
                f.write(' ***\n')
        if self.reboot_required_pkgs and self.package_name:
            with io.open(self.reboot_required_pkgs, 'a') as f:
                f.write(self.package_name)
                f.write('\n')
