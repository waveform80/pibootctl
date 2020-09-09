# Copyright (c) 2020 Canonical Ltd.
# Copyright (c) 2019, 2020 Dave Jones <dave@waveform.org.uk>
#
# This file is part of pibootctl.
#
# pibootctl is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pibootctl is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pibootctl.  If not, see <https://www.gnu.org/licenses/>.

"""
The :mod:`pibootctl.parser` module provides the :class:`BootParser` class for
parsing the boot configuration of the Raspberry Pi.

The output of this class consists of derivatives of :class:`BootLine`
(:class:`BootSection`, :class:`BootCommand`, etc.) and :class:`BootFile`
instances, which in turn reference :class:`BootConditions` instances to
indicate the context in which they were found.

.. autoclass:: BootParser
    :members:

.. autoclass:: BootLine

.. autoclass:: BootSection

.. autoclass:: BootCommand

.. autoclass:: BootInclude

.. autoclass:: BootFile

.. autoclass:: BootConditions
    :members:
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


def coalesce(*values, default=None):
    for value in values:
        if value is not None:
            return value
    return default


class BootInvalid(Warning):
    "Raised when an invalid line is encountered"


class BootLine:
    """
    Represents a line in a boot configuration. This is effectively an abstract
    base class and should never appear in output itself. Provides four
    attributes:

    .. attribute:: filename

        A :class:`str` indicating the path (relative to the configuration's
        root) of the file containing the line.

    .. attribute:: linenum

        The 1-based line number of the line.

    .. attribute:: conditions

        A :class:`BootConditions` specifying the filters in effect for this
        configuration line.

    .. attribute:: comment

        Any comment that appears after other content on the line, or
        :data:`None` if no comment was present
    """
    def __init__(self, filename, linenum, conditions, comment=None):
        self.filename = filename
        self.linenum = linenum
        self.conditions = conditions
        self.comment = comment

    def compare(self, other):
        if not isinstance(other, BootLine):
            raise ValueError('other is not a BootLine')
        result = set()
        if self.filename == other.filename and self.linenum == other.linenum:
            result.add('location')
        if self.conditions == other.conditions:
            result.add('conditions')
        if self.comment == other.comment:
            result.add('comment')
        return result

    def __eq__(self, other):
        try:
            return self.compare(other) == {
                'location', 'conditions', 'comment', 'key', 'value'}
        except ValueError:
            return NotImplemented


class BootComment(BootLine):
    """
    A derivative of :class:`BootLine` for lines consisting purely of ``#
    comments`` in a boot configuration.
    """
    def compare(self, other):
        result = super().compare(other)
        if isinstance(other, BootComment):
            result |= {'key', 'value'}
        return result

    def __repr__(self):
        return (
            'BootComment(filename={self.filename!r}, linenum={self.linenum!r}, '
            'comment={self.comment!r})'.format(self=self))


class BootSection(BootLine):
    """
    A derivative of :class:`BootLine` for ``[conditional sections]`` in a boot
    configuration. Adds a single attribute:

    .. attribute:: section

        The criteria of the section (everything between the square brackets).

    .. note::

        The :attr:`conditions` for a :class:`BootSection` instance *includes*
        the filters defined by that section.
    """
    def __init__(self, filename, linenum, conditions, section, comment=None):
        super().__init__(filename, linenum, conditions, comment)
        self.section = section

    def compare(self, other):
        result = super().compare(other)
        if isinstance(other, BootSection):
            result.add('key')
            if self.section == other.section:
                result.add('value')
        return result

    def __str__(self):
        return '[{self.section}]'.format(self=self)

    def __repr__(self):
        return (
            'BootSection(filename={self.filename!r}, linenum={self.linenum!r}, '
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

        The HDMI display that the command applies to. This is usually
        :data:`None` unless the command has an explicit hdmi suffix (":"
        separated after the :attr:`command` title but before the "="), or the
        command appears in an [HDMI:1] section.
    """
    def __init__(self, filename, linenum, conditions, command, params,
                 hdmi=None, comment=None):
        super().__init__(filename, linenum, conditions, comment)
        self.command = command
        self.params = params
        self.hdmi = hdmi

    def compare(self, other):
        result = super().compare(other)
        if isinstance(other, BootCommand):
            if self.command == other.command and \
                    coalesce(self.hdmi, other.hdmi, 0) == \
                    coalesce(other.hdmi, self.hdmi, 0):
                result.add('key')
                if self.params == other.params:
                    result.add('value')
        return result

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
            'BootCommand(filename={self.filename!r}, linenum={self.linenum!r}, '
            'command={self.command!r}, params={self.params!r}, '
            'hdmi={self.hdmi!r})'.format(self=self))


