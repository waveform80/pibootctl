import io
import os
import sys
import locale
import gettext
import argparse
import configparser
from pathlib import Path
from fnmatch import fnmatch
from datetime import datetime
from zipfile import ZipFile, ZIP_DEFLATED

from .term import ErrorHandler
from .parser import BootParser
from .settings import Settings
from .output import (
    format_value,
    dump_store,
    dump_diff,
    dump_setting_user,
    dump_settings,
    load_settings,
)

try:
    import argcomplete
except ImportError:
    argcomplete = None


_ = gettext.gettext


def main(args=None):
    sys.excepthook = ErrorHandler()
    sys.excepthook[PermissionError] = (permission_error, 1)
    if not int(os.environ.get('DEBUG', '0')):
        sys.excepthook[Exception] = (sys.excepthook.exc_message, 1)
    locale.setlocale(locale.LC_ALL, '')
    parser = get_parser()
    args = parser.parse_args(args)
    args.func(args)


def permission_error(exc_type, exc_value, exc_tb):
    msg = [exc_value]
    if os.geteuid() != 0:
        msg.append(_(
            "You need root permissions to modify the boot configuration"))
    return msg


def get_parser():
    config = configparser.ConfigParser(
        defaults={
            'boot_path':    '/boot',
            'store_path':   '/boot/pictl',
            'config_read':  'config.txt',
            'config_write': 'config.txt',
            'backup':       'on',
        },
        default_section='defaults',
        interpolation=None)
    config.read(
        ['/etc/pictl.conf', os.path.expanduser('~/.config/pictl/pictl.conf')],
        encoding='ascii')

    parser = argparse.ArgumentParser(
        description=_(
            "pictl is a tool for querying and modifying the boot "
            "configuration of the Raspberry Pi"))
    parser.add_argument(
        '--version', action='version', version='0.1')
    parser.add_argument(
        '-B', '--boot-path', metavar='DIR', type=Path,
        default=config.get('defaults', 'boot_path'),
        help=_(
            "The path on which the boot partition is mounted. Defaults to "
            "%(default)r."))
    parser.add_argument(
        '-r', '--config-read', metavar='FILE',
        default=config.get('defaults', 'config_read'),
        help=_(
            "The name of the config.txt file read by the bootloader, relative "
            "to --boot-path. Defaults to %(default)r."))
    parser.add_argument(
        '-w', '--config-write', metavar='FILE',
        default=config.get('defaults', 'config_write'),
        help=_(
            "The name of the config.txt file written by this tool, relative "
            "to --boot-path. Defaults to %(default)r."))
    parser.add_argument(
        '-s', '--store-path', metavar='DIR', type=Path,
        default=config.get('defaults', 'store_path'),
        help=_(
            "The path in which to store saved boot configurations. Defaults "
            "to %(default)r."))
    parser.set_defaults(func=do_help)
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
            "Output the current value of the boot time settings that match "
            "the specified pattern (or all if no pattern is provided)"),
        help=_("Output the current boot time configuration"))
    dump_cmd.add_argument("vars", nargs="?", metavar="pattern")
    dump_cmd.add_argument(
        "--modified", action="store_true",
        help=_("Only include modified settings in the output"))
    add_format_args(dump_cmd)
    dump_cmd.set_defaults(func=do_dump, style="user")

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
    add_format_args(get_cmd)
    get_cmd.set_defaults(func=do_get, style="user")

    set_cmd = commands.add_parser(
        "set",
        description=_(
            "Update one or more boot configuration values."),
        help=_("Change the state of one or more boot settings"))
    set_cmd.add_argument(
        "--no-backup", action="store_false", dest="backup",
        help=_("Don't take an automatic backup of the current boot "
               "configuration if one doesn't exist"))
    fmt_group = set_cmd.add_mutually_exclusive_group(required=True)
    fmt_group.add_argument(
        "--json", dest="style", action="store_const", const="json",
        help=_("Read JSON from stdin"))
    fmt_group.add_argument(
        "--yaml", dest="style", action="store_const", const="yaml",
        help=_("Read YAML from stdin"))
    fmt_group.add_argument(
        "--shell", dest="style", action="store_const", const="shell",
        help=_("Read shell-style var=value lines from stdin"))
    fmt_group.add_argument(
        "set_vars", nargs="*", metavar="name=value", default=[],
        help=_("Specify one or more settings to change on the command line"))
    set_cmd.set_defaults(func=do_set, style="user",
                         backup=config.getboolean('defaults', 'backup'))

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
    load_cmd.set_defaults(func=do_load,
                          backup=config.getboolean('defaults', 'backup'))

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
    add_format_args(diff_cmd)
    diff_cmd.set_defaults(func=do_diff, style="user")

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
        "--modified", action="store_true",
        help=_("Only include modified settings in the output"))
    add_format_args(show_cmd)
    show_cmd.set_defaults(func=do_show, style="user")

    ls_cmd = commands.add_parser(
        "list", aliases=["ls"],
        description=_(
            "List all stored boot configurations."),
        help=_("List the stored boot configurations"))
    add_format_args(ls_cmd)
    ls_cmd.set_defaults(func=do_list, style="user")

    rm_cmd = commands.add_parser(
        "remove", aliases=["rm"],
        description=_("Remove a stored boot configuration."),
        help=_("Remove a stored boot configuration"))
    rm_cmd.add_argument(
        "name",
        help=_("The name of the boot configuration to remove"))
    rm_cmd.set_defaults(func=do_remove)

    return parser


