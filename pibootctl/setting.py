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
The :mod:`pibootctl.setting` module defines all the classes used to represent
boot configuration settings:

.. image:: images/setting_hierarchy.*
    :align: center

The base of the hierarchy is :class:`Setting` but this is effectively an
abstract class and it is rare that anyone will need to use it directly. Rather
you should derive from one of the concrete implementations below it like
:class:`OverlayParam`, :class:`Command`, or one of the type-specializations
like :class:`CommandBool`, :class:`CommandInt`, etc.

.. note::

    For the sake of brevity, only the generic classes defined in
    :mod:`pibootctl.setting` are documented here. There are also specialization
    classes specific to individual settings defined (for cases of complex
    inter-dependencies, e.g. how the Bluetooth enabled status affects the
    default serial UART).

    Developers are advised to familiarize themselves with the full range of
    classes in this module before defining additional ones.

.. autoclass:: Setting
    :members:

.. autoclass:: Overlay
    :members: overlay

.. autoclass:: OverlayParam
    :members: param

.. autoclass:: OverlayParamInt

.. autoclass:: OverlayParamBool

.. autoclass:: Command
    :members: commands, index

.. autoclass:: CommandInt

.. autoclass:: CommandIntHex

.. autoclass:: CommandBool

.. autoclass:: CommandBoolInv

.. autoclass:: CommandForceIgnore
    :members: force, ignore

.. autoclass:: CommandMaskMaster

.. autoclass:: CommandMaskDummy

.. autoclass:: CommandFilename
    :members: filename

.. autoclass:: CommandIncludedFile

.. autoexception:: ParseWarning

