import sys
import gettext
import argparse

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
    "camera",
    "audio",
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


def parse_lines(filename):
    dtoverlay = 'base'
    for var, value in parse_syntax(filename):
        if var in {'device_tree_overlay', 'dtoverlay'}:
            if not value:
                dtoverlay = 'base'
            elif ':' in value:
                dtoverlay, params = value.split(':', 1)
                for param in params.split(','):
                    yield parse_dtparam(dtoverlay, param)
            else:
                dtoverlay = value
        elif var in {'device_tree_param', 'dtparam'}:
            yield parse_dtparam(dtoverlay, value)
        else:
            yield None, var, value


def parse_syntax(filename):
    for line in io.open(filename, 'r', encoding='ascii'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            var, value = line.split('=', 1)
            var = var.strip()
            value = value.strip()
            yield None, var, value
        elif line.startswith('include'):
            command, included_filename = line.split(None, 1)
            yield from parse_syntax(included_filename)
        elif line.startswith('initramfs'):
            # Yes this is technically "initramfs <filename> <address>" but
            # we don't care about parsing this anyway
            var, value = line.split(None, 1)
            yield None, var, value


def parse_dtparam(dtoverlay, dtparam):
    bool_params = {
        'audio':        False,
        'axiperf':      False,
        'eee':          True,
        'i2c_arm':      False,
        'i2c_vc':       False,
        'i2s':          False,
        'random':       True,
        'sd_debug':     False,
        'sd_force_pio': False,
        'spi':          False,
        'uart0':        True,
        'uart1':        False,
        'watchdog':     False,
    }
    if '=' in dtparam:
        dtparam, value = dtparam.split('=', 1)
        dtparam = dtparam.strip()
        value = value.strip()
    else:
        value = None
    if dtoverlay == 'base':
        if dtparam in {'i2c', 'i2c_arm', 'i2c1'}:
            dtparam = 'i2c_arm'
        elif dtparam in {'i2c_vc', 'i2c0'}:
            dtparam = 'i2c_vc'
        elif dtparam == 'i2c_baudrate':
            dtparam = 'i2c_arm_baudrate'
        if dtparam in bool_params:
            value = not value or value == 'on'
    yield dtoverlay, dtparam, value


def parse_config(filename='/boot/firmware/syscfg.txt'):
    


def update_config(filename, values):
    pass


def do_list():
    pass


def do_get(args):
    pass


def do_set(args):
    pass


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
