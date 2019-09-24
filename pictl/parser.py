import errno
from pathlib import Path
from collections import namedtuple


ConfigLoc = namedtuple('ConfigLoc', ('path', 'lineno'))
ConfigParam = namedtuple('ConfigParam', ('overlay', 'param', 'value', 'loc'))
ConfigCommand = namedtuple('ConfigCommand', ('command', 'value', 'loc'))
ConfigOverlay = namedtuple('ConfigOverlay', ('overlay', 'loc'))
ConfigInclude = namedtuple('ConfigInclude', ('include', 'loc'))
ConfigSection = namedtuple('ConfigSection', ('section', 'loc'))


BASE_PARAMS = {
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


class ConfigTxtParser:
    def __init__(self):
        self._content = defaultdict(list)

    def parse(self, filename='/boot/firmware/config.txt'):
        return list(self._parse(self._read(filename)))

    def _read(self, filename):
        config_path = Path(filename)
        for lineno, line in enumerate(config_path.open('r', encoding='ascii')):
            self._content[config_path].append(line)
            # The bootloader ignores everything beyond column 80
            line = line.strip()[:80]
            if not line or line.startswith('#'):
                continue
            if line.startswith('include'):
                command, included_filename = line.split(None, 1)
                included_path = config_path.parent.joinpath(included_filename)
                yield line, ConfigLoc(config_path, lineno)
                try:
                    yield from self._read(str(included_path))
                except OSError as e:
                    if e.errno == errno.ENOENT:
                        # Ignore non-existent includes, just like the
                        # bootloader does
                        # TODO Warning?
                        pass
            else:
                yield line, ConfigLoc(config_path, lineno)

    def _parse(self, lines):
        overlay = 'base'
        for line, loc in lines:
            if '=' in line:
                cmd, value = line.split('=', 1)
                cmd = cmd.strip()
                value = value.strip()
                if cmd in {'device_tree_overlay', 'dtoverlay'}:
                    if ':' in value:
                        overlay, params = value.split(':', 1)
                        yield ConfigOverlay(overlay, loc)
                        for param in params.split(','):
                            yield self._parse_param(overlay, param, loc)
                    else:
                        overlay = value or 'base'
                        yield ConfigOverlay(overlay, loc)
                elif cmd in {'device_tree_param', 'dtparam'}:
                    yield self._parse_param(overlay, value, line)
                else:
                    yield ConfigCommand(cmd, value, loc)
            elif line.startswith('include'):
                command, filename = line.split(None, 1)
                yield ConfigInclude(filename, loc)
            elif line.startswith('initramfs'):
                command, filename, address = line.split(None, 2)
                yield ConfigCommand(command, (filename, address), loc)
            elif line.startswith('[') and line.endswith(']'):
                yield ConfigSection(line[1:-1], loc)
            else:
                # TODO warning?
                assert False

    def _parse_param(self, overlay, line, loc):
        if '=' in line:
            param, value = line.split('=', 1)
            param = param.strip()
            value = value.strip()
        else:
            param = line
            value = None
        if overlay == 'base':
            if param in {'i2c', 'i2c_arm', 'i2c1'}:
                param = 'i2c_arm'
            elif param in {'i2c_vc', 'i2c0'}:
                param = 'i2c_vc'
            elif param == 'i2c_baudrate':
                param = 'i2c_arm_baudrate'
            if param in bool_params:
                value = not value or value == 'on'
        return ConfigParam(overlay, param, value, loc)



