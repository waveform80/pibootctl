import hashlib
import zipfile
import warnings
from pathlib import Path
from collections import defaultdict

from .info import get_board_types, get_board_serial


class BootInvalid(Warning):
    "Raised when an invalid line is encountered"


class BootLine:
    def __init__(self, path, lineno):
        assert isinstance(path, Path)
        self.path = path
        self.lineno = lineno

    def __eq__(self, other):
        return (
            isinstance(other, BootLine) and
            other.path == self.path and
            other.lineno == self.lineno
        )

    def __repr__(self):
        return (
            'BootLine(path={self.path!r}, lineno={self.lineno!r})'.format(
                self=self))


class BootSection(BootLine):
    def __init__(self, path, lineno, section):
        super().__init__(path, lineno)
        self.section = section

    def __eq__(self, other):
        return (
            super().__eq__(other) and
            isinstance(other, BootSection) and
            other.section == self.section
        )

    def __str__(self):
        return '[{self.section}]'.format(self=self)

    def __repr__(self):
        return (
            'BootSection(path={self.path!r}, lineno={self.lineno!r}, '
            'section={self.section!r})'.format(self=self))


class BootCommand(BootLine):
    def __init__(self, path, lineno, command, params, hdmi=None):
        super().__init__(path, lineno)
        self.command = command
        self.params = params
        self.hdmi = hdmi

    def __eq__(self, other):
        return (
            super().__eq__(other) and
            isinstance(other, BootCommand) and
            other.command == self.command and
            other.params == self.params and
            other.hdmi == self.hdmi
        )

    def __str__(self):
        if self.command == 'initramfs':
            template = '{self.command} {self.params[0]} {self.params[1]}'
        elif not self.hdmi:
            template = '{self.command}={self.params}'
        else:
            template = '{self.command}:{self.hdmi}={self.params}'
        return template.format(self=self)

    def __repr__(self):
        return (
            'BootCommand(path={self.path!r}, lineno={self.lineno!r}, '
            'command={self.command!r}, params={self.params!r}, '
            'hdmi={self.hdmi!r})'.format(self=self))


class BootInclude(BootLine):
    def __init__(self, path, lineno, include):
        super().__init__(path, lineno)
        assert isinstance(include, Path)
        self.include = include

    def __eq__(self, other):
        return (
            super().__eq__(other) and
            isinstance(other, BootInclude) and
            other.include == self.include
        )

    def __str__(self):
        return 'include {self.include}'.format(self=self)

    def __repr__(self):
        return (
            'BootInclude(path={self.path!r}, lineno={self.lineno!r}, '
            'include={self.include!r})'.format(self=self))


class BootOverlay(BootLine):
    def __init__(self, path, lineno, overlay):
        super().__init__(path, lineno)
        self.overlay = overlay

    def __eq__(self, other):
        return (
            super().__eq__(other) and
            isinstance(other, BootOverlay) and
            other.overlay == self.overlay
        )

    def __str__(self):
        return 'dtoverlay={self.overlay}'.format(self=self)

    def __repr__(self):
        return (
            'BootOverlay(path={self.path!r}, lineno={self.lineno!r}, '
            'overlay={self.overlay!r})'.format(self=self))


class BootParam(BootLine):
    def __init__(self, path, lineno, overlay, param, value):
        super().__init__(path, lineno)
        self.overlay = overlay
        self.param = param
        self.value = value

    def __eq__(self, other):
        return (
            super().__eq__(other) and
            isinstance(other, BootParam) and
            other.overlay == self.overlay and
            other.param == self.param and
            other.value == self.value
        )

    def __str__(self):
        return 'dtparam={self.param}={self.value}'.format(self=self)

    def __repr__(self):
        return (
            'BootParam(path={self.path!r}, lineno={self.lineno!r}, '
            'overlay={self.overlay!r}, param={self.param!r}, '
            'value={self.value!r})'.format(self=self))


class BootFilter:
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


class BootParser:
    def __init__(self):
        self._content = defaultdict(list)
        self._hash = None

    @property
    def content(self):
        return self._content

    @property
    def hash(self):
        return self._hash

    def parse(self, path, filename="config.txt"):
        """
        Parse the boot configuration on *path* which may either be a string or
        a :class:`~pathlib.Path`. The path must either be a directory
        containing *filename* (which defaults to "config.txt"), or a .zip file
        containing *filename* (i.e. a stored boot configuration as produced by
        the "save" command).
        """
        self._content.clear()
        self._hash = hashlib.sha1()
        if not isinstance(filename, Path):
            filename = Path(filename)
        if not isinstance(path, Path):
            path = Path(path)
        if not path.is_dir():
            path = zipfile.ZipFile(str(path))
        return list(self._parse(path, filename))
        # XXX verify hash in stored configs?

    def _parse(self, path, filename):
        overlay = 'base'
        filter = BootFilter()
        for lineno, content in self._read(path, filename):
            if content.startswith('[') and content.endswith(']'):
                content = content[1:-1]
                filter.evaluate(content)
                yield BootSection(filename, lineno, content)
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
                            yield BootOverlay(filename, lineno, overlay)
                            for param, value in self._parse_params(overlay, params):
                                yield BootParam(
                                    filename, lineno, overlay, param, value)
                        else:
                            overlay = value or 'base'
                            yield BootOverlay(filename, lineno, overlay)
                    elif cmd in {'device_tree_param', 'dtparam'}:
                        for param, value in self._parse_params(overlay, value):
                            yield BootParam(
                                filename, lineno, overlay, param, value)
                    else:
                        if ':' in cmd:
                            cmd, hdmi = cmd.split(':', 1)
                            try:
                                hdmi = int(hdmi)
                            except ValueError:
                                hdmi = 0
                        else:
                            hdmi = filter.hdmi
                        yield BootCommand(
                            filename, lineno, cmd, value, hdmi=hdmi)
                elif content.startswith('include'):
                    command, included = content.split(None, 1)
                    included = Path(included)
                    yield BootInclude(filename, lineno, included)
                    yield from self._parse(path, included)
                elif content.startswith('initramfs'):
                    command, initrd, address = content.split(None, 2)
                    yield BootCommand(
                        filename, lineno, command, (initrd, address))
                else:
                    warnings.warn(BootInvalid(
                        "{filename}:{lineno} invalid line".format(
                            filename=filename, lineno=lineno)))

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

    def _read(self, path, filename):
        if isinstance(path, Path):
            context = lambda: (path / filename).open('rb')
        else:
            context = lambda: path.open(str(filename), 'r')
        with context() as text:
            for lineno, line in enumerate(text, start=1):
                self._hash.update(line)
                self._content[filename].append(line)
                content = line.decode('ascii', errors='replace').rstrip()
                # NOTE: The bootloader ignores everything beyond column 80 and
                # leading whitespace. The following slicing and stripping of
                # the string is done in a precise order to ensure we excise
                # chars beyond column 80 *before* stripping leading spaces
                content = content[:80].lstrip()
                try:
                    comment = content.index('#')
                except ValueError:
                    pass
                else:
                    content = content[:comment]
                if not content.strip():
                    continue
                yield lineno, content