.. autoexception:: ValueWarning
"""

import gettext
import warnings
from textwrap import dedent
from functools import reduce
from collections import namedtuple
from itertools import groupby, chain
from operator import or_, itemgetter
from contextlib import contextmanager

from .exc import DelegatedOutput
from .formatter import FormatDict, TransMap, int_ranges
from .parser import BootOverlay, BootParam, BootCommand, coalesce
from .userstr import UserStr, to_bool, to_int, to_float, to_list, to_str
from .info import get_board_type, get_board_mem

_ = gettext.gettext


def format_valid_table(doc, valid):
    """
    A small utility function that replaces instances of ``{valid}`` in *doc*
    with a formatted table containing the keys and values of the :class:`dict`
    *valid*.
    """
    return dedent(doc).format_map(
        TransMap(valid=FormatDict(
            valid, key_title=_('Value'), value_title=_('Meaning'))))


class ParseWarning(Warning):
    """
    Warning class used by :meth:`Setting.extract` to warn about invalid
    values while parsing.
    """


class ValueWarning(Warning):
    """
    Warning class used by :meth:`Setting.validate` to warn about dangerous
    or inappropriate configurations.
    """


class Setting:
    """
    Represents a configuration setting.

    Each setting has a *name* which uniquely identifies the setting, a
    *default* value, and an optional *doc* string. The life-cycle of a typical
    setting in the scenario where the active boot configuration is being
    changed is:

    * :meth:`extract` the value of a setting from parsed configuration lines
    * :meth:`update` the value of a setting from user-provided values
    * :meth:`validate` a setting in the wider context of a configuration
    * generate :meth:`output` to represent the setting in a new config.txt

    Optionally:

    * :attr:`hint` may be queried to describe a value in human-readable terms
    """
    def __init__(self, name, *, default=None, doc=''):
        # self._settings is set in Settings.__init__ and Settings.copy
        self._settings = None
        self._name = name
        self._default = default
        self._value = None
        self._doc = dedent(doc).format(name=name, default=default)
        self._lines = ()

    def __repr__(self):
        return (
            '<{self.__class__.__name__} name={self.name!r} '
            'default={self.default!r} value={self.value!r} '
            'modified={self.modified}>'.format(self=self))

    @property
    def name(self):
        """
        The name of the setting. This is a dot-delimited list of strings; note
        that the individual components do not have to be valid identifiers. For
        example, "boot.kernel.64bit".
        """
        return self._name

    @property
    def doc(self):
        """
        A description of the setting, used as help-text on the command line.
        """
        return self._doc

    @property
    def key(self):
        """
        Returns a tuple of strings which will be used to order the output of
        :meth:`output` in the generated configuration.

        .. note::

            The output of this property *must* be unique for each setting,
            unless a setting delegates all its output to another setting.
        """
        raise NotImplementedError

    @property
    def modified(self):
        """
        Returns :data:`True` when the setting has been modified. Note that it
        is *not* sufficient to simply compare :attr:`value` to :attr:`default`
        as some defaults are context- or platform-specific.
        """
        return self._value is not None

    @property
    def default(self):
        """
        The default value of this setting. The default may be sensitive to the
        wider context of :class:`~pibootctl.store.Settings` (i.e. the default
        of one setting can change depending on the current value of other
        settings).
        """
        return self._default

    @property
    def value(self):
        """
        Returns the current value of the setting (or the :attr:`default` if the
        setting has not been :attr:`modified`).
        """
        # Must use self.default here, not self._default as descendents may
        # calculate more complex defaults
        return self.default if self._value is None else self._value

    @property
    def lines(self):
        """
        Returns the :class:`~pibootctl.parser.BootLine` items which (if enabled
        by conditionals) affected the value of the setting, in the reverse
        order they were encountered while parsing (so the first *enabled* item
        holds the current value).
        """
        return self._lines

    @property
    def hint(self):
        """
        Provides a human-readable interpretation of the state of the setting.
        Used by the "dump" and "show" commands to provide translations of
        default and current values.

        Must return :data:`None` if no explanation is available or necessary.
        Otherwise, must return a :class:`str`.
        """
        return None

    def extract(self, config):
        """
        Given a *config* which must be a sequence of
        :class:`~pibootctl.parser.BootLine` items, yields each line that
        potentially affects the setting's value (including those currently
        disabled by conditionals), and the new value that the line produces (or
        :data:`None` indicating that the value is now, or is still, the default
        state).

        .. note::

            This method is *not* influenced by conditionals that disable a
            line. In this case the method must still yield the line and the
            value it would produce (were it enabled). The caller will deal with
            the fact the line is currently disabled (but needs to be aware of
            such lines for the configuration mutator).

            For this reason (and others) this method must *not* affect
            :attr:`value` directly; the caller will handle mutating the value
            when required.
        """
        raise NotImplementedError

    def update(self, value):
        """
        Given a *value*, returns it transformed to the setting's native type
        (typically an :class:`int` or :class:`bool` but can be whatever type is
        appropriate).

        The *value* may be a regular type (:class:`str`, :class:`int`,
        :data:`None`, etc.) as deserialized from one of the input formats (JSON
        or YAML). Alternatively, it may be a
        :class:`~pibootctl.userstr.UserStr`, indicating that the value is a
        string given by the user on the command line and should be interpreted
        by the setting accordingly.

        .. note::

            Note to implementers: the method must *not* affect :attr:`value`
            directly; the caller will handle this.
        """
        return value

    def validate(self):
        """
        Validates the setting within the context of the other
        :class:`~pibootctl.store.Settings`. Raises :exc:`ValueError` in the
        event that the current value is invalid. May optionally use
        :exc:`ValueWarning` to warn about dangerous or inappropriate
        configurations.
        """

    def output(self):
        """
        Yields lines of configuration to represent the current state of the
        setting (taking in account the context of other
        :class:`~pibootctl.store.Settings`).
        """
        # If a setting's output is handled by another setting (e.g. for cases
        # where a single command is broken up into multiple settings), raise
        # DeletedOutput(master) where master is the setting that handles all
        # output for the subordinate settings. This is necessary to permit the
        # containing configuration to track which settings have actually
        # generated output (to avoid duplication of lines in such cases).
        raise NotImplementedError

    @contextmanager
    def _override(self, value):
        """
        Used as a context manager, temporarily overrides the *value* of this
        setting until the contextual block ends. Note that *value* does **not**
        pass through :meth:`update` via this route.
        """
        old_value = self._value
        self._value = value
        try:
            yield
        finally:
            self._value = old_value

    def _relative(self, path):
        """
        Returns the name of this setting with a suffix replaced by *path*.

        The number of leading dot-characters in *path* dictate how many
        dot-separated components of this setting's name are removed before
        appending the remainder of *path*. For example:

            >>> s.name
            'foo.bar'
            >>> s._relative('baz')
            'foo.bar.baz'
            >>> s._relative('.baz')
            'foo.baz'
            >>> s._relative('.baz.quux')
            'foo.baz.quux'
            >>> s._relative('..baz.quux')
            'baz.quux'

        In other words, a *path* with no dot-prefix returns children of the
        current setting, a *path* with a single dot-prefix returns siblings of
        the current setting, and so on.
        """
        parts = self.name.split('.')
        while path[:1] == '.':
            del parts[-1]
            path = path[1:]
        path = path.split('.')
        return '.'.join(parts + path)

    def _query(self, name):
        """
        Queries another setting in the same set as this one.

        This method should be used in preference to simply querying
        ``self._settings()[name]`` as it's possible that the named setting has
        been "hidden" in the set by a filter. This method bypasses the visible
        filter to ensure that settings can always query other settings.
        """
        assert self._settings
        # This is set to a weakref.ref by the Settings initializer (and
        # Settings.copy); hence why we call it to return the actual reference.
        return self._settings()._items[name]


class Overlay(Setting):
    """
    Represents a boolean setting that is "on" if the represented *overlay* is
    present, and "off" otherwise.
    """
    def __init__(self, name, *, overlay, default=False, doc=''):
        super().__init__(name, default=default, doc=doc)
        self._overlay = overlay

    @property
    def overlay(self):
        """
        The name of the overlay this parameter affects.
        """
        return self._overlay

    @property
    def key(self):
        return ('overlays', '' if self.overlay == 'base' else self.overlay)

    def extract(self, config):
        for item in config:
            if isinstance(item, BootOverlay):
                if item.overlay == self.overlay:
                    yield item, True

    def update(self, value):
        return to_bool(value)

    def output(self):
        if self.value:
            yield 'dtoverlay={self.overlay}'.format(self=self)


class OverlayParam(Overlay):
    """
    Represents a *param* to a device-tree *overlay*. Like :class:`Setting`,
    this is effectively an abstract base class to be derived from.
    """
    def __init__(self, name, *, overlay='base', param, default=None, doc=''):
        super().__init__(name, overlay=overlay, default=default, doc=doc)
        self._param = param

    @property
    def param(self):
        """
        The name of the parameter within the base overlay that this setting
        represents.
        """
        return self._param

    @property
    def key(self):
        return (
            'overlays',
            '' if self.overlay == 'base' else self.overlay,
            self.param
        )

    def extract(self, config):
        value = None
        for item in config:
            if isinstance(item, BootOverlay):
                if item.overlay == self.overlay:
                    yield item, value
            elif isinstance(item, BootParam):
                if item.overlay == self.overlay and item.param == self.param:
                    value = item.value
                    yield item, value

    def update(self, value):
        return value

    def output(self):
        # We don't worry about outputting the dtoverlay; presumably that is
        # represented by another setting and the key property will order our
        # output appropriately after the correct dtoverlay output
        if self.modified:
            yield 'dtparam={self.param}={self.value}'.format(self=self)


class OverlayParamStr(OverlayParam):
    """
    Represents a string parameter to a device-tree overlay.

    The *valid* parameter may optionally provide a dictionary mapping
    valid string values for the command to explanations, to be provided by
    the basic :attr:`~Setting.hint` implementation.
    """
    def __init__(self, name, *, overlay='base', param, default=None, doc='',
                 valid=None):
        if valid is None:
            valid = {}
        doc = format_valid_table(doc, valid)
        super().__init__(name, overlay=overlay, param=param, default=default,
                         doc=doc)
        self._valid = valid

    @property
    def hint(self):
        return self._valid.get(self.value)

    def validate(self):
        if self._valid and self.value not in self._valid:
            raise ValueError(_(
                '{self.name} must be one of {valid}'
            ).format(self=self, valid=', '.join(self._valid)))


class OverlayParamInt(OverlayParam):
    """
    Represents an integer parameter to a device-tree overlay.

    The *valid* parameter may optionally provide a dictionary mapping valid
    integer values for the command to string explanations, to be provided by
    the basic :attr:`~Setting.hint` implementation.
    """
    def __init__(self, name, *, overlay='base', param, default=0, doc='',
                 valid=None):
        if valid is None:
            valid = {}
        doc = format_valid_table(doc, valid)
        super().__init__(name, overlay=overlay, param=param, default=default,
                         doc=doc)
        self._valid = valid

    @property
    def hint(self):
        return self._valid.get(self.value)

    def extract(self, config):
        for item, value in super().extract(config):
            try:
                yield item, None if value is None else int(value)
            except ValueError:
                warnings.warn(ParseWarning(
                    '{item.filename} line {item.linenum}: invalid integer '
                    '{value!r}'.format(item=item, value=value)))
                yield item, None

    def update(self, value):
        return to_int(super().update(value))

    def validate(self):
        if self._valid and self.value not in self._valid:
            raise ValueError(_(
                '{self.name} must be in the range {valid}'
            ).format(self=self, valid=int_ranges(self._valid)))


class OverlayParamBool(OverlayParam):
    """
    Represents a boolean parameter to the base device-tree overlay.
    """
    def __init__(self, name, *, overlay='base', param, default=False, doc=''):
        super().__init__(name, overlay=overlay, param=param, default=default,
                         doc=doc)

    def extract(self, config):
        for item, value in super().extract(config):
            yield item, None if value is None else (value == 'on')

    def update(self, value):
        return to_bool(super().update(value))

    def output(self):
        if self.modified:
            yield 'dtparam={self.param}={value}'.format(
                self=self, value='on' if self.value else 'off')


class Command(Setting):
    """
    Represents a string-valued configuration *command* or *commmands* (one
    of these must be specified, but not both). If multiple *commands* are
    represented, only the first will be generated by :meth:`output` in this
    base class.

    This is also the base class for most simple-valued configuration commands
    (integer, boolean, etc).
    """
    def __init__(self, name, *, command=None, commands=None, default=None,
                 doc='', index=None):
        assert (command is None) ^ (commands is None), \
            'command or commands must be given, not both'
        doc = dedent(doc).format_map(TransMap(index=index))
        super().__init__(name, default=default, doc=doc)
        if command is None:
            self._commands = tuple(commands)
        else:
            self._commands = (command,)
        self._index = index

    @property
    def commands(self):
        """
        The configuration commands that this setting represents.
        """
        return self._commands

    @property
    def index(self):
        """
        The index of this setting for multi-valued settings (e.g. settings
        which apply to HDMI outputs).
        """
        return self._index

    @property
    def key(self):
        return ('commands', self.name)

    def extract(self, config):
        for item in config:
            if (
                    isinstance(item, BootCommand) and
                    item.command in self.commands and
                    coalesce(item.hdmi, 0) == coalesce(self.index, 0)):
                yield item, item.params

    def output(self, fmt=''):
        if self.modified:
            if self.index:
                template = '{self.commands[0]}:{self.index}={self.value:{fmt}}'
            else:
                template = '{self.commands[0]}={self.value:{fmt}}'
            yield template.format(self=self, fmt=fmt)


class CommandStr(Command):
    """
    Represents a string-valued configuration *command* or *commands*.

    The *valid* parameter may optionally provide a dictionary mapping
    valid string values for the command to explanations, to be provided by
    the basic :attr:`~Setting.hint` implementation.
    """
    def __init__(self, name, *, command=None, commands=None, default=None,
                 doc='', index=0, valid=None):
        if valid is None:
            valid = {}
        doc = format_valid_table(doc, valid)
        super().__init__(name, command=command, commands=commands,
                         default=default, doc=doc, index=index)
        self._valid = valid

    @property
    def hint(self):
        return self._valid.get(self.value)

    def update(self, value):
        return to_str(value)

    def validate(self):
        if self._valid and self.value not in self._valid:
            raise ValueError(_(
                '{self.name} must be one of {valid}'
            ).format(self=self, valid=', '.join(self._valid)))


class CommandInt(Command):
    """
    Represents an integer-valued configuration *command* or *commands*.

    The *valid* parameter may optionally provide a dictionary mapping valid
    integer values for the command to string explanations, to be provided by
    the basic :attr:`~Setting.hint` implementation.
    """
    def __init__(self, name, *, command=None, commands=None, default=0, doc='',
                 index=0, valid=None):
        if valid is None:
            valid = {}
        doc = format_valid_table(doc, valid)
        super().__init__(name, command=command, commands=commands,
                         default=default, doc=doc, index=index)
        self._valid = valid

    @property
    def hint(self):
        return self._valid.get(self.value)

    def extract(self, config):
        for item, value in super().extract(config):
            try:
                yield item, to_int(value)
            except ValueError:
                warnings.warn(ParseWarning(
                    '{item.filename} line {item.linenum}: invalid integer '
                    '{value!r}'.format(item=item, value=value)))
                # Invalid integers get treated as the setting default (based on
                # what the bootloader does too - it *doesn't* ignore the
                # setting)
                yield item, None

    def update(self, value):
        return to_int(value)

    def validate(self):
        if self._valid and self.value not in self._valid:
            raise ValueError(_(
                '{self.name} must be in the range {valid}'
            ).format(self=self, valid=int_ranges(self._valid)))

    def output(self, fmt='d'):
        yield from super().output(fmt)


class CommandIntHex(CommandInt):
    """
    An integer-valued configuration *command* or *commands* that are typically
    represented in hexi-decimal (like memory addresses).
    """
    @property
    def hint(self):
        return '{:#x}'.format(self.value)

    def output(self, fmt='#x'):
        yield from super().output(fmt)


class CommandBool(Command):
    """
    Represents a boolean-valued configuration *command* or *commands*.
    """
    def __init__(self, name, *, command=None, commands=None, default=False,
                 doc='', index=0):
        super().__init__(name, command=command, commands=commands,
                         default=default, doc=doc, index=index)

    def extract(self, config):
        for item, value in super().extract(config):
            try:
                yield item, bool(to_int(value))
            except ValueError:
                warnings.warn(ParseWarning(
                    '{item.filename} line {item.linenum}: invalid bool '
                    '{value!r}'.format(item=item, value=value)))
                yield item, None

    def update(self, value):
        return to_bool(value)

    def output(self, fmt='d'):
        yield from super().output(fmt)


class CommandBoolInv(CommandBool):
    """
    Represents a boolean-valued configuration *command* or *commands* with
    inverted logic, e.g. video.overscan.enabled represents the
    ``disable_overscan`` setting and therefore its value is always the opposite
    of the actual written value.
    """
    def extract(self, config):
        for item, value in super().extract(config):
            yield item, not value

    def output(self, fmt='d'):
        if self.modified:
            with self._override(not self.value):
                yield from super().output(fmt)


class CommandForceIgnore(CommandBool):
    """
    Represents the tri-valued configuration values with *force* and *ignore*
    commands, e.g. ``hdmi_force_hotplug`` and ``hdmi_ignore_hotplug``.

    For these cases, when both commands are "0" the setting is considered to
    have the value :data:`None` (which in most cases means "determine
    automatically"). When the *force* command is "1", the setting is
    :data:`True` and thus when the *ignore* command is "1", the setting is
    :data:`False`. When both are "1" (a contradictory setting) the final
    setting encountered takes precedence.
    """
    def __init__(self, name, *, force, ignore, doc='', index=0):
        super().__init__(name, commands=(force, ignore), default=None, doc=doc)
        self._force = force
        self._ignore = ignore
        self._index = index

    @property
    def force(self):
        """
        The boolean command that forces this setting on.
        """
        return self._force

    @property
    def ignore(self):
        """
        The boolean command that forces this setting off.
        """
        return self._ignore

    def extract(self, config):
        value = None
        for item in config:
            try:
                if (
                        isinstance(item, BootCommand) and
                        item.command in self.commands and
                        int(item.params)):
                    value = item.command == self.force
                    yield item, value
            except ValueError:
                warnings.warn(ParseWarning(
                    '{item.filename} line {item.linenum}: invalid integer '
                    '{item.params!r}'.format(item=item)))
                # In this case, the "value" of the command is effectively 0
                # but because this setting is only affected by "positive"
                # commands there's no change. We yield the line to indicate
                # it *attempted* to affect the setting, but with the current
                # (internal) value so it doesn't
                yield item, value

    def output(self):
        if self.modified:
            if self.index:
                template = '{command}:{self.index}=1'
            else:
                template = '{command}=1'
            yield template.format(
                self=self,
                command={
                    True:  self.force,
                    False: self.ignore,
                }[self.value],
            )


class CommandMaskMaster(CommandInt):
    """
    Represents an integer bit-mask setting as several settings. The "master"
    setting is the only one that produces any output. It defines the suffixes
    of its *dummies* (instances of :class:`CommandMaskDummy` which parse the
    same setting but produce no output of their own).

    The *mask* specifies the integer bit-mask to be applied to the underlying
    value for this setting. The right-shift will be calculated from this.
    Single-bit masks will be represented as boolean values rather than
    integers.
    """
    def __init__(self, name, *, mask, command=None, commands=None, default=0,
                 doc='', index=0, valid=None, dummies=()):
        assert mask
        super().__init__(name, command=command, commands=commands,
                         default=default, doc=doc, index=index, valid=valid)
        self._mask = mask
        self._shift = (mask & -mask).bit_length() - 1  # ffs(3)
        self._bool = (mask >> self._shift) == 1
        self._names = (self.name,) + tuple(
            self._relative(name) for name in dummies)

    def extract(self, config):
        for item, value in super().extract(config):
            value = (value & self._mask) >> self._shift
            yield item, bool(value) if self._bool else value

    def update(self, value):
        if self._bool:
            return to_bool(value)
        else:
            return super().update(value)

    def output(self):
        if any(self._query(name).modified for name in self._names):
            value = reduce(or_, (
                self._query(name).value << self._query(name)._shift
                for name in self._names
            ))
            template = '{self.commands[0]}={value:#x}'
            yield template.format(self=self, value=value)


class CommandMaskDummy(CommandMaskMaster):
    """
    Represents portions of integer bit-masks which are subordinate to a
    :class:`CommandMaskMaster` setting.
    """
    def output(self):
        # Override with appropriate DelegatedOutput in sub-classes
        if self.modified:
            raise DelegatedOutput('some.setting')
        else:
            return ()


class CommandFilename(Command):
    """
    Represents settings that contain a filename affected by the os_prefix
    command. The :attr:`filename` returns the full filename incorporating the
    value of "boot.prefix" (if set), and :attr:`~Setting.hint` outputs a
    suitable message including the full path.
    """
    @property
    def filename(self):
        """
        The full filename represented by the value, after concatenating it with
        the value of "boot.prefix".
        """
        return self._query('boot.prefix').value + self.value

    @property
    def hint(self):
        if self.value and self._query('boot.prefix').modified:
            return _('{!r} with boot.prefix').format(self.filename)
        else:
            return None


class CommandIncludedFile(CommandFilename):
    """
    Represents settings that reference a file which should be included in any
    stored boot configuration.
    """
    # This class is effectively just a flag; the store handles scanning all
    # settings for descendents of this class and incorporating their content
    # after parsing the rest of the boot configuration


class CommandDisplayGroup(CommandInt):
    """
    Represents settings that control the group of display modes used for the
    configuration of a video output, e.g. ``hdmi_group`` or ``dpi_group``.
    """
    def __init__(self, name, *, command=None, commands=None, default=0, doc='',
                 index=0):
        super().__init__(name, command=command, commands=commands,
                         default=default, doc=doc, index=index, valid={
                             0: _('auto from EDID'),
                             1: 'CEA',
                             2: 'DMT',
                         })


class DisplayMode(namedtuple('DisplayMode', (
    'resolution', 'refresh', 'ratio', 'notes'))):
    __slots__ = ()
    def __new__(cls, resolution='', refresh='', ratio='', notes=''):
        return super().__new__(cls, resolution, refresh, ratio, notes)

    def __str__(self):
        if self.resolution:
            if self.notes:
                template = '{self.resolution} @{self.refresh} ({self.notes})'
            else:
                template = '{self.resolution} @{self.refresh}'
        else:
            template = '{self.notes}'
        return template.format(self=self)


class CommandDisplayMode(CommandInt):
    """
    Represents settings that control the mode of a video output, e.g.
    ``hdmi_mode`` or ``dpi_mode``.
    """
    def __init__(self, name, *, command=None, commands=None, default=0, doc='',
                 index=0):
        self._valid_cea = {
            1:   DisplayMode('640x480', '60Hz',  '4:3',   'VGA'),
            2:   DisplayMode('480p',    '60Hz',  '4:3'),
            3:   DisplayMode('480p',    '60Hz',  '16:9'),
            4:   DisplayMode('720p',    '60Hz',  '16:9'),
            5:   DisplayMode('1080i',   '60Hz',  '16:9'),
            6:   DisplayMode('480i',    '60Hz',  '4:3'),
            7:   DisplayMode('480i',    '60Hz',  '16:9'),
            8:   DisplayMode('240p',    '60Hz',  '4:3'),
            9:   DisplayMode('240p',    '60Hz',  '16:9'),
            10:  DisplayMode('480i',    '60Hz',  '4:3',   'pixel quadrupling'),
            11:  DisplayMode('480i',    '60Hz',  '16:9',  'pixel quadrupling'),
            12:  DisplayMode('240p',    '60Hz',  '4:3',   'pixel quadrupling'),
            13:  DisplayMode('240p',    '60Hz',  '16:9',  'pixel quadrupling'),
            14:  DisplayMode('480p',    '60Hz',  '4:3',   'pixel doubling'),
            15:  DisplayMode('480p',    '60Hz',  '16:9',  'pixel doubling'),
            16:  DisplayMode('1080p',   '60Hz',  '16:9'),
            17:  DisplayMode('576p',    '50Hz',  '4:3'),
            18:  DisplayMode('576p',    '50Hz',  '16:9'),
            19:  DisplayMode('720p',    '50Hz',  '16:9'),
            20:  DisplayMode('1080i',   '50Hz',  '16:9'),
            21:  DisplayMode('576i',    '50Hz',  '4:3'),
            22:  DisplayMode('576i',    '50Hz',  '16:9'),
            23:  DisplayMode('288p',    '50Hz',  '4:3'),
            24:  DisplayMode('288p',    '50Hz',  '16:9'),
            25:  DisplayMode('576i',    '50Hz',  '4:3',   'pixel quadrupling'),
            26:  DisplayMode('576i',    '50Hz',  '16:9',  'pixel quadrupling'),
            27:  DisplayMode('288p',    '50Hz',  '4:3',   'pixel quadrupling'),
            28:  DisplayMode('288p',    '50Hz',  '16:9',  'pixel quadrupling'),
            29:  DisplayMode('576p',    '50Hz',  '4:3',   'pixel doubling'),
            30:  DisplayMode('576p',    '50Hz',  '16:9',  'pixel doubling'),
            31:  DisplayMode('1080p',   '50Hz',  '16:9'),
            32:  DisplayMode('1080p',   '24Hz',  '16:9'),
            33:  DisplayMode('1080p',   '25Hz',  '16:9'),
            34:  DisplayMode('1080p',   '30Hz',  '16:9'),
            35:  DisplayMode('480p',    '60Hz',  '4:3',   'pixel quadrupling'),
            36:  DisplayMode('480p',    '60Hz',  '16:9',  'pixel quadrupling'),
            37:  DisplayMode('576p',    '50Hz',  '4:3',   'pixel quadrupling'),
            38:  DisplayMode('576p',    '50Hz',  '16:9',  'pixel quadrupling'),
            39:  DisplayMode('1080i',   '50Hz',  '16:9',  'reduced blanking'),
            40:  DisplayMode('1080i',   '100Hz', '16:9'),
            41:  DisplayMode('720p',    '100Hz', '16:9'),
            42:  DisplayMode('576p',    '100Hz', '4:3'),
            43:  DisplayMode('576p',    '100Hz', '16:9'),
            44:  DisplayMode('576i',    '100Hz', '4:3'),
            45:  DisplayMode('576i',    '100Hz', '16:9'),
            46:  DisplayMode('1080i',   '120Hz', '16:9'),
            47:  DisplayMode('720p',    '120Hz', '16:9'),
            48:  DisplayMode('480p',    '120Hz', '4:3'),
            49:  DisplayMode('480p',    '120Hz', '16:9'),
            50:  DisplayMode('480i',    '120Hz', '4:3'),
            51:  DisplayMode('480i',    '120Hz', '16:9'),
            52:  DisplayMode('576p',    '200Hz', '4:3'),
            53:  DisplayMode('576p',    '200Hz', '16:9'),
            54:  DisplayMode('576i',    '200Hz', '4:3'),
            55:  DisplayMode('576i',    '200Hz', '16:9'),
            56:  DisplayMode('480p',    '240Hz', '4:3'),
            57:  DisplayMode('480p',    '240Hz', '16:9'),
            58:  DisplayMode('480i',    '240Hz', '4:3'),
            59:  DisplayMode('480i',    '240Hz', '16:9'),
            60:  DisplayMode('720p',    '24Hz',  '16:9'),
            61:  DisplayMode('720p',    '25Hz',  '16:9'),
            62:  DisplayMode('720p',    '30Hz',  '16:9'),
            63:  DisplayMode('1080p',   '120Hz', '16:9'),
            64:  DisplayMode('1080p',   '100Hz', '16:9'),
            65:  DisplayMode(notes='user timings'),
            66:  DisplayMode('720p',      '25Hz',  '64:27',   'Pi 4'),
            67:  DisplayMode('720p',      '30Hz',  '64:27',   'Pi 4'),
            68:  DisplayMode('720p',      '50Hz',  '64:27',   'Pi 4'),
            69:  DisplayMode('720p',      '60Hz',  '64:27',   'Pi 4'),
            70:  DisplayMode('720p',      '100Hz', '64:27',   'Pi 4'),
            71:  DisplayMode('720p',      '120Hz', '64:27',   'Pi 4'),
            72:  DisplayMode('1080p',     '24Hz',  '64:27',   'Pi 4'),
            73:  DisplayMode('1080p',     '25Hz',  '64:27',   'Pi 4'),
            74:  DisplayMode('1080p',     '30Hz',  '64:27',   'Pi 4'),
            75:  DisplayMode('1080p',     '50Hz',  '64:27',   'Pi 4'),
            76:  DisplayMode('1080p',     '60Hz',  '64:27',   'Pi 4'),
            77:  DisplayMode('1080p',     '100Hz', '64:27',   'Pi 4'),
            78:  DisplayMode('1080p',     '120Hz', '64:27',   'Pi 4'),
            79:  DisplayMode('1680x720',  '24Hz',  '64:27',   'Pi 4'),
            80:  DisplayMode('1680x720',  '25Hz',  '64:27',   'Pi 4'),
            81:  DisplayMode('1680x720',  '30Hz',  '64:27',   'Pi 4'),
            82:  DisplayMode('1680x720',  '50Hz',  '64:27',   'Pi 4'),
            83:  DisplayMode('1680x720',  '60Hz',  '64:27',   'Pi 4'),
            84:  DisplayMode('1680x720',  '100Hz', '64:27',   'Pi 4'),
            85:  DisplayMode('1680x720',  '120Hz', '64:27',   'Pi 4'),
            86:  DisplayMode('2560x720',  '24Hz',  '64:27',   'Pi 4'),
            87:  DisplayMode('2560x720',  '25Hz',  '64:27',   'Pi 4'),
            88:  DisplayMode('2560x720',  '30Hz',  '64:27',   'Pi 4'),
            89:  DisplayMode('2560x720',  '50Hz',  '64:27',   'Pi 4'),
            90:  DisplayMode('2560x720',  '60Hz',  '64:27',   'Pi 4'),
            91:  DisplayMode('2560x720',  '100Hz', '64:27',   'Pi 4'),
            92:  DisplayMode('2560x720',  '120Hz', '64:27',   'Pi 4'),
            93:  DisplayMode('2160p',     '24Hz',  '16:9',    'Pi 4'),
            94:  DisplayMode('2160p',     '25Hz',  '16:9',    'Pi 4'),
            95:  DisplayMode('2160p',     '30Hz',  '16:9',    'Pi 4'),
            96:  DisplayMode('2160p',     '50Hz',  '16:9',    'Pi 4'),
            97:  DisplayMode('2160p',     '60Hz',  '16:9',    'Pi 4'),
            98:  DisplayMode('4096x2160', '24Hz',  '256:135', 'Pi 4'),
            99:  DisplayMode('4096x2160', '25Hz',  '256:135', 'Pi 4'),
            100: DisplayMode('4096x2160', '30Hz',  '256:135', 'Pi 4'),
            101: DisplayMode('4096x2160', '50Hz',  '256:135', 'Pi 4'),
            102: DisplayMode('4096x2160', '60Hz',  '256:135', 'Pi 4'),
            103: DisplayMode('2160p',     '24Hz',  '64:27',   'Pi 4'),
            104: DisplayMode('2160p',     '25Hz',  '64:27',   'Pi 4'),
            105: DisplayMode('2160p',     '30Hz',  '64:27',   'Pi 4'),
            106: DisplayMode('2160p',     '50Hz',  '64:27',   'Pi 4'),
            107: DisplayMode('2160p',     '60Hz',  '64:27',   'Pi 4'),
        }
        self._valid_dmt = {
            1:  DisplayMode('640x350',   '85Hz',  '64:35'),
            2:  DisplayMode('640x400',   '85Hz',  '16:10'),
            3:  DisplayMode('720x400',   '85Hz',  '18:10'),
            4:  DisplayMode('640x480',   '60Hz',  '4:3'),
            5:  DisplayMode('640x480',   '72Hz',  '4:3'),
            6:  DisplayMode('640x480',   '75Hz',  '4:3'),
            7:  DisplayMode('640x480',   '85Hz',  '4:3'),
            8:  DisplayMode('800x600',   '56Hz',  '4:3'),
            9:  DisplayMode('800x600',   '60Hz',  '4:3'),
            10: DisplayMode('800x600',   '72Hz',  '4:3'),
            11: DisplayMode('800x600',   '75Hz',  '4:3'),
            12: DisplayMode('800x600',   '85Hz',  '4:3'),
            13: DisplayMode('800x600',   '120Hz', '4:3'),
            14: DisplayMode('848x480',   '60Hz',  '16:9'),
            15: DisplayMode('1024x768',  '43Hz',  '4:3',    'incompatible'),
            16: DisplayMode('1024x768',  '60Hz',  '4:3'),
            17: DisplayMode('1024x768',  '70Hz',  '4:3'),
            18: DisplayMode('1024x768',  '75Hz',  '4:3'),
            19: DisplayMode('1024x768',  '85Hz',  '4:3'),
            20: DisplayMode('1024x768',  '120Hz', '4:3'),
            21: DisplayMode('1152x864',  '75Hz',  '4:3'),
            22: DisplayMode('1280x768',  '60Hz',  '15:9',   'reduced blanking'),
            23: DisplayMode('1280x768',  '60Hz',  '15:9'),
            24: DisplayMode('1280x768',  '75Hz',  '15:9'),
            25: DisplayMode('1280x768',  '85Hz',  '15:9'),
            26: DisplayMode('1280x768',  '120Hz', '15:9',   'reduced blanking'),
            27: DisplayMode('1280x800',  '60',    '16:10',  'reduced blanking'),
            28: DisplayMode('1280x800',  '60Hz',  '16:10'),
            29: DisplayMode('1280x800',  '75Hz',  '16:10'),
            30: DisplayMode('1280x800',  '85Hz',  '16:10'),
            31: DisplayMode('1280x800',  '120Hz', '16:10',  'reduced blanking'),
            32: DisplayMode('1280x960',  '60Hz',  '4:3'),
            33: DisplayMode('1280x960',  '85Hz',  '4:3'),
            34: DisplayMode('1280x960',  '120Hz', '4:3',    'reduced blanking'),
            35: DisplayMode('1280x1024', '60Hz',  '5:4'),
            36: DisplayMode('1280x1024', '75Hz',  '5:4'),
            37: DisplayMode('1280x1024', '85Hz',  '5:4'),
            38: DisplayMode('1280x1024', '120Hz', '5:4',    'reduced blanking'),
            39: DisplayMode('1360x768',  '60Hz',  '16:9'),
            40: DisplayMode('1360x768',  '120Hz', '16:9',   'reduced blanking'),
            41: DisplayMode('1400x1050', '60Hz',  '4:3',    'reduced blanking'),
            42: DisplayMode('1400x1050', '60Hz',  '4:3'),
            43: DisplayMode('1400x1050', '75Hz',  '4:3'),
            44: DisplayMode('1400x1050', '85Hz',  '4:3'),
            45: DisplayMode('1400x1050', '120Hz', '4:3',    'reduced blanking'),
            46: DisplayMode('1440x900',  '60Hz',  '16:10',  'reduced blanking'),
            47: DisplayMode('1440x900',  '60Hz',  '16:10'),
            48: DisplayMode('1440x900',  '75Hz',  '16:10'),
            49: DisplayMode('1440x900',  '85Hz',  '16:10'),
            50: DisplayMode('1440x900',  '120Hz', '16:10',  'reduced blanking'),
            51: DisplayMode('1600x1200', '60Hz',  '4:3'),
            52: DisplayMode('1600x1200', '65Hz',  '4:3'),
            53: DisplayMode('1600x1200', '70Hz',  '4:3'),
            54: DisplayMode('1600x1200', '75Hz',  '4:3'),
            55: DisplayMode('1600x1200', '85Hz',  '4:3'),
            56: DisplayMode('1600x1200', '120Hz', '4:3',    'reduced blanking'),
            57: DisplayMode('1680x1050', '60Hz',  '16:10',  'reduced blanking'),
            58: DisplayMode('1680x1050', '60Hz',  '16:10'),
            59: DisplayMode('1680x1050', '75Hz',  '16:10'),
            60: DisplayMode('1680x1050', '85Hz',  '16:10'),
            61: DisplayMode('1680x1050', '120Hz', '16:10',  'reduced blanking'),
            62: DisplayMode('1792x1344', '60Hz',  '4:3'),
            63: DisplayMode('1792x1344', '75Hz',  '4:3'),
            64: DisplayMode('1792x1344', '120Hz', '4:3',    'reduced blanking'),
            65: DisplayMode('1856x1392', '60Hz',  '4:3'),
            66: DisplayMode('1856x1392', '75Hz',  '4:3'),
            67: DisplayMode('1856x1392', '120Hz', '4:3',    'reduced blanking'),
            68: DisplayMode('1920x1200', '60Hz',  '16:10',  'reduced blanking'),
            69: DisplayMode('1920x1200', '60Hz',  '16:10'),
            70: DisplayMode('1920x1200', '75Hz',  '16:10'),
            71: DisplayMode('1920x1200', '85Hz',  '16:10'),
            72: DisplayMode('1920x1200', '120Hz', '16:10',  'reduced blanking'),
            73: DisplayMode('1920x1440', '60Hz',  '4:3'),
            74: DisplayMode('1920x1440', '75Hz',  '4:3'),
            75: DisplayMode('1920x1440', '120Hz', '4:3',    'reduced blanking'),
            76: DisplayMode('2560x1600', '60Hz',  '16:10',  'reduced blanking'),
            77: DisplayMode('2560x1600', '60Hz',  '16:10'),
            78: DisplayMode('2560x1600', '75Hz',  '16:10'),
            79: DisplayMode('2560x1600', '85Hz',  '16:10'),
            80: DisplayMode('2560x1600', '120Hz', '16:10',  'reduced blanking'),
            81: DisplayMode('1366x768',  '60Hz',  '16:9'),
            82: DisplayMode('1920x1080', '60Hz',  '16:9',   '1080p'),
            83: DisplayMode('1600x900',  '60Hz',  '16:9',   'reduced blanking'),
            84: DisplayMode('2048x1152', '60Hz',  '16:9',   'reduced blanking'),
            85: DisplayMode('1280x720',  '60Hz',  '16:9',   '720p'),
            86: DisplayMode('1366x768',  '60Hz',  '16:9',   'reduced blanking'),
            87: DisplayMode(notes='user timings'),
        }
        doc = dedent(doc).format_map(
            TransMap(
                valid_cea=FormatDict(
                    self._valid_cea, key_title=_('Mode'),
                    value_title=(_('Resolution'), _('Refresh'),
                                 _('Ratio'), _('Notes'))),
                valid_dmt=FormatDict(
                    self._valid_dmt, key_title=_('Mode'),
                    value_title=(_('Resolution'), _('Refresh'),
                                 _('Ratio'), _('Notes'))),
            ))
        super().__init__(name, command=command, commands=commands,
                         default=default, doc=doc, index=index)

    @property
    def hint(self):
        return {
            0: _('auto from EDID'),
            1: str(self._valid_cea.get(self.value, '?')),
            2: str(self._valid_dmt.get(self.value, '?')),
        }.get(self._query(self._relative('.group')).value, '?')

    def validate(self):
        group = self._query(self._relative('.group'))
        valid = {
            0: {0},
            1: self._valid_cea.keys(),
            2: self._valid_dmt.keys(),
        }[group.value]
        if self.value not in valid:
            raise ValueError(_(
                '{self.name} must be {valid} when {group.name} is '
                '{group.value}'
            ).format(self=self, valid=int_ranges(valid), group=group))


class CommandDisplayTimings(Command):
    """
    Represents settings that manually specify the timings of a video output,
    e.g. ``hdmi_timings`` or ``dpi_timings``.
    """
    def __init__(self, name, *, command=None, commands=None, default=None,
                 doc='', index=0):
        super().__init__(name, command=command, commands=commands,
                         default=[] if default is None else default,
                         doc=doc, index=index)

    def extract(self, config):
        for item, value in super().extract(config):
            try:
                value = value.strip()
                if value:
                    value = [to_int(elem) for elem in value.split()]
                    yield item, value
                else:
                    yield item, []
            except ValueError:
                warnings.warn(ParseWarning(
                    '{item.filename} line {item.linenum}: invalid integer in '
                    '{value!r}'.format(item=item, value=value)))
                yield item, []

    def update(self, value):
        if isinstance(value, UserStr):
            value = value.strip()
            if value:
                return [int(elem) for elem in value.split(',')]
            return None
        else:
            return value

    def validate(self):
        if self.modified and len(self.value) not in (0, 17):
            raise ValueError(
                _('{self.name} takes 17 comma-separated integers')
                .format(self=self))

    def output(self):
        if self.modified:
            joined_value = ' '.join(str(i) for i in self.value)
            with self._override(joined_value):
                yield from super().output()


class CommandDisplayRotate(CommandInt):
    """
    Represents settings that control the rotation of a video output. This is
    expected to work in concert with a :class:`CommandDisplayFlip` setting
    (both rotate and flip are usually conflated into a single command, e.g.
    ``display_hdmi_rotate`` or ``display_lcd_rotate``).

    Also handles the deprecated ``display_rotate`` command, and the extra
    ``lcd_rotate`` command.
    """
    def __init__(self, name, *, command=None, commands=None, default=0, doc='',
                 index=0):
        super().__init__(name, command=command, commands=commands,
                         default=default, doc=doc, index=index)

    def extract(self, config):
        for item, value in super().extract(config):
            yield item, ((value & 0x3) * 90)

    def validate(self):
        if self.value not in (0, 90, 180, 270):
            raise ValueError(_(
                '{self.name} must be 0, 90, 180, or 270'
            ).format(self=self))

    def output(self):
        flip = self._query(self._relative('.flip'))
        if self.modified or flip.modified:
            value = (self.value // 90) | (flip.value << 16)
            if 'lcd_rotate' in self.commands:
                # For the DSI LCD display, prefer lcd_rotate as it uses the
                # display's electronics to handle rotation rather than the GPU.
                # However, if a flip is required, just use the GPU (because we
                # have to anyway).
                if value > 0b11:
                    template = '{self.commands[0]}={value:#x}'
                else:
                    template = 'lcd_rotate={value}'
            else:
                if self.index:
                    template = '{self.commands[0]}:{self.index}={value:#x}'
                else:
                    template = '{self.commands[0]}={value:#x}'
            yield template.format(self=self, value=value)


class CommandDisplayFlip(CommandInt):
    """
    Represents settings that control reflection (flipping) of a video output.
    See :class:`CommandDisplayRotate` for further information.
    """
    def __init__(self, name, *, command=None, commands=None, default=0, doc='',
                 index=0):
        super().__init__(name, command=command, commands=commands,
                         default=default, index=index, doc=doc, valid={
                             0: 'none',
                             1: 'horizontal',
                             2: 'vertical',
                             3: 'both', })

    def extract(self, config):
        for item, value in super().extract(config):
            yield item, ((value >> 16) & 0x3)

    def output(self):
        # See CommandDisplayRotate.output above
        if self.modified:
            raise DelegatedOutput(self._relative('.rotate'))
        else:
            return ()


class CommandDPIOutput(CommandMaskMaster):
    """
    Represents the format portion of ``dpi_output_format``.
    """
    def output(self):
        if self._query(self._relative('.enabled')).value:
            # For the DPI LCD display, always output dpi_output_format when
            # enable_dpi_lcd is set (and conversely, don't output it when not
            # set)
            yield from super().output()


class CommandDPIDummy(CommandMaskDummy):
    """
    Represents the non-format portions of ``dpi_output_format``.
    """
    def output(self):
        if self.modified:
            raise DelegatedOutput('video.dpi.format')
        else:
            return ()


class CommandHDMIBoost(CommandInt):
    """
    Represents the ``config_hdmi_boost`` setting with its custom range of
    valid values.
    """
    def validate(self):
        if not 0 <= self.value <= 11:
            raise ValueError(_(
                '{self.name} must be between 0 and 11 (default 5)'
            ).format(self=self))


class CommandEDIDIgnore(CommandIntHex):
    """
    Represents the ``hdmi_ignore_edid`` "boolean" setting with its bizarre
    "true" value.
    """
    # See hdmi_ignore_edid in
    # https://www.raspberrypi.org/documentation/configuration/config-txt/video.md
    def __init__(self, name, *, command=None, commands=None, default=False,
                 doc=''):
        super().__init__(name, command=command, commands=commands,
                         default=default, doc=doc)

    @property
    def hint(self):
        pass

    def extract(self, config):
        for item, value in super().extract(config):
            yield item, value == 0xa5000080

    def update(self, value):
        return to_bool(value)

    def output(self):
        if self.modified:
            new_value = 0xa5000080 if self.value else 0
            with self._override(new_value):
                yield from super().output()


class CommandBootDelay2(Command):
    """
    Represents the combination of ``boot_delay`` and ``boot_delay_ms``.
    """
    def extract(self, config):
        boot_delay = boot_delay_ms = 0
        for item in config:
            if isinstance(item, BootCommand):
                if item.command == 'boot_delay':
                    try:
                        boot_delay = to_int(item.params)
                    except ValueError:
                        warnings.warn(ParseWarning(
                            '{item.filename} line {item.linenum}: invalid '
                            'integer {item.params!r}'.format(item=item)))
                        boot_delay = 0
                    yield item, boot_delay + (boot_delay_ms / 1000)
                elif item.command == 'boot_delay_ms':
                    try:
                        boot_delay_ms = to_int(item.params)
                    except ValueError:
                        warnings.warn(ParseWarning(
                            '{item.filename} line {item.linenum}: invalid '
                            'integer {item.params!r}'.format(item=item)))
                        boot_delay_ms = 0
                    yield item, boot_delay + (boot_delay_ms / 1000)

    def output(self):
        if self.modified:
            whole, frac = divmod(self.value, 1)
            whole = int(whole)
            frac = int(frac * 1000)
            if whole:
                yield 'boot_delay={value}'.format(value=whole)
            if frac:
                yield 'boot_delay_ms={value}'.format(value=frac)

    def update(self, value):
        return to_float(value)

    def validate(self):
        if self.value < 0.0:
            raise ValueError(_(
                '{self.name} cannot be negative'
            ).format(self=self))


class CommandKernelAddress(CommandIntHex):
    """
    Represents the ``kernel_address`` setting, and implements its
    context-sensitive default values. Also handles the deprecated
    ``kernel_old`` configuration parameter.
    """
    @property
    def default(self):
        if self._query(self._relative('.64bit')).value:
            return 0x80000
        else:
            return 0x8000

    def extract(self, config):
        for item in config:
            if isinstance(item, BootCommand):
                try:
                    if item.command == 'kernel_address':
                        yield item, to_int(item.params)
                    elif item.command == 'kernel_old':
                        # TODO What does kernel_old=0 mean? Similar to start_x=0?
                        if to_int(item.params):
                            yield item, 0
                except ValueError:
                    warnings.warn(ParseWarning(
                        '{item.filename} line {item.linenum}: invalid integer '
                        '{item.params!r}'.format(item=item)))
                    yield item, None


class CommandKernel64(CommandBool):
    """
    Handles the ``arm_64bit`` configuration setting, and the deprecated
    ``arm_control`` setting it replaced.
    """
    def extract(self, config):
        for item in config:
            if isinstance(item, BootCommand):
                try:
                    if item.command == 'arm_64bit':
                        yield item, bool(to_int(item.params))
                    elif item.command == 'arm_control':
                        yield item, bool(to_int(item.params) & 0x200)
                except ValueError:
                    warnings.warn(ParseWarning(
                        '{item.filename} line {item.linenum}: invalid integer '
                        '{item.params!r}'.format(item=item)))
                    yield item, None


class CommandKernelFilename(CommandFilename):
    """
    Handles the ``kernel`` setting and its platform-dependent defaults.
    """
    @property
    def default(self):
        if self._query(self._relative('.64bit')).value:
            return 'kernel8.img'
        else:
            board_type = get_board_type()
            if board_type == 'pi4':
                return 'kernel7l.img'
            elif board_type in {'pi2', 'pi3', 'pi3+'}:
                return 'kernel7.img'
            else:
                return 'kernel.img'


class CommandKernelCmdline(CommandIncludedFile):
    """
    Handles the ``cmdline`` setting.
    """
    # TODO modification/tracking of external file


Firmware = namedtuple('Firmware', ('default', 'camera', 'debug', 'cutdown'))
FW_START = {
    # pi4:           default       camera         debug(+camera)  lite
    False: Firmware('start.elf',  'start_x.elf', 'start_db.elf', 'start_cd.elf'),
    True:  Firmware('start4.elf', 'start4x.elf', 'start4db.elf', 'start4cd.elf'),
}
FW_FIXUP = {
    key: Firmware(*(
        filename.replace('start', 'fixup').replace('.elf', '.dat')
        for filename in filenames
    ))
    for key, filenames in FW_START.items()
}


# Some notes on start_x, start_debug, start_file, and fixup_file for the
# setting classes below.
#
# The interaction between these settings is both simple and horribly
# complicated (at least from the perspective of this application). Each of
# these is effectively a separate setting within the firmware, and is evaluated
# in order, so only the final value of each setting matters. However, there are
# rules of precedence regarding those final values:
#
# 1. non-blank start_file and fixup_file values trump everything; if these are
#    set they are acted upon.
# 2. if start_file and fixup_file aren't set then gpu_mem=16 wins next; if this
#    is set then start_file is effectively "start_cd.elf" ("start4cd.elf" on
#    the pi4)
# 3. Otherwise, start_debug=1 wins; if this is set then start_file is
#    effectively "start_db.elf" ("start4db.elf" on the pi4), and fixup_file is
#    "fixup_db.dat" or "fixup4db.dat"
# 4. Otherwise, start_x=1 wins; if this is set then start_file is "start_x.elf"
#    ("start4x.elf" on the pi4), and fixup_file is "fixup_x.dat" or
#    "fixup4x.dat".
# 5. If no values are specified for these, then start_file is effectively
#    "start.elf" or ("start4.elf" on the pi4) and fixup_file is "fixup.dat" (or
#    "fixup4.dat").
# 6. The debug firmware incorporates the camera firmware.
#
# Some consequences of the above rules; consider the following (silly, but
# valid) configuration:
#
# start_debug=1
# start_x=1
# start_x=0
#
# This results in the debug firmware being loaded because at the end of parsing
# the configuration, start_file hasn't been explicitly set, gpu_mem defaults to
# 64, and start_debug is 1 (so start_x is irrelevant; whether it's 0 or 1 the
# debug firmware would be loaded). Likewise, consider:
#
# start_x=1
# start_debug=1
# start_debug=0
#
# This results in the camera firmware being loaded as start_debug is 0 by the
# end of parsing and start_x is still 1. In turn, this implies that the
# "start_x=0" and "start_debug=0" states are fairly meaningless statements. If
# a configuration explicitly sets them to zero (ultimately) we should simply
# treat them as "unset".


class CommandFirmwareCamera(CommandBool):
    """
    Handles the ``start_x`` and ``start_debug`` settings.
    """
    @property
    def default(self):
        pi4 = get_board_type() == 'pi4'
        return (self._query('gpu.mem').value >= 64) and (
            self._query('boot.firmware.filename').value,
            self._query('boot.firmware.fixup').value
        ) in {
            (FW_START[pi4].camera, FW_FIXUP[pi4].camera),
            # The debug firmware includes the camera firmware, so start_debug
            # also implicitly activates the camera
            (FW_START[pi4].debug, FW_FIXUP[pi4].debug)
        }

    def extract(self, config):
        for item, value in super().extract(config):
            # NOTE: start_x is only valid in config.txt
            if item.filename == 'config.txt' and item.command == 'start_x':
                yield item, True if value else None

    def output(self):
        if self.modified and self.value:
            yield 'start_x=1'

    def validate(self):
        if self.value and self._query('gpu.mem').value < 64:
            raise ValueError(_(
                'gpu.mem must be at least 64 when camera.enabled is on'))


class CommandFirmwareDebug(CommandBool):
    """
    Handles the ``start_debug`` setting.
    """
    @property
    def default(self):
        pi4 = get_board_type() == 'pi4'
        return (self._query('gpu.mem').value > 16) and (
            self._query('boot.firmware.filename').value,
            self._query('boot.firmware.fixup').value
        ) == (FW_START[pi4].debug, FW_FIXUP[pi4].debug)

    def extract(self, config):
        for item, value in super().extract(config):
            # NOTE: start_debug is only valid in config.txt
            if item.filename == 'config.txt' and item.command == 'start_debug':
                yield item, True if value else None

    def output(self):
        if self.modified and self.value:
            yield 'start_debug=1'


class CommandFirmwareFilename(CommandFilename):
    """
    Handles the ``start_file`` setting.
    """
    @property
    def default(self):
        pi4 = get_board_type() == 'pi4'
        debug = self._query('boot.debug.enabled')
        camera = self._query('camera.enabled')
        # The "modified" tests below appear extraneous but aren't; they guard
        # against a circular reference in the case where everything is default.
        if self._query('gpu.mem').value <= 16:
            return FW_START[pi4].cutdown
        elif debug.modified and debug.value:
            return FW_START[pi4].debug
        elif camera.modified and camera.value:
            return FW_START[pi4].camera
        else:
            return FW_START[pi4].default

    def extract(self, config):
        for item, value in super().extract(config):
            # NOTE: start_filename is only valid in config.txt
            if item.filename == 'config.txt':
                yield item, value

    # TODO validate() to check for pi4/non-pi4 compatible firmware


class CommandFirmwareFixup(CommandFilename):
    """
    Handles the ``fixup_file`` setting.
    """
    @property
    def default(self):
        pi4 = get_board_type() == 'pi4'
        debug = self._query('boot.debug.enabled')
        camera = self._query('camera.enabled')
        # See notes above
        if self._query('gpu.mem').value <= 16:
            return FW_FIXUP[pi4].cutdown
        elif debug.modified and debug.value:
            return FW_FIXUP[pi4].debug
        elif camera.modified and camera.value:
            return FW_FIXUP[pi4].camera
        else:
            return FW_FIXUP[pi4].default

    def extract(self, config):
        for item, value in super().extract(config):
            # NOTE: fixup_file is only valid in config.txt
            if item.filename == 'config.txt':
                yield item, value

    # TODO validate() to check for pi4/non-pi4 compatible firmware


class CommandDeviceTree(CommandFilename):
    """
    Handles the ``device_tree`` command.
    """


class CommandDeviceTreeAddress(CommandIntHex):
    """
    Handles the ``device_tree_address`` command.
    """
    @property
    def hint(self):
        if self.value == 0:
            return _('auto')
        else:
            return super().hint


class CommandRamFSAddress(CommandIntHex):
    """
    Handles the ``ramfsaddr`` and ``initramfs`` commands.
    """
    @property
    def hint(self):
        if self.value == 0:
            return _('auto')  # followkernel
        else:
            # FIXME What?
            return super().hint

    def extract(self, config):
        for item in config:
            if isinstance(item, BootCommand):
                try:
                    if item.command == 'ramfsaddr':
                        yield item, to_int(item.params)
                    elif item.command == 'initramfs':
                        filename, address = item.params
                        if address == 'followkernel':
                            yield item, None
                        else:
                            yield item, to_int(address)
                except ValueError:
                    warnings.warn(ParseWarning(
                        '{item.filename} line {item.linenum}: invalid integer '
                        '{item.params!r}'.format(item=item)))
                    yield item, None


class CommandRamFSFilename(Command):
    """
    Handles the ``ramfsfile`` and ``initramfs`` commands which can both
    accept multiple files (to be concatenated).
    """
    def __init__(self, name, *, command=None, commands=None, default=None,
                 doc='', index=0):
        if default is None:
            default = []
        super().__init__(name, command=command, commands=commands,
                         default=default, doc=doc, index=index)

    @property
    def filename(self):
        """
        The list of full filenames represented by the value, after
        concatenation with the value of "boot.prefix".
        """
        prefix = self._query('boot.prefix').value
        return [prefix + item for item in self.value]

    @property
    def hint(self):
        if self.value and self._query('boot.prefix').modified:
            return _('{!r} with boot.prefix').format(self.filename)
        else:
            return None

    def extract(self, config):
        for item in config:
            if isinstance(item, BootCommand):
                if item.command == 'ramfsfile':
                    yield item, to_list(item.params, sep=',')
                elif item.command == 'initramfs':
                    filename, address = item.params
                    yield item, to_list(filename, sep=',')

    def update(self, value):
        return to_list(value)

    def validate(self):
        if self.modified and len(self.name) + sum(
                len(item) + 1 for item in self.value) > 80:
            raise ValueError(_('Excessively long list of initramfs files'))

    def output(self):
        if self.modified:
            new_value = ','.join(self.value)
            with self._override(new_value):
                yield from super().output()


class CommandSerialEnabled(CommandBool):
    """
    Handles the ``enable_uart`` setting and its platform-dependent defaults.
    """
    @property
    def default(self):
        if get_board_type() in {'pi0w', 'pi3', 'pi3+', 'pi4'}:
            return not self._query('bluetooth.enabled').value
        else:
            return True


class OverlaySerialUART(Setting):
    """
    Handles deriving the default serial UART based on the enabled state of
    Bluetooth (if present) and/or the presence of the miniuart-bt overlay.
    """
    @property
    def default(self):
        if get_board_type() in {'pi0w', 'pi3', 'pi3+', 'pi4'}:
            if self._query('bluetooth.enabled').value:
                return 1
            else:
                return 0
        else:
            return 0

    @property
    def key(self):
        return ('overlays', 'miniuart-bt')

    @property
    def hint(self):
        if self.value == 0:
            return '/dev/ttyAMA0; PL011'
        else:
            return '/dev/ttyS0; mini-UART'

    def extract(self, config):
        for item in config:
            if isinstance(item, BootOverlay):
                if item.overlay in ('miniuart-bt', 'pi3-miniuart-bt'):
                    yield item, 0

    def update(self, value):
        return to_int(value)

    def validate(self):
        if self.value == 1 and not self._query('bluetooth.enabled').value:
            raise ValueError(_(
                'serial.uart must be 0 when bluetooth.enabled is off'))

    def output(self):
        if self.modified:
            raise DelegatedOutput('bluetooth.enabled')
        else:
            return ()


class OverlayBluetoothEnabled(Setting):
    """
    Represents the ``miniuart-bt`` and ``disable-bt`` overlays (via the
    ``bluetooth.enabled`` pseudo-command).
    """
    @property
    def default(self):
        return get_board_type() in {'pi0w', 'pi3', 'pi3+', 'pi4'}

    @property
    def key(self):
        return ('overlays', 'disable-bt')

    def extract(self, config):
        for item in config:
            if isinstance(item, BootOverlay):
                if item.overlay in ('disable-bt', 'pi3-disable-bt'):
                    yield item, False
                elif item.overlay in ('miniuart-bt', 'pi3-miniuart-bt'):
                    yield item, True
                # XXX What happens if both overlays are specified?

    def update(self, value):
        return to_bool(value)

    def output(self):
        if self.modified or self._query('serial.uart').modified:
            # TODO what about pi3- prefix on systems with deprecated overlays?
            if not self.value:
                yield 'dtoverlay=disable-bt'
            elif self._query('serial.uart').value == 0:
                yield 'dtoverlay=miniuart-bt'


class OverlayKMS(Setting):
    """
    Represents the framebuffer driver as 'legacy' (when no overlays are used),
    'fkms' (when the vc4-fkms-v3d overlay is loaded), or 'kms' (when the
    vc4-kms-v3d overlay is loaded).
    """
    @property
    def default(self):
        return 'legacy'

    @property
    def key(self):
        return ('overlays', 'vc4-fkms-v3d')

    def extract(self, config):
        for item in config:
            if isinstance(item, BootOverlay):
                try:
                    yield item, {
                        'vc4-fkms-v3d': 'fkms',
                        'vc4-kms-v3d':  'kms',
                    }[item.overlay]
                except KeyError:
                    pass

    def update(self, value):
        return to_str(value)

    def validate(self):
        if self.value not in {'legacy', 'kms', 'fkms'}:
            raise ValueError(
                _("{self.name} must be one of 'legacy', 'kms', "
                  "'fkms'").format(self=self))

    def output(self):
        try:
            yield 'dtoverlay=' + {
                'fkms': 'vc4-fkms-v3d',
                'kms':  'vc4-kms-v3d',
            }[self.value]
        except KeyError:
            pass

    @property
    def hint(self):
        return {
            'legacy': 'no KMS',
            'fkms':   'Fake KMS',
            'kms':    'Full KMS',
        }[self.value]


class OverlayDWC2(Setting):
    """
    Represents the dwc-otg and dwc2 overlays. The former is default on all
    pi models except the 0 where the latter is default.
    """
    @property
    def default(self):
        return get_board_type() in {'pi0', 'pi0w'}

    @property
    def key(self):
        return ('overlays', 'dwc2' if self.value else 'dwc-otg')

    def extract(self, config):
        for item in config:
            if isinstance(item, BootOverlay):
                if item.overlay == 'dwc-otg':
                    yield item, False
                elif item.overlay == 'dwc2':
                    yield item, True
                # XXX What happens if both overlays are specified?

    def update(self, value):
        return to_bool(value)

    def output(self):
        if self.modified:
            if self.value:
                yield 'dtoverlay=dwc2'
            else:
                yield 'dtoverlay=dwc-otg'


class CommandCPUL2Cache(CommandBoolInv):
    """
    Handles the ``disable_l2cache`` command.
    """
    @property
    def default(self):
        return {
            'pi0':  True,
            'pi0w': True,
            'pi1':  True,
            'pi2':  False,
            'pi3':  False,
            'pi3+': False,
            'pi4':  False,
        }.get(get_board_type())


class CommandCPUFreqMax(CommandInt):
    """
    Handles the ``arm_freq`` command.
    """
    @property
    def default(self):
        return {
            'pi0':  1000,
            'pi0w': 1000,
            'pi1':  700,
            'pi2':  900,
            'pi3':  1200,
            'pi3+': 1400,
            'pi4':  1500,
        }.get(get_board_type(), 0)

    def validate(self):
        other = self._query(self._relative('.min'))
        if self.value < other.value:
            raise ValueError(_(
                '{self.name} cannot be less then {other.name}').format(
                    self=self, other=other))

    @property
    def hint(self):
        return 'MHz'


class CommandCPUFreqMin(CommandInt):
    """
    Handles the ``arm_freq_min`` command.
    """
    @property
    def default(self):
        if self._query('cpu.turbo.force').value:
            return self._query(self._relative('.max')).value
        else:
            return {
                'pi0':  700,
                'pi0w': 700,
                'pi1':  700,
                'pi2':  600,
                'pi3':  600,
                'pi3+': 600,
                'pi4':  600,
            }.get(get_board_type(), 0)

    @property
    def hint(self):
        return 'MHz'


class CommandCoreFreqMax(CommandInt):
    """
    Handles the ``core_freq`` command.
    """
    @property
    def default(self):
        if (
                self._query('serial.enabled').value and
                self._query('serial.uart').value == 1 and
                not self._query('cpu.turbo.force').value):
            return self._query(self._relative('.min')).value
        else:
            board_type = get_board_type()
            if board_type == 'pi4':
                return (
                    360 if self._query('video.tv.enabled').value else
                    550 if self._query('video.hdmi.4kp60').value else
                    500)
            else:
                return {
                    'pi0':  400,
                    'pi0w': 400,
                    'pi1':  250,
                    'pi2':  250,
                    'pi3':  400,
                    'pi3+': 400,
                }.get(board_type, 0)

    def output(self):
        blocks = [self] + [
            self._query(self._relative(
                '...{block}.frequency.max'.format(block=block)
            ))
            for block in ('h264', 'isp', 'v3d')
        ]
        if any(block.modified for block in blocks):
            if all(self.value == block.value for block in blocks):
                yield 'gpu_freq={value}'.format(value=self.value)
            else:
                yield from super().output()

    def validate(self):
        other = self._query(self._relative('.min'))
        if self.value < other.value:
            raise ValueError(_(
                '{self.name} cannot be less then {other.name}').format(
                    self=self, other=other))

    @property
    def hint(self):
        return 'MHz'


class CommandCoreFreqMin(CommandInt):
    """
    Handles the ``core_freq_min`` command.
    """
    @property
    def default(self):
        if self._query('cpu.turbo.force').value:
            return self._query(self._relative('.max')).value
        else:
            board_type = get_board_type()
            if board_type == 'pi4' and self._query('video.hdmi.4kp60').value:
                return 275
            elif board_type:
                return 250
            else:
                return 0

    def output(self):
        blocks = [self] + [
            self._query(self._relative(
                '...{block}.frequency.min'.format(block=block)
            ))
            for block in ('h264', 'isp', 'v3d')
        ]
        if any(block.modified for block in blocks):
            if all(self.value == block.value for block in blocks):
                yield 'gpu_freq_min={value}'.format(value=self.value)
            else:
                yield from super().output()

    @property
    def hint(self):
        return 'MHz'


class CommandGPUFreqMax(CommandInt):
    """
    Handles the ``h264_freq``, ``isp_freq``, and ``v3d_freq`` commands.
    """
    @property
    def default(self):
        board_type = get_board_type()
        if board_type == 'pi4':
            return (
                360 if self._query('video.tv.enabled').value else
                550 if self._query('video.hdmi.4kp60').value else
                500)
        else:
            return {
                'pi0':  300,
                'pi0w': 300,
                'pi1':  250,
                'pi2':  250,
                'pi3':  400,
                'pi3+': 400,
            }.get(board_type, 0)

    def output(self):
        blocks = [
            self._query(self._relative(
                '...{block}.frequency.max'.format(block=block)
            ))
            for block in ('core', 'h264', 'isp', 'v3d')
        ]
        if any(block.modified for block in blocks):
            if all(self.value == block.value for block in blocks):
                raise DelegatedOutput(self._relative('...core.frequency.max'))
            else:
                yield from super().output()

    def validate(self):
        other = self._query(self._relative('.min'))
        if self.value < other.value:
            raise ValueError(_(
                '{self.name} cannot be less then {other.name}').format(
                    self=self, other=other))

    @property
    def hint(self):
        return 'MHz'


class CommandGPUFreqMin(CommandInt):
    """
    Handles the ``h264_freq_min``, ``isp_freq_min``, and ``v3d_freq_min``
    commands.
    """
    @property
    def default(self):
        if self._query('cpu.turbo.force').value:
            return self._query(self._relative('.max')).value
        else:
            board_type = get_board_type()
            return 500 if board_type == 'pi4' else 250 if board_type else 0

    def output(self):
        blocks = [
            self._query(self._relative(
                '...{block}.frequency.min'.format(block=block)
            ))
            for block in ('core', 'h264', 'isp', 'v3d')
        ]
        if any(block.modified for block in blocks):
            if all(self.value == block.value for block in blocks):
                raise DelegatedOutput(self._relative('...core.frequency.min'))
            else:
                yield from super().output()

    @property
    def hint(self):
        return 'MHz'


class CommandTotalMem(CommandInt):
    """
    Handles the ``total_mem`` command.
    """
    @property
    def default(self):
        return get_board_mem() or 1024

    def extract(self, config):
        for item, value in super().extract(config):
            if item.filename == 'config.txt':
                # NOTE: total_mem is only valid in config.txt
                yield item, value

    def validate(self):
        if self.value < 128:
            raise ValueError(_(
                '{self.name} must be at least 128Mb').format(self=self))

    @property
    def hint(self):
        return 'Mb'


class CommandGPUMem(CommandInt):
    """
    Handles the ``gpu_mem`` command.
    """
    @property
    def default(self):
        return 64 if get_board_mem() < 1024 else 76

    def extract(self, config):
        values = {name: None for name in self.commands}
        override = 'gpu_mem_{mem}'.format(mem=min(1024, get_board_mem()))
        if override not in values:
            override = None
        for item in config:
            # NOTE: gpu_mem_XXX is only valid in config.txt
            if isinstance(item, BootCommand) and item.filename == 'config.txt':
                # The following convoluted logic deals with the fact that
                # gpu_mem_1024 et al. override gpu_mem regardless of ordering
                if item.command in values:
                    try:
                        values[item.command] = to_int(item.params)
                    except ValueError:
                        warnings.warn(ParseWarning(
                            '{item.filename} line {item.linenum}: invalid '
                            'integer {item.params!r}'.format(item=item)))
                        values[item.command] = None
                if item.command in ('gpu_mem', override):
                    yield item, (
                        values['gpu_mem']
                        if values.get(override) is None else
                        values.get(override)
                    )

    def validate(self):
        if self.value < 16:
            raise ValueError(_(
                '{self.name} must be at least 16Mb').format(self=self))
        mem = get_board_mem()
        max_gpu_mem = {
            256: 128,
            512: 384,
        }.get(mem, 512)
        if self.value > max_gpu_mem:
            raise ValueError(_(
                '{self.name} must be less than {max_gpu_mem}Mb').format(
                    self=self, max_gpu_mem=max_gpu_mem))

    @property
    def hint(self):
        return 'Mb'


class CommandTVOut(CommandBool):
    """
    Handles the ``enable_tvout`` Pi4 command.
    """
    @property
    def default(self):
        return get_board_type() != 'pi4'

    def validate(self):
        other = self._query('video.hdmi.4kp60')
        if self.value and other.value:
            raise ValueError(_(
                '{self.name} and {other.name} cannot both be on').format(
                    self=self, other=other))


class CommandVideoLicense(Command):
    """
    Handles the ``decode_MPG2`` and ``decode_WVC1`` commands.
    """
    def __init__(self, name, *, command=None, commands=None, doc=''):
        super().__init__(name, command=command, commands=commands,
                         default=[], doc=doc, index=0)

    def extract(self, config):
        for item, value in super().extract(config):
            yield item, to_list(value, sep=',')

    def update(self, value):
        return to_list(value)

    def validate(self):
        if self.modified and len(self.value) > 8:
            raise ValueError(_('Maximum of 8 licenses may be specified'))

    def output(self):
        if self.modified:
            new_value = ','.join(self.value)
            with self._override(new_value):
                yield from super().output()


# Notes on parsing the values of the "gpio" command (from experimentation
# with various pathological settings):
#
# 1. Any invalid values/chars on the right of the equals sign invalidates
#    the entire setting, e.g. "18=xx,op,dh" is entirely ignored
# 2. Invalid values/chars to the left of the equals sign invalidate all
#    GPIO numbers after that point, but permit setting all GPIOs mentioned
#    until that point, e.g. "18,xx,23=op,dh" still sets GPIO18 to out/high
# 3. Invalid chars include spaces, e.g. "18,23=op, dh" is entirely
#    ignored (by rule 1)
# 4. Invalid chars in a range invalidate the entire range, e.g.
#    "18- 23=op,dh" sets nothing
# 5. Hex-specifications are not permitted, e.g. "0x17=op,dh" is ignored
# 6. Multiple valid settings on the right are permitted; only the last
#    apply, e.g. "18=ip,op,ip,op,dl,dh" sets GPIO18 to out/high

GPIO_MODES = {
    'ip': 'in',
    'op': 'out',
    'a0': 'alt0',
    'a1': 'alt1',
    'a2': 'alt2',
    'a3': 'alt3',
    'a4': 'alt4',
    'a5': 'alt5',
}
GPIO_IN_STATES = {
    'pd': 'down',
    'pu': 'up',
    'np': 'none',
    'pn': 'none',
}
GPIO_OUT_STATES = {
    'dl': 'low',
    'dh': 'high',
}
GPIO_MODES_MAP = {v: k for k, v in GPIO_MODES.items()}
GPIO_STATES_MAP = {
    v: k
    for k, v in chain(
        GPIO_IN_STATES.items(),
        GPIO_OUT_STATES.items(),
    )
}
GPIO_STATES_MAP['none'] = 'np'  # force this for consistency
GPIO_COMMANDS = (
    GPIO_MODES.keys() |
    GPIO_IN_STATES.keys() |
    GPIO_OUT_STATES.keys()
)

def parse_gpio(s):
    if '=' not in s:
        raise ValueError('missing = in gpio specification')
    left, right = s.split('=', 1)
    commands = right.split(',')
    # Note we do not strip any values here (remember spaces invalidate)
    if set(commands) - GPIO_COMMANDS:
        raise ValueError('invalid command in gpio specification')
    mode = 'ip'
    state = 'np'
    for command in commands:
        if command in GPIO_MODES:
            mode = command
        else:
            state = command
    if mode == 'op' and state in GPIO_IN_STATES:
        state = 'dl'
    elif mode == 'ip' and state in GPIO_OUT_STATES:
        state = 'np'
    gpios = set()
    for maybe_range in left.split(','):
        if '-' in maybe_range:
            gpio_start, gpio_end = maybe_range.split('-', 1)
            # int() implicitly strips the input; we need to avoid that and note
            # an invalid point
            if gpio_start != gpio_start.strip() or gpio_end != gpio_end.strip():
                break
            try:
                gpio_start = int(gpio_start)
                gpio_end = int(gpio_end)
            except ValueError:
                break
            else:
                if gpio_end < 0:
                    break
                for gpio in range(gpio_start, gpio_end + 1):
                    gpios.add(gpio)
        else:
            gpio = maybe_range
            if gpio != gpio.lstrip():
                break
            try:
                gpio = int(gpio)
            except ValueError:
                break
            else:
                gpios.add(gpio)
    return (
        gpios, GPIO_MODES[mode],
        GPIO_IN_STATES[state] if mode == 'ip' else
        GPIO_OUT_STATES[state] if mode == 'op' else
        'none'
    )


class CommandGPIOMode(CommandStr):
    """
    Handles the mode selection part of the ``gpio`` command.
    """
    def __init__(self, name, *, command=None, commands=None, doc='', index=0):
        super().__init__(name, command=command, commands=commands,
                         default='in', doc=doc, index=index, valid={
                             'in':   'Input',
                             'out':  'Output',
                             'alt0': 'Alt. Function 0',
                             'alt1': 'Alt. Function 1',
                             'alt2': 'Alt. Function 2',
                             'alt3': 'Alt. Function 3',
                             'alt4': 'Alt. Function 4',
                             'alt5': 'Alt. Function 5',
                         })

    def extract(self, config):
        for item in config:
            if isinstance(item, BootCommand) and item.command == 'gpio':
                try:
                    gpios, mode, state = parse_gpio(item.params)
                except ValueError:
                    warnings.warn(ParseWarning(
                        '{item.filename} line {item.linenum}: invalid gpio '
                        'spec {item.params!r}'.format(item=item)))
                    # TODO We've no idea if the line *would've* affected this
                    # gpio here; probably ought to fix that
                else:
                    if self.index in gpios:
                        yield item, mode

    def output(self):
        # Only gpio0 gets to write output, and does so on behalf of all GPIO
        # settings
        if self.index > 0:
            if self.modified:
                raise DelegatedOutput('gpio0.mode')
        else:
            gpios = {
                gpio: (
                    self._query('gpio{}.mode'.format(gpio)),
                    self._query('gpio{}.state'.format(gpio)),
                )
                for gpio in range(28)
            }
            if any(
                    mode.modified or state.modified
                    for mode, state in gpios.values()
            ):
                states = {
                    gpio: (mode.value, state.value)
                    for gpio, (mode, state) in gpios.items()
                    if mode.modified or state.modified
                }
                states = sorted(states.items(), key=itemgetter(1))
                states = {
                    state: set(gpio for gpio, _state in gpios)
                    for state, gpios in groupby(states, key=itemgetter(1))
                }
                for (mode, state), gpios in states.items():
                    yield 'gpio={gpios}={mode},{state}'.format(
                        gpios=int_ranges(gpios, list_sep=','),
                        mode=GPIO_MODES_MAP[mode],
                        state=GPIO_STATES_MAP[state])


class CommandGPIOState(CommandStr):
    """
    Handles the state selection part of the ``gpio`` command.
    """
    def __init__(self, name, *, command=None, commands=None, doc='', index=0):
        super().__init__(name, command=command, commands=commands,
                         default='none', doc=doc, index=index, valid={
                             'up':   'Pulled up',
                             'down': 'Pulled down',
                             'none': 'No pull/floating',
                             'low':  'Driven low',
                             'high': 'Driven high',
                         })

    def extract(self, config):
        for item in config:
            if isinstance(item, BootCommand) and item.command == 'gpio':
                try:
                    gpios, mode, state = parse_gpio(item.params)
                except ValueError:
                    warnings.warn(ParseWarning(
                        '{item.filename} line {item.linenum}: invalid gpio '
                        'spec {item.params!r}'.format(item=item)))
                    # TODO We've no idea if the line *would've* affected this
                    # gpio here; probably ought to fix that
                else:
                    if self.index in gpios:
                        yield item, state

    def output(self):
        if self.modified:
            raise DelegatedOutput('gpio0.mode')
        else:
            return ()