class BootInclude(BootLine):
    """
    A derivative of :class:`BootLine` representing an "include" command in a
    boot configuration. Adds a single attribute:

    .. attribute:: include

        The name of the file to be included.
    """
    def __init__(self, filename, linenum, conditions, include, comment=None):
        super().__init__(filename, linenum, conditions, comment)
        self.include = include

    def compare(self, other):
        result = super().compare(other)
        if isinstance(other, BootInclude):
            result.add('key')
            if self.include == other.include:
                result.add('value')
        return result

    def __str__(self):
        return 'include {self.include}'.format(self=self)

    def __repr__(self):
        return (
            'BootInclude(filename={self.filename!r}, linenum={self.linenum!r}, '
            'include={self.include!r})'.format(self=self))


class BootOverlay(BootLine):
    """
    A derivative of :class:`BootLine` representing a device-tree overlay
    ("dtoverlay=") command in a boot configuration. Adds a single attribute:

    .. attribute:: overlay

        The name of the device-tree overlay to load.
    """
    def __init__(self, filename, linenum, conditions, overlay, comment=None):
        super().__init__(filename, linenum, conditions, comment)
        self.overlay = overlay

    def compare(self, other):
        result = super().compare(other)
        if isinstance(other, BootOverlay):
            result.add('key')
            if self.overlay == other.overlay:
                result.add('value')
        return result

    def __str__(self):
        return 'dtoverlay={self.overlay}'.format(self=self)

    def __repr__(self):
        return (
            'BootOverlay(filename={self.filename!r}, linenum={self.linenum!r}, '
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
    def __init__(self, filename, linenum, conditions, overlay, param, value,
                 comment=None):
        super().__init__(filename, linenum, conditions, comment)
        self.overlay = overlay
        self.param = param
        self.value = value

    def compare(self, other):
        result = super().compare(other)
        if isinstance(other, BootParam):
            if self.overlay == other.overlay and self.param == other.param:
                result.add('key')
                if self.value == other.value:
                    result.add('value')
        return result

    def __str__(self):
        return 'dtparam={self.param}={self.value}'.format(self=self)

    def __repr__(self):
        return (
            'BootParam(filename={self.filename!r}, linenum={self.linenum!r}, '
            'overlay={self.overlay!r}, param={self.param!r}, '
            'value={self.value!r})'.format(self=self))


class BootConditions(namedtuple('BootConditions', (
        'pi',
        'hdmi',
        'edid',
        'serial',
        'gpio',
        'none',
        'suppress_count'
    ))):
    """
    Represents the set of conditional filters that apply to a given
    :class:`BootLine`. The class implements methods necessary to compare
    instances as if they were sets.

    For example::

        >>> cond_all = BootConditions()
        >>> cond_pi3 = BootConditions(pi='pi3')
        >>> cond_pi3p = BootConditions(pi='pi3p')
        >>> cond_serial = BootConditions(pi='pi3', serial=0x12345678)
        >>> cond_all == cond_pi3
        False
        >>> cond_all >= cond_pi3
        True
        >>> cond_pi3 > cond_pi3p
        True
        >>> cond_serial < cond_pi3
        True
        >>> cond_serial < cond_pi3p
        False

    .. attribute:: pi

        The model of pi that the section applies to. See `conditional
        filters`_ for details of valid values. This represents sections
        like ``[pi3]``.

    .. attribute:: hdmi

        The index of the HDMI port (0 or 1) that settings within this section
        will apply to, if no index-suffix is provided by the setting itself.
        This represents sections like ``[HDMI:0]``.

    .. attribute:: edid

        The EDID of the display that the section applies to. This represents
        sections like ``[EDID=VSC-TD2220]``.

    .. attribute:: serial

        The serial number of the Pi that settings within this section will
        apply to, stored as an :class:`int`. This represents sections like
        ``[0x12345678]``.

    .. attribute:: gpio

        The GPIO number and state that must be matched for settings in this
        section to apply, stored as a (gpio, state) tuple. This represents
        sections like ``[gpio2=0]``.

    .. attribute:: none

        If this is :data:`True` then a ``[none]`` section has been encountered
        and no settings apply.

    .. attribute:: suppress_count

        This is a "suppression count" used to track sections within included
        files that are currently disabled (because the include occurred within
        a section that itself is disabled).

    .. _conditional filters: https://www.raspberrypi.org/documentation/configuration/config-txt/conditional.md
    """
    __slots__ = ()

    def __new__(cls, pi=None, hdmi=None, edid=None, serial=None, gpio=None,
                none=False, suppress_count=0):
        return super().__new__(
            cls, pi, hdmi, edid, serial, gpio, none, suppress_count)

    def __eq__(self, other):
        if not isinstance(other, BootConditions):
            return NotImplemented
        return (
            self.pi == other.pi and
            self.hdmi == other.hdmi and
            self.edid == other.edid and
            self.serial == other.serial and
            self.gpio == other.gpio and
            self.none == other.none
            # NOTE: suppress_count is deliberately excluded here; it is nothing
            # to do with the conditional filters themselves but is an artefact
            # of their effect on includes
        )

    def __le__(self, other):
        if not isinstance(other, BootConditions):
            return NotImplemented
        return (
            (self.pi == other.pi or other.pi is None or (self.pi, other.pi) in {
                ('pi3+', 'pi3'),
                ('pi0w', 'pi0'),
            }) and
            (self.hdmi == other.hdmi or other.hdmi is None) and
            (self.edid == other.edid or other.edid is None) and
            (self.serial == other.serial or other.serial is None) and
            (self.gpio == other.gpio or other.gpio is None) and
            (self.none == other.none or not other.none)
            # See note above regarding suppress_count
        )

    def __ne__(self, other):
        return not (self == other)

    def __ge__(self, other):
        return not (self < other)

    def __lt__(self, other):
        return (self <= other) and (self != other)

    def __gt__(self, other):
        return (self >= other) and (self != other)

    def evaluate(self, section):
        """
        Calculates a new conditional state (based upon the current conditional
        state) from the specified *section* criteria. Returns a new
        :class:`BootConditions` instance.
        """
        # Derived from information at [COND]
        if section == 'all':
            return self._replace(pi=None, hdmi=None, edid=None, serial=None,
                                 gpio=None, none=False)
        elif section == 'none':
            return self._replace(none=True)
        elif section.startswith('HDMI:'):
            try:
                return self._replace(hdmi={
                    'HDMI:0': 0,
                    'HDMI:1': 1,
                }[section])
            except KeyError:
                # Ignore invalid filters (as the bootloader does)
                return self
        elif section.startswith('EDID='):
            return self._replace(edid=section[len('EDID='):])
        elif section.startswith('gpio'):
            s = section[len('gpio'):]
            gpio, value = s.split('=', 1)
            try:
                gpio = int(gpio)
                value = bool(int(value))
            except ValueError:
                return self
            else:
                return self._replace(gpio=(gpio, value))
        elif section.startswith('0x'):
            try:
                return self._replace(serial=int(section, base=16))
            except ValueError:
                return self
        elif section.startswith('pi'):
            if section in {'pi0', 'pi0w', 'pi1', 'pi2', 'pi3', 'pi3+', 'pi4'}:
                return self._replace(pi=section)
            else:
                return self
        else:
            warnings.warn(
                BootInvalid('unrecognized conditional: {}'.format(section)))
            return self
        assert False, 'invalid evaluate state'

    def generate(self, context=None):
        """
        Given *context*, a :class:`BootConditions` instance representing the
        currently active conditional sections, this method yields the
        conditional secitons required to set the conditions to this instance.
        If *context* is not specified, it defaults to conditions equivalent
        to ``[any]``, which is the default in the Pi bootloader.

        For example::

            >>> current = BootConditions(pi='pi2', gpio=(4, True))
            >>> wanted = BootConditions()
            >>> print('\\n'.join(wanted.generate(current)))
            [all]
            >>> wanted = BootConditions(pi='pi4')
            >>> print('\\n'.join(wanted.generate(current)))
            [all]
            [pi4]
            >>> current = BootConditions(pi='pi2')
            >>> print('\\n'.join(wanted.generate(current)))
            [pi4]
            >>> current = BootConditions(none=True)
            >>> print('\\n'.join(wanted.generate(current)))
            [all]
            [pi3]

        .. note::

            The yielded strings do *not* end with a line terminator.
        """
        if context is None:
            context = BootConditions()
        # If we have to "undo" any conditionals (because the context conditions
        # limit gpio, for example but our conditions don't) then reset
        # everything with [all]
        if context.none or any(
                old is not None and new is None
                for old, new in zip(context[:-2], self[:-2])):
            yield '[all]'
        if self.pi is not None:
            yield '[{self.pi}]'.format(self=self)
        if self.hdmi is not None:
            yield '[HDMI:{self.hdmi}]'.format(self=self)
        if self.edid is not None:
            yield '[EDID={self.edid}]'.format(self=self)
        if self.serial is not None:
            yield '[0x{self.serial:X}]'.format(self=self)
        if self.gpio is not None:
            yield '[gpio{self.gpio[0]:d}={self.gpio[1]:d}]'.format(self=self)

    def suppress(self):
        """
        If the current boot conditions are not :attr:`enabled`, returns a
        new :class:`BootConditions` instance with the suppression count
        incremented by one. This is used during parsing to disable all
        conditionals in suppressed includes.
        """
        if not self.enabled:
            return self._replace(suppress_count=self.suppress_count + 1)
        else:
            return self

    @property
    def enabled(self):
        """
        Returns :data:`True` if parsed items are currently effective. If this
        is :data:`False`, parsed items are ignored.
        """
        return (
            # Cannot currently assess HDMI, EDID, or GPIO criteria
            not self.none and
            (self.pi is None or self.pi in get_board_types()) and
            (self.serial is None or self.serial == get_board_serial()) and
            (self.suppress_count == 0)
        )


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
        return cls(filename, datetime(1970, 1, 1), b'', encoding, errors)

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

    * a :class:`dict` mapping filenames to :class:`BootFile` instances;
      effectively the output of :attr:`files` after parsing
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
        self._timestamp = datetime(1970, 1, 1)  # UNIX epoch
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

    def _parse(self, filename, conditions=None):
        overlay = 'base'
        if conditions is None:
            conditions = BootConditions()
        for linenum, content, comment in self._read_text(filename):
            if not content:
                yield BootComment(filename, linenum, conditions, comment)
            elif content.startswith('[') and content.endswith(']'):
                content = content[1:-1]
                conditions = conditions.evaluate(content)
                yield BootSection(
                    filename, linenum, conditions, content, comment=comment)
            elif '=' in content:
                cmd, value = content.split('=', 1)
                # We deliberately don't strip cmd or value here because the
                # bootloader doesn't either; whitespace on either side of
                # the = is significant and can invalidate lines
                if cmd in {'device_tree_overlay', 'dtoverlay'}:
                    if ':' in value:
                        overlay, params = value.split(':', 1)
                        yield BootOverlay(
                            filename, linenum, conditions, overlay,
                            comment=comment)
                        for param, value in self._parse_params(overlay, params):
                            yield BootParam(
                                filename, linenum, conditions, overlay, param,
                                value, comment=comment)
                    else:
                        overlay = value or 'base'
                        yield BootOverlay(
                            filename, linenum, conditions, overlay,
                            comment=comment)
                elif cmd in {'device_tree_param', 'dtparam'}:
                    for param, value in self._parse_params(overlay, value):
                        yield BootParam(
                            filename, linenum, conditions, overlay, param,
                            value, comment=comment)
                else:
                    if ':' in cmd:
                        cmd, hdmi = cmd.split(':', 1)
                        try:
                            hdmi = int(hdmi)
                        except ValueError:
                            hdmi = None
                    else:
                        hdmi = conditions.hdmi
                    yield BootCommand(
                        filename, linenum, conditions, cmd, value, hdmi=hdmi,
                        comment=comment)
            elif content.startswith('include'):
                command, included = content.split(None, 1)
                yield BootInclude(filename, linenum, conditions, included)
                yield from self._parse(included, conditions.suppress())
            elif content.startswith('initramfs'):
                command, initrd, address = content.split(None, 2)
                yield BootCommand(
                    filename, linenum, conditions, command, (initrd, address),
                    comment=comment)
            else:
                warnings.warn(BootInvalid(
                    "{filename}:{linenum} invalid line".format(
                        filename=filename, linenum=linenum)))

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
        for linenum, line in enumerate(
                self._open(filename, encoding='ascii', errors='replace').lines(),
                start=1):
            # The bootloader ignores everything beyond column 80 and
            # leading whitespace. The following slicing and stripping of
            # the string is done in a precise order to ensure that we capture
            # any comments fully, but ignore all non-comment chars beyond
            # column 80 *before* stripping leading spaces
            try:
                i = line.index('#')
            except ValueError:
                comment = None
            else:
                line, comment = line[:i], line[i + 1:].rstrip()
            line = line.rstrip()[:80].lstrip()
            if not line.strip() and comment is None:
                continue
            yield linenum, line, comment

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
            assert False, 'invalid path type'

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


# [COND]:
# https://www.raspberrypi.org/documentation/configuration/config-txt/conditional.md