def add_format_args(parser):
    fmt_group = parser.add_mutually_exclusive_group()
    fmt_group.add_argument(
        "--json", dest="style", action="store_const", const="json",
        help=_("Use JSON as the output format"))
    fmt_group.add_argument(
        "--yaml", dest="style", action="store_const", const="yaml",
        help=_("Use YAML as the output format"))
    fmt_group.add_argument(
        "--shell", dest="style", action="store_const", const="shell",
        help=_("Use a var=value format suitable for the shell"))


def do_help(args):
    default = Settings()
    if 'cmd' in args and args.cmd in default:
        dump_setting_user(default[args.cmd], fp=sys.stdout)
    else:
        parser = get_parser()
        if 'cmd' not in args or args.cmd is None:
            parser.parse_args(['-h'])
        else:
            parser.parse_args([args.cmd, '-h'])


def do_dump(args):
    do_dump_or_show(args, args.boot_path)


def do_show(args):
    zip_path = (args.store_path / args.name).with_suffix('.zip')
    do_dump_or_show(args, zip_path)


def do_dump_or_show(args, path):
    parser = BootParser()
    default = Settings()
    stored = default.copy()
    stored.extract(parser.parse(path, args.config_read))
    # NOTE: need to keep a reference to the stored set; some settings depend
    # on the overall context to determine their value and their reference to it
    # is weak
    settings = stored
    if args.vars:
        settings = {
            setting
            for setting in settings
            if fnmatch(setting.name, args.vars)
        }
    if args.modified:
        settings = {
            setting
            for setting in settings
            if setting.value is not setting.default
        }
    dump_settings(args.style, settings, fp=sys.stdout)


def do_get(args):
    parser = BootParser()
    default = Settings()
    current = default.copy()
    current.extract(parser.parse(args.boot_path, args.config_read))
    if len(args.get_vars) == 1:
        try:
            print(format_value(args.style, current[args.get_vars[0]].value))
        except KeyError:
            raise ValueError(_('unknown setting: {}').format(args.get_vars[0]))
    else:
        settings = set()
        for var in args.get_vars:
            try:
                settings.add(current[var])
            except KeyError:
                raise ValueError(_('unknown setting: {}').format(var))
        dump_settings(args.style, settings, fp=sys.stdout)


