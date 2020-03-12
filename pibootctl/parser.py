"""
The :mod:`pibootctl.parser` module provides the :class:`BootParser` class for
parsing the boot configuration of the Raspberry Pi.

The output of this class consists of derivatives of :class:`BootLine`
(:class:`BootSection`, :class:`BootCommand`, etc.) and :class:`BootFile`
instances.

.. autoclass:: BootParser
    :members:

.. autoclass:: BootLine

.. autoclass:: BootSection

.. autoclass:: BootCommand

.. autoclass:: BootInclude

.. autoclass:: BootFile
"""

import io
import os
import hashlib
import warnings
from pathlib import Path
from zipfile import ZipFile, ZipInfo
from datetime import datetime
from collections import namedtuple

from .info import get_board_types, get_board_serial


class BootInvalid(Warning):
    "Raised when an invalid line is encountered"


class BootLine:
    """
    Represents a line in a boot configuration. Provides two simple attributes:

    .. attribute:: path

        A :class:`str` indicating the path of the file containing the line.

    .. attribute:: lineno

        The 1-based line number of the line.
    """
    def __init__(self, path, lineno):
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
    """
    A derivative of :class:`BootLine` for ``[conditional sections]`` in a boot
    configuration. Adds a single attribute:

    .. attribute:: section

        The criteria of the section (everything between the square brackets).
    """
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
    """
    A derivative of :class:`BootLine` which represents a command in a boot
    configuration, e.g. "disable_overscan=1". Adds several attributes:

    .. attribute:: command

        The title of the command; characters before the first "=" in the line.

    .. attribute:: params

        The value of the command; characters after the first "=" in the line.
        As a special case, the "initramfs" command has two values and thus if
        :attr:`command` is "initramfs" then this attribute will be a 2-tuple.

    .. attribute:: hdmi

        The HDMI display that the command applies to. This is usually 0 unless
        the command has an explicit hdmi suffix (":" separated after the
        :attr:`command` title but before the "="), or unless the command
        appears in an [HDMI:1] section.
    """
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
    """
    A derivative of :class:`BootLine` representing an "include" command in a
    boot configuration. Adds a single attribute:

    .. attribute:: include

        The name of the file to be included.
    """
    def __init__(self, path, lineno, include):
        super().__init__(path, lineno)
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
    """
    A derivative of :class:`BootLine` representing a device-tree overlay
    ("dtoverlay=") command in a boot configuration. Adds a single attribute:

    .. attribute:: overlay

        The name of the device-tree overlay to load.
    """
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
    """
    A derivative of :class:`BootLine` representing a parameter to a loaded
    device-tree overlay ("dtparam=") command in a boot configuration. Adds
    several attributes:

    .. attribute:: overlay

        The device-tree overlay that the parameter applies to.

    .. attribute:: param

        The name of the parameter affected by the command.

    .. attribute:: value

        The new value to assign to the overlay parameter.
    """
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
        else:
            warnings.warn(
                BootInvalid('unrecognized conditional: {}'.format(section)))

    @property
    def enabled(self):
        return self.pi and self.serial


class BootFile(namedtuple('Content', (
    'filename',
    'timestamp',
    'content',
    'encoding',
    'errors'
))):
    """
    Represents a file in a boot configuration.

    .. attribute:: filename

        A :class:`str` representing the file's path relative to the boot
        configuration's container (whatever that may be: a path, a zip archive,
        etc.)

    .. attribute:: timestamp

        A :class:`~datetime.datetime` containing the last modification
        timestamp of the file.

            .. note::

                This is rounded down to a 2-second precision as that is all
                that `PKZIP`_ archives support.

    .. attribute:: content

        A :class:`bytes` string containing the complete content of the file.

    .. attribute:: encoding

        :data:`None` if the file is a binary file. Otherwise, specifies the
        name of the character encoding to be used when reading the file.

    .. attribute:: errors

        :data:`None` if the file is a binary file. Otherwise, specifies the
        character replacement strategy to be used with erroneous characters
        encountered when reading the file.

    .. _PKZIP: https://en.wikipedia.org/wiki/Zip_(file_format)
    """
    __slots__ = ()

    def __new__(cls, filename, timestamp, content, encoding=None, errors=None):
        # Adjust timestamps down to 2-second precision (all that's supported in
        # the PKZIP format), and to a minimum of 1980. This is to support those
        # scenarios (e.g. no network) in which a pi has de-synced clock and
        # winds up with files in 1970 (prior to the date PKZIP supports).
        return super().__new__(
            cls, filename,
            timestamp.replace(
                year=max(1980, timestamp.year),
                second=timestamp.second // 2 * 2,
                microsecond=0),
            content, encoding, errors)

    @classmethod
    def empty(cls, filename, encoding=None, errors=None):
        """
        Class method for constructing an apparently empty :class:`BootFile`.
        """
        return cls(filename, datetime.fromtimestamp(0), b'', encoding, errors)

    def lines(self):
        """
        Generator method which returns lines of text from the file using the
        associated :attr:`encoding` and :attr:`errors`.
        """
        yield from io.TextIOWrapper(
            io.BytesIO(self.content), encoding=self.encoding,
            errors=self.errors)

    def add_to_zip(self, arc):
        """
        Adds this :class:`BootFile` to the specified *arc* (which must be a
        :class:`~zipfile.ZipFile` instance), using the stored filename and
        last modification timestamp.
        """
        info = ZipInfo(str(self.filename), (
            self.timestamp.year, self.timestamp.month, self.timestamp.day,
            self.timestamp.hour, self.timestamp.minute, self.timestamp.second))
        arc.writestr(info, self.content)


