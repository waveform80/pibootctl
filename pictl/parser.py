import hashlib
from pathlib import Path
from collections import defaultdict

from .info import get_board_types, get_board_serial


class Line:
    def __init__(self, path, lineno):
        assert isinstance(path, Path)
        self.path = path
        self.lineno = lineno


class Section(Line):
    def __init__(self, path, lineno, section):
        super().__init__(path, lineno)
        self.section = section

    def __str__(self):
        return '[{self.section}]'.format(self=self)


class Command(Line):
    def __init__(self, path, lineno, command, params, hdmi=None):
        super().__init__(path, lineno)
        self.command = command
        self.params = params
        self.hdmi = hdmi

    def __str__(self):
        if self.command == 'initramfs':
            template = '{self.command} {self.params[0]} {self.params[1]}'
        elif not self.hdmi:
            template = '{self.command}={self.params}'
        else:
            template = '{self.command}:{self.hdmi}={self.params}'
        return template.format(self=self)


class Include(Line):
    def __init__(self, path, lineno, include):
        super().__init__(path, lineno)
        assert isinstance(include, Path)
        self.include = include

    def __str__(self):
        return 'include {self.include}'.format(self=self)


class Overlay(Line):
    def __init__(self, path, lineno, overlay):
        super().__init__(path, lineno)
        self.overlay = overlay

    def __str__(self):
        return 'dtoverlay={self.overlay}'.format(self=self)


class Param(Line):
    def __init__(self, path, lineno, overlay, param, value):
        super().__init__(path, lineno)
        self.overlay = overlay
        self.param = param
        self.value = value

    def __str__(self):
        return 'dtparam={self.param}={self.value}'.format(self=self)


class Filter:
    def __init__(self):
        self.pi = True
        self.hdmi = 0
        self.serial = True

    def evaluate(self, section):
        # Derived from information at:
        # https://www.raspberrypi.org/documentation/configuration/config-txt/conditional.md
        if section == 'all':
            self.pi = self.serial = True
        elif section == 'none':
            self.pi = False
        elif section.startswith('HDMI:'):
            self.hdmi = 1 if section == 'HDMI:1' else 0
        elif section.startswith('EDID='):
            # We can't currently evaluate this at runtime so just assume it
            # doesn't alter the current filter state
            pass
        elif section.startswith('gpio'):
            # We can't evaluate the GPIO filters either (the GPIO state has
            # potentially changed since boot and we shouldn't mess with their
            # modes at this point)
            pass
        elif section.startswith('0x'):
            try:
                self.serial = int(section, base=16) == get_board_serial()
            except ValueError:
                # Ignore invalid filters (as the bootloader does)
                pass
        elif section.startswith('pi'):
            self.pi = section in get_board_types()

    @property
    def enabled(self):
        return self.pi and self.serial


class Parser:
    def __init__(self):
        self._content = defaultdict(list)
        self._hash = None

    @property
    def content(self):
        return self._content

    @property
    def hash(self):
        return self._hash

    def parse(self, filename):
        if not isinstance(filename, Path):
            filename = Path(filename)
        self._content.clear()
        self._hash = hashlib.sha1()
        return list(self._parse(filename))

    def _parse(self, path):
        overlay = 'base'
        filter = Filter()
        for lineno, content in self._read(path):
            if content.startswith('[') and content.endswith(']'):
                content = content[1:-1]
                filter.evaluate(content)
                yield Section(path, lineno, content)
            elif filter.enabled:
                if '=' in content:
                    cmd, value = content.split('=', 1)
                    # NOTE: We deliberately don't strip cmd or value here
                    # because the bootloader doesn't either; whitespace on
                    # either side of the = is significant and can invalidate
                    # lines
                    if cmd in {'device_tree_overlay', 'dtoverlay'}:
                        if ':' in value:
                            overlay, params = value.split(':', 1)
                            yield Overlay(
                                path, lineno, overlay, prefix, newline)
                            for param, value in self._parse_params(overlay, params):
                                yield Param(path, lineno, overlay, param, value)
                        else:
                            overlay = value or 'base'
                            yield Overlay(path, lineno, overlay)
                    elif cmd in {'device_tree_param', 'dtparam'}:
                        for param, value in self._parse_params(overlay, value):
                            yield Param(path, lineno, overlay, param, value)
                    else:
                        if ':' in cmd:
                            cmd, hdmi = cmd.split(':', 1)
                            try:
                                hdmi = int(hdmi)
                            except ValueError:
                                hdmi = 0
                        else:
                            hdmi = filter.hdmi
                        yield Command(path, lineno, cmd, value, hdmi=hdmi)
                elif content.startswith('include'):
                    command, filename = content.split(None, 1)
                    included_path = path.parent.joinpath(filename)
                    yield Include(path, lineno, included_path)
                    yield from self._parse(included_path)
                elif content.startswith('initramfs'):
                    command, filename, address = content.split(None, 2)
                    yield Command(path, lineno, command, (filename, address))
                else:
                    # TODO warning?
                    assert False, repr(line)

    def _parse_params(self, overlay, params):
        for token in params.split(','):
            if '=' in token:
                param, value = token.split('=', 1)
                # NOTE: Again, we deliberately don't strip param or value
            else:
                param = token
                value = 'on'
            if overlay == 'base':
                if param in {'i2c', 'i2c_arm', 'i2c1'}:
                    param = 'i2c_arm'
                elif param in {'i2c_vc', 'i2c0'}:
                    param = 'i2c_vc'
                elif param == 'i2c_baudrate':
                    param = 'i2c_arm_baudrate'
            yield param, value

    def _read(self, path):
        with path.open('rb') as f:
            for lineno, line in enumerate(f):
                self._hash.update(line)
                self._content[path].append(line)
                content = line.decode('ascii').rstrip()
                # NOTE: The bootloader ignores everything beyond column 80 and
                # leading whitespace. The following slicing and stripping of
                # the string is done in a precise order to ensure we excise
                # chars beyond column 80 *before* stripping leading spaces
                content = content[:80].lstrip()
                if not content or content.startswith('#'):
                    continue
                yield lineno, content