def do_set(args):
    parser = BootParser()
    default = Settings()
    current = default.copy()
    current.extract(parser.parse(args.boot_path, args.config_read))
    updated = current.copy()
    if args.style == 'user':
        settings = {}
        for var in args.set_vars:
            if not '=' in var:
                raise ValueError(_('expected "=" in {}').format(var))
            name, value = var.split('=', 1)
            settings[name] = value
    else:
        settings = load_settings(args.style)
    for name, value in settings.items():
        try:
            updated[name].update(value)
        except KeyError:
            raise ValueError(_('unknown setting: {}').format(name))
    updated.validate()
    backup_if_needed(args, parser)
    with io.open(str(args.boot_path / args.config_write),
                 'w', encoding='ascii') as out:
        out.write(updated.output())
    reboot_required()
    # TODO Check for efficacy (overriden values)


def do_save(args):
    parser = BootParser()
    parser.parse(args.boot_path, args.config_read)
    store_parsed(args, parser, args.name)


def do_load(args):
    parser = BootParser()
    parser.parse(args.boot_path, args.config_read)
    backup_if_needed(args, parser)
    zip_path = (args.store_path / args.name).with_suffix('.zip')
    with ZipFile(str(zip_path), 'r') as arc:
        if not arc.comment.startswith(b'pictl:0:'):
            raise ValueError(
                _("{file} is not a valid pictl boot configuration"
                  ).format(file=zip_path))
        for info in arc.infolist():
            arc.extract(info, path=str(args.boot_path))
    reboot_required()


def do_diff(args):
    parser = BootParser()
    left = Settings()
    right = left.copy()
    if args.left is None:
        left_path = args.boot_path
    else:
        left_path = (args.store_path / args.left).with_suffix('.zip')
    left.extract(parser.parse(left_path, args.config_read))
    right_path = (args.store_path / args.right).with_suffix('.zip')
    right.extract(parser.parse(right_path, args.config_read))
    dump_diff(args.style, args.left, args.right, left.diff(right), fp=sys.stdout)


def do_list(args):
    parser = BootParser()
    parser.parse(args.boot_path, args.config_read)
    active_hash = parser.hash.hexdigest().lower()
    table = []
    for name, arc_hash, timestamp in enumerate_store(args):
        table.append((name, arc_hash == active_hash, timestamp))
    dump_store(args.style, table, fp=sys.stdout)


def do_remove(args):
    zip_path = (args.store_path / args.name).with_suffix('.zip')
    zip_path.unlink()


def enumerate_store(args):
    for p in args.store_path.glob('*.zip'):
        with ZipFile(str(p), 'r') as arc:
            if arc.comment.startswith(b'pictl:0:'):
                arc_hash = arc.comment[8:48].decode('ascii').lower()
                yield p.stem, arc_hash, datetime.fromtimestamp(p.stat().st_mtime)


def store_parsed(args, parser, name):
    zip_path = (args.store_path / name).with_suffix('.zip')
    # TODO use mode 'x'? Add a --force to overwrite with mode 'w'?
    with ZipFile(str(zip_path), 'w', compression=ZIP_DEFLATED) as arc:
        arc.comment = 'pictl:0:{}'.format(parser.hash.hexdigest()).encode('ascii')
        for path, lines in parser.content.items():
            arc.writestr(str(path), b''.join(lines))


def backup_if_needed(args, parser):
    if args.backup:
        active_hash = parser.hash.hexdigest().lower()
        for name, arc_hash, timestamp in enumerate_store(args):
            if arc_hash == active_hash:
                # There's already an archive of the parsed configuration
                return
        name = 'backup-{now:%Y%m%d-%H%M%S}'.format(now=datetime.now())
        print("Backing up current configuration in {name}".format(name=name))
        store_parsed(args, parser, name)


def reboot_required():
    # TODO: activate me
    #with io.open('/var/run/reboot-required', 'w') as f:
    #    f.write("*** ")
    #    f.write(_("System restart required"))
    #    f.write(" ***\n")
    #with io.open('/var/run/reboot-required.pkgs', 'a') as f:
    #    f.write("pictl\n")
    pass
