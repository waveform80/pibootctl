import io
import os
import sys
import gettext
import argparse
import configparser
from pathlib import Path
from datetime import datetime

from .store import Store, Settings
from .term import ErrorHandler
from .userstr import UserStr
from .output import Namespace

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
    parser = get_parser()
    args = parser.parse_args(args, namespace=Namespace())
    args.func(args)


def permission_error(exc_type, exc_value, exc_tb):
    msg = [exc_value]
    if os.geteuid() != 0:
        msg.append(_(
            "You need root permissions to modify the boot configuration or "
            "stored boot configurations"))
    return msg


def get_parser():
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
        '-r', '--config-read', metavar='FILE',
        default=section['config_read'],
        help=_(
            "The name of the config.txt file read by the bootloader, relative "
            "to --boot-path. Defaults to %(default)r."))
    parser.add_argument(
        '-w', '--config-write', metavar='FILE',
        default=section['config_write'],
        help=_(
            "The name of the config.txt file written by this tool, relative "
            "to --boot-path. Defaults to %(default)r."))
    parser.add_argument(
        '-s', '--store-path', metavar='DIR', type=Path,
        default=section['store_path'],
        help=_(
            "The path in which to store saved boot configurations. Defaults "
            "to %(default)r."))
    parser.set_defaults(
        func=do_help,
        backup=section.getboolean('backup'),
        package_name=section['package_name'],
        reboot_required=section['reboot_required'],
        reboot_required_pkgs=section['reboot_required_pkgs'])
    commands = parser.add_subparsers(title=_("commands"))

    help_cmd = commands.add_parser(
        "help", aliases=["?"],
        description=_(
            "Displays help about the specified command or setting, or about "
            "all commands if none is given."),
        help=_("Displays help about the specified command or setting"))
    help_cmd.add_argument("cmd", nargs='?')
    help_cmd.set_defaults(func=do_help)

    dump_cmd = commands.add_parser(
        "status", aliases=["dump"],
        description=_(
            "Output the current value of modified boot time settings that "
            "match the specified pattern (or all if no pattern is provided)"),
        help=_("Output the current boot time configuration"))
    dump_cmd.add_argument("vars", nargs="?", metavar="pattern")
    dump_cmd.add_argument(
        "-a", "--all", action="store_true",
        help=_(
            "Include all settings, regardless of modification, in the output"))
    Namespace.add_style_arg(dump_cmd)
    dump_cmd.set_defaults(func=do_dump)

    get_cmd = commands.add_parser(
        "get",
        description=_(
            "Query the status of one or more boot configuration values. When "
            "outputting in JSON, YAML, or shell format, if a single value is "
            "requested then just the value is produced. If multiple values "
            "requested then a JSON object, YAML mapping, or list of shell "
            "vars is output."),
        help=_("Query the state of one or more boot settings"))
    get_cmd.add_argument("get_vars", nargs="+", metavar="setting")
    Namespace.add_style_arg(get_cmd)
    get_cmd.set_defaults(func=do_get)

    set_cmd = commands.add_parser(
        "set",
        description=_(
            "Update one or more boot configuration values."),
        help=_("Change the state of one or more boot settings"))
    set_cmd.add_argument(
        "--no-backup", action="store_false", dest="backup",
        help=_("Don't take an automatic backup of the current boot "
               "configuration if one doesn't exist"))
    group = Namespace.add_style_arg(set_cmd, required=True)
    group.add_argument(
        "set_vars", nargs="*", metavar="name=value", default=[],
        help=_("Specify one or more settings to change on the command line"))
    set_cmd.set_defaults(func=do_set)

    save_cmd = commands.add_parser(
        "save",
        description=_(
            "Store the current boot configuration under a given name."),
        help=_("Store the current boot configuration for later use"))
    save_cmd.add_argument(
        "name",
        help=_("The name to save the current boot configuration under; can "
               "include any characters legal in a filename"))
    save_cmd.set_defaults(func=do_save)

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
        help=_("Don't take an automatic backup of the current boot "
               "configuration if one doesn't exist"))
    load_cmd.set_defaults(func=do_load)

    diff_cmd = commands.add_parser(
        "diff",
        description=_(
            "Display the settings that differ between two stored boot "
            "configurations, or between one stored boot configuration and the "
            "current configuration."),
        help=_("Show the differences between boot configurations"))
    diff_cmd.add_argument(
        "left", nargs="?",
        help=_("The boot configuration to compare from, or the current "
               "configuration if omitted"))
    diff_cmd.add_argument(
        "right",
        help=_("The boot configuration to compare against"))
    Namespace.add_style_arg(diff_cmd)
    diff_cmd.set_defaults(func=do_diff)

    show_cmd = commands.add_parser(
        "show", aliases=["cat"],
        description=_(
            "Display the specified stored boot configuration, or the sub-set "
            "of settings that match the specified pattern."),
        help=_("Show the specified stored configuration"))
    show_cmd.add_argument(
        "name",
        help=_("The name of the boot configuration to display"))
    show_cmd.add_argument("vars", nargs="?", metavar="pattern")
    show_cmd.add_argument(
        "-a", "--all", action="store_true",
        help=_("Include all settings, not just those modified, in the output"))
    Namespace.add_style_arg(show_cmd)
    show_cmd.set_defaults(func=do_show)

    ls_cmd = commands.add_parser(
        "list", aliases=["ls"],
        description=_("List all stored boot configurations."),
        help=_("List the stored boot configurations"))
    Namespace.add_style_arg(ls_cmd)
    ls_cmd.set_defaults(func=do_list)

    rm_cmd = commands.add_parser(
        "remove", aliases=["rm"],
        description=_("Remove a stored boot configuration."),
        help=_("Remove a stored boot configuration"))
    rm_cmd.add_argument(
        "name",
        help=_("The name of the boot configuration to remove"))
    rm_cmd.set_defaults(func=do_remove)

    return parser


