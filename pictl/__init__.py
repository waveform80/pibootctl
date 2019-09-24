import sys
import gettext
import argparse

from .parser import ConfigTxtParser

_ = gettext.gettext

try:
    import argcomplete
except ImportError:
    argcomplete = None


COMPONENTS = {
    "gpio.spi",
    "gpio.i2c",
    "gpio.i2s",
    "gpio.uart",
    "gpio.1wire",
    "gpio.remote",
    "camera.enabled",
    "audio.out",
    "wifi.country",
    "video.overscan",
    "video.pixel_2x",  # XXX ?
    "video.gl",  # XXX opengl?
}


def main(args=None):
    parser = argparse.ArgumentParser(
        description=_("pictl is a tool for enabling or disabling hardware on "
                      "the pi"))
    subparsers = parser.add_subparsers()

    list_parser = subparsers.add_parser(
        "list",
        description=_("List the status of all hardware"),
        help=_("List the status of all hardware"))
    get_parser = subparsers.add_parser(
        "get",
        description=_("Query the status of all or some hardware"),
        help=_("Query the status of all or some hardware"))
    get_parser.add_argument("get_vars", nargs="*", metavar="setting")
    set_parser = subparsers.add_parser(
        "set",
        description=_("Enable or disable hardware components"),
        help=_("Enable or disable hardware components"))
    set_parser.add_argument("set_vars", nargs="+", metavar="setting")
    args = parser.parse_args(args)

    if "set_vars" in args:
        do_set(args.set_var)
    elif "get_vars" in args:
        do_get(args.get_var)
    else:
        do_list()


def update_config(filename, values):
    reboot_required()


def reboot_required():
    subprocess.check_call(
        ['/usr/share/update-notifier/notify-reboot-required'],
        env={'DPKG_MAINTSCRIPT_PACKAGE': 'pictl'})


def do_list():
    parser = ConfigTxtParser()
    for item in parser.parse('../pi3-gadget/configs/config.txt.armhf'):
        if isinstance


def do_get(args):
    pass


def do_set(args):
    pass


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