class BootParser:
    """
    Parser for the files used to configure the Raspberry Pi's bootloader.

    The *path* specifies the container of all files that make up the
    configuration. It be one of:

    * a :class:`str` or a :class:`~pathlib.Path` in which case the path
      specified must be a directory

    * a :class:`~zipfile.ZipFile`

    * a :class:`dict` mapping filenames to sequences of :class:`str` (for
      configuration files), or :class:`bytes` strings for auxilliary binary
      files; effectively the output of :attr:`files` after parsing
    """
    def __init__(self, path):
        if isinstance(path, str):
            path = Path(path)
        assert isinstance(path, (Path, ZipFile, dict))
        if isinstance(path, Path):
            assert path.is_dir()
        self._path = path
        self._files = {}
        self._hash = None
        self._config = None
        self._timestamp = None

    @property
    def path(self):
        """
        The path under which all configuration files can be found. This may be
        a :class:`~pathlib.Path` instance, or a :class:`~zipfile.ZipFile`, or a
        :class:`dict`.
        """
        return self._path

    @property
    def config(self):
        """
        The parsed configuration; a sequence of :class:`BootLine` instances (or
        derivatives of :class:`BootLine`), after :meth:`parse` has been
        successfully called.
        """
        return self._config

    @property
    def files(self):
        """
        The content of all parsed files; a mapping of filename to
        :class:`BootFile` objects.
        """
        return self._files

    @property
    def hash(self):
        """
        After :meth:`parse` is successfully called, this is the SHA1 hash of
        the complete configuration in parsed order (i.e. starting at
        "config.txt" and proceeding through all included files).
        """
        return self._hash.hexdigest().lower()

    @property
    def timestamp(self):
        """
        The latest modified timestamp on all files that were read as a result
        of calling :meth:`parse`.
        """
        return self._timestamp

    def parse(self, filename="config.txt"):
        """
        Parse the boot configuration on :attr:`path`. The optional *filename*
        specifies the "root" of the configuration, and defaults to
        :file:`config.txt`.

        If parsing is successful, this will update the :attr:`files`,
        :attr:`hash`, :attr:`timestamp`, and :attr:`config` attributes.
        """
        self._files.clear()
        self._hash = hashlib.sha1()
        self._timestamp = datetime.fromtimestamp(0)  # UNIX epoch
        self._config = list(self._parse(filename))

    def add(self, filename, encoding=None, errors=None):
        """
        Adds the auxilliary *filename* under :attr:`path` to the configuration.
        This is used to update the :attr:`hash` and :attr:`files` of the parsed
        configuration to include files which are referenced by the boot
        configuration but aren't themselves configuration files (e.g. EDID
        data, and the kernel cmdline.txt).

        If specified, *encoding* and *errors* are as for :func:`open`. If
        *encoding* is :data:`None`, the data is assumed to be binary and the
        method will return the content of the file as a :class:`bytes` string.
        Otherwise, the content of the file is assumed to be text and will be
        returned as a :class:`list` of :class:`str`.
        """
        return self._open(filename, encoding, errors)

    def _parse(self, filename):
        overlay = 'base'
        filter = BootFilter()
        for lineno, content in self._read_text(filename):
            if content.startswith('[') and content.endswith(']'):
                content = content[1:-1]
                filter.evaluate(content)
                yield BootSection(filename, lineno, content)
            elif filter.enabled:
                if '=' in content:
                    cmd, value = content.split('=', 1)
                    # We deliberately don't strip cmd or value here because the
                    # bootloader doesn't either; whitespace on either side of
                    # the = is significant and can invalidate lines
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
                    yield BootInclude(filename, lineno, included)
                    yield from self._parse(included)
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
                # Again, we deliberately don't strip param or value
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

    def _read_text(self, filename):
        for lineno, line in enumerate(
                self._open(filename, encoding='ascii', errors='replace').lines(),
                start=1):
            # The bootloader ignores everything beyond column 80 and
            # leading whitespace. The following slicing and stripping of
            # the string is done in a precise order to ensure we excise
            # chars beyond column 80 *before* stripping leading spaces
            line = line.rstrip()[:80].lstrip()
            try:
                comment = line.index('#')
            except ValueError:
                pass
            else:
                line = line[:comment]
            if not line.strip():
                continue
            yield lineno, line

    def _open(self, filename, encoding=None, errors=None):
        if isinstance(self.path, Path):
            try:
                with (self.path / filename).open('rb') as f:
                    file = BootFile(
                        filename,
                        datetime.fromtimestamp(os.fstat(f.fileno()).st_mtime),
                        f.read(), encoding, errors)
            except FileNotFoundError:
                file = None
        elif isinstance(self.path, ZipFile):
            try:
                with self.path.open(str(filename), 'r') as f:
                    file = BootFile(
                        filename,
                        datetime(*self.path.getinfo(f.name).date_time),
                        f.read(), encoding, errors)
            except KeyError:
                # Yes, ZipFile raises KeyError when an archive member isn't
                # found...
                file = None
        elif isinstance(self.path, dict):
            try:
                file = BootFile(
                    filename,
                    self.path[filename].timestamp,
                    self.path[filename].content, encoding, errors)
            except KeyError:
                file = None
        else:
            assert False  # pragma: no cover

        if file is None:
            # It is *not* an error if filename doesn't exist under path; e.g.
            # if config.txt doesn't exist that just means a purely default
            # config. Likewise, if edid.dat doesn't exist, that's normal. In
            # this case we return an "empty" file, but we *don't* add an entry
            # to files
            file = BootFile.empty(filename)
        else:
            self._timestamp = max(self._timestamp, file.timestamp)
            self._hash.update(file.content)
            self._files[filename] = file
        return file