def do_help(args):
    default = Settings()
    # TODO Use something like levenshtein to detect "close" but incorrect
    # setting names
    if 'cmd' in args and args.cmd in default:
        args.dump_setting(default[args.cmd], fp=sys.stdout)
    else:
        parser = get_parser()
        if 'cmd' not in args or args.cmd is None:
            parser.parse_args(['-h'])
        else:
            parser.parse_args([args.cmd, '-h'])


def do_dump(args):
    do_dump_or_show(args, None)


def do_show(args):
    do_dump_or_show(args, args.name)


def do_dump_or_show(args, key):
    store = Store(args)
    stored = store[key].settings
    # TODO Is this still necessary?
    # Need to keep a reference to the stored set; some settings depend on the
    # overall context to determine their value and their reference to it is
    # weak
    settings = stored
    if args.vars:
        settings = settings.filter(args.vars)
    if not args.all:
        settings = settings.modified()
    args.dump_settings(settings, fp=sys.stdout, mod=args.all)


def do_get(args):
    store = Store(args)
    current = store[None]
    if len(args.get_vars) == 1:
        try:
            print(args.format_value(current[args.get_vars[0]].value))
        except KeyError:
            raise ValueError(_('unknown setting: {}').format(args.get_vars[0]))
    else:
        settings = set()
        for var in args.get_vars:
            try:
                settings.add(current[var])
            except KeyError:
                raise ValueError(_('unknown setting: {}').format(var))
        args.dump_settings(settings, fp=sys.stdout)


def do_set(args):
    store = Store(args)
    current = store[None]
    updated = current.copy()
    if args.style == 'user':
        settings = {}
        for var in args.set_vars:
            if not '=' in var:
                raise ValueError(_('expected "=" in {}').format(var))
            name, value = var.split('=', 1)
            settings[name] = UserStr(value)
    else:
        settings = args.load_settings()
    updated.update(settings)
    updated.validate()
    backup_if_needed(args, parser)
    # TODO Only write settings that aren't present in non-written files
    with io.open(str(args.boot_path / args.config_write),
                 'w', encoding='ascii') as out:
        out.write(updated.output())
    reboot_required(args)
    # TODO Check for efficacy (overridden values)


def do_save(args):
    store = Store(args)
    store[args.name] = store[None]


def do_load(args):
    store = Store(args)
    # Look up the config to load before we do any backups, just in case the
    # user's made a mistake and the config doesn't exist
    to_load = store[args.name]
    backup_if_needed(args, store)
    store[None] = to_load
    reboot_required(args)


def do_diff(args):
    store = Store(args)
    args.dump_diff(args.left, args.right,
                   store[args.left].settings.diff(store[args.right].settings),
                   fp=sys.stdout)


def do_list(args):
    store = Store(args)
    current = store[None]
    table = [
        (key, value.hash == current.hash, value.timestamp)
        for key, value in store.items()
        if key is not None
    ]
    args.dump_store(table, fp=sys.stdout)


def do_remove(args):
    store = Store(args)
    del store[args.name]


def backup_if_needed(args, store):
    if args.backup and store.active is None:
        name = 'backup-{now:%Y%m%d-%H%M%S}'.format(now=datetime.now())
        # TODO Clocks can be funny on the pi; make absolutely damned certain
        # that name doesn't already exist
        print(_('Backing up current configuration in {name}').format(name=name),
              file=sys.stderr)
        store[name] = store[None]


def reboot_required(args):
    if args.reboot_required:
        with io.open(args.reboot_required, 'w') as f:
            f.write('*** ')
            f.write(_('System restart required'))
            f.write(' ***\n')
    if args.reboot_required_pkgs and args.package_name:
        with io.open(args.reboot_required_pkgs, 'a') as f:
            f.write(args.package_name)
            f.write('\n')
