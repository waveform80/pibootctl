import io
import os
import sys
import errno
import gettext
import argparse
import configparser
from fnmatch import fnmatch

from .parser import Parser
from .settings import Settings
from .term import term_color, term_size
from .formatter import render, unicode_table
from .formats import format_value, dump_setting_user, dump_settings, load_settings

_ = gettext.gettext

try:
    import argcomplete
except ImportError:
    argcomplete = None


class EmptySettings(Exception):
    "Raised when no settings match filtering criteria"


class InvalidSetting(Exception):
    "Raised when a setting name is not recognized"


def main(args=None):
    parser = get_parser()
    args = parser.parse_args(args)
    args.func(args)


def get_parser():
    config = configparser.ConfigParser(
        defaults={
            'config_read': '/boot/config.txt',
            'config_write': '/boot/config.txt',
            'config_store': '/boot/pictl',
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
        '-r', '--config-read', metavar='FILE',
        default=config.get('defaults', 'config_read'),
        help=_(
            "The path to the config.txt file read by the bootloader. Defaults "
            "to %(default)s."))
    parser.add_argument(
        '-w', '--config-write', metavar='FILE',
        default=config.get('defaults', 'config_write'),
        help=_(
            "The path to the config.txt file written by this tool. Default to "
            "%(default)s (but can be a file included by another)."))
    parser.add_argument(
        '-s', '--config-store', metavar='DIR',
        default=config.get('defaults', 'config_store'),
        help=_(
            "The path in which to store saved boot configurations. Defaults "
            "to %(default)s."))
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
    dump_cmd.add_argument("list_vars", nargs="?", metavar="pattern")
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
    set_cmd.set_defaults(func=do_set, style="user")

    save_cmd = commands.add_parser(
        "save",
        description=_(
            "Store the current boot configuration under a given name."),
        help=_("Store the current boot configuration for later use"))
    save_cmd.add_argument(
        "name",
        help=_("The name to save the current boot configuration under"))
    save_cmd.set_defaults(func=do_save)

    load_cmd = commands.add_parser(
        "load",
        description=_(
            "Overwrite the current boot configuration with a stored one."),
        help=_("Replace the boot configuration with a saved one"))
    load_cmd.add_argument(
        "name",
        help=_("The name of the boot configuration to restore"))
    load_cmd.set_defaults(func=do_load)

    ls_cmd = commands.add_parser(
        "list", aliases=["ls"],
        description=_(
            "List all stored boot configurations (see the save command)."),
        help=_("List the stored boot configurations"))
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
    parser = Parser()
    default = Settings()
    current = default.copy()
    current.extract(parser.parse(args.config_read))
    # NOTE: need to keep a reference to the current set; some settings depend
    # on the overall context to determine their value and their reference to it
    # is weak
    settings = current
    if args.list_vars:
        settings = {
            setting
            for setting in settings
            if fnmatch(setting.name, args.list_vars)
        }
    if args.modified:
        settings = {
            setting
            for setting in settings
            if setting.value is not setting.default
        }
    if not settings:
        raise EmptySettings('no settings match the filtering criteria')
    dump_settings(args.style, settings, fp=sys.stdout)


def do_get(args):
    parser = Parser()
    default = Settings()
    current = default.copy()
    current.extract(parser.parse(args.config_read))
    if len(args.get_vars) == 1:
        try:
            print(format_value(args.style, current[args.get_vars[0]].value))
        except KeyError:
            raise InvalidSetting(
                'unknown setting: {}'.format(args.get_vars[0]))
    else:
        settings = set()
        for var in args.get_vars:
            try:
                settings.add(current[var])
            except KeyError:
                raise InvalidSetting(var)
        dump_settings(args.style, settings, fp=sys.stdout)


def do_set(args):
    parser = Parser()
    default = Settings()
    current = default.copy()
    current.extract(parser.parse(args.config_read))
    updated = current.copy()
    if args.style == 'user':
        settings = {}
        for var in args.set_vars:
            if not '=' in var:
                raise InvalidSetting('expected "=" in {}'.format(var))
            name, value = var.split('=', 1)
            settings[name] = value
    else:
        settings = load_settings(args.style)
    for name, value in settings.items():
        try:
            updated[name].update(value)
        except KeyError:
            raise InvalidSetting(name)
    updated.validate()
    try:
        with io.open(args.config_write, 'w', encoding='ascii') as out:
            out.write(updated.output())
    except PermissionError:
        if os.geteuid() != 0:
            raise PermissionError(
                errno.EACCESS,
                "Unable to re-write {}; you may need to be root (try "
                "sudo)".format(args.config_write))
    else:
        reboot_required()
    # TODO Check for efficacy (overriden values)


def do_save(args):
    raise NotImplementedError


def do_load(args):
    raise NotImplementedError


def do_list(args):
    raise NotImplementedError


def do_remove(args):
    raise NotImplementedError


def reboot_required():
    # TODO: activate me
    #with io.open('/var/run/reboot-required', 'w') as f:
    #    f.write("*** ")
    #    f.write(_("System restart required"))
    #    f.write(" ***\n")
    #with io.open('/var/run/reboot-required.pkgs', 'a') as f:
    #    f.write("pictl\n")
    pass
