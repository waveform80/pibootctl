import gettext
from copy import deepcopy
from weakref import ref
from operator import or_
from textwrap import dedent
from fnmatch import fnmatch
from functools import reduce
from collections.abc import Mapping
from contextlib import contextmanager
from collections import namedtuple, OrderedDict

from .formatter import FormatDict, TransMap, int_ranges
from .parser import BootOverlay, BootParam, BootCommand
from .userstr import UserStr, to_bool, to_int, to_str
from .info import get_board_types

_ = gettext.gettext


#BASE_PARAM_DEFAULTS = {
#    'audio':            False,
#    'axiperf':          False,
#    'eee':              True,
#    'i2c_arm':          False,
#    'i2c_vc':           False,
#    'i2s':              False,
#    'random':           True,
#    'sd_debug':         False,
#    'sd_force_pio':     False,
#    'spi':              False,
#    'uart0':            True,
#    'uart1':            False,
#    'watchdog':         False,
#}


class ValueWarning(Warning):
    """
    Warning class used by :meth:`Setting.validate` to warn about dangerous
    or inappropriate configurations.
    """


class Settings(Mapping):
    """
    Represents a complete configuration; acts like an ordered mapping of
    names to :class:`Setting` objects.
    """
    def __init__(self):
        # This is deliberately imported upon construction instead of at the
        # module level, partly to avoid a circular reference but mostly because
        # the settings module is "expensive" to import and materially affects
        # start-up time on slower Pis; this matters where it is not required
        # (e.g. just running --help)
        from .settings import SETTINGS

        self._items = deepcopy(SETTINGS)
        for setting in self._items.values():
            setting._settings = ref(self)
        self._visible = set(self._items.keys())

    def __len__(self):
        return len(self._visible)

    def __iter__(self):
        # This curious ordering is necessary to ensure the sorting order of
        # _items is preserved
        for key in self._items:
            if key in self._visible:
                yield key

    def __contains__(self, key):
        return key in self._visible

    def __getitem__(self, key):
        if key not in self._visible:
            raise KeyError(key)
        return self._items[key]

    def copy(self):
        """
        Returns a distinct copy of the configuration that can be updated
        without affecting the original.
        """
        new = deepcopy(self)
        for setting in new._items.values():
            setting._settings = ref(new)
        return new

    def modified(self):
        """
        Returns a copy of the configuration which only contains modified
        settings.
        """
        # When filtering we mustn't actually remove any members of _items as
        # Setting instances may need to refer to a "hidden" value to, for
        # example, determine their default value
        new_visible = {
            name for name in self._visible
            if self[name].modified
        }
        copy = self.copy()
        copy._visible = new_visible
        return copy

    def filter(self, pattern):
        """
        Returns a copy of the configuration which only contains settings with
        names matching *pattern*, which may contain regular shell globbing
        patterns.
        """
        new_visible = {
            name for name in self._visible
            if fnmatch(name, pattern)
        }
        copy = self.copy()
        copy._visible = new_visible
        return copy

    def diff(self, other):
        """
        Returns a set of (self, other) setting tuples for all settings that
        differ between *self* and *other* (another :class:`Settings` instance).
        If a particular setting is missing from either side, its entry will be
        given as :data:`None`.
        """
        return {
            (setting, other[setting.name]
                      if setting.name in other else
                      None)
            for setting in self.values()
            if setting.name not in other or
            other[setting.name].value != setting.value
        } | {
            (None, setting)
            for name in other
            if name not in self
        }

    def extract(self, config):
        """
        Extracts values for the settings from the parsed *config* (which must
        be a sequence of :class:`BootLine` objects or their descendents).
        """
        for setting in self.values():
            for item, value in setting.extract(config):
                setting._value = value
                # TODO track the config items affecting the setting

    def update(self, values):
        """
        Given a mapping of setting names to new values, updates the values
        of the corresponding settings in this collection. If a value is
        :data:`None`, the setting is reset to its default value.
        """
        for name, value in values.items():
            if name not in self._visible:
                raise KeyError(name)
            item = self._items[name]
            item._value = item.update(value)

    def validate(self):
        """
        Checks for errors in the configuration. This ensures that each setting
        makes sense in the wider context of all other settings.
        """
        # NOTE: This ignores the _visible filter; the complete configuration
        # is always validated
        for item in self._items.values():
            item.validate()

    def output(self):
        """
        Generate a new boot configuration file which represents the settings
        stored in this mapping.
        """
        output = """\
# This file is intended to contain system-made configuration changes. User
# configuration changes should be placed in "usercfg.txt". Please refer to the
# README file for a description of the various configuration files on the boot
# partition.

""".splitlines()
        for name, setting in self._items.items():
            if name in self._visible:
                for line in setting.output():
                    output.append(line)
        return '\n'.join(output)


class Setting:
    """
    Represents a configuration setting.

    Each setting has a *name* which uniquely identifies the setting, a
    *default* value, and an optional *doc* string. The specification is used
    to:

    * :meth:`extract` the value of a setting from parsed configuration lines
    * :meth:`update` the value of a setting from user-provided values
    * :meth:`validate` a setting in the wider context of a configuration
    * generate :meth:`output` to represent the setting in a new config.txt

    Optionally:

    * :attr:`hint` may be queried to describe a value in human-readable terms
    """
    def __init__(self, name, *, default=None, doc=''):
        # NOTE: self._settings is set in Settings.__init__ and Settings.copy
        self._settings = None
        self._name = name
        self._default = default
        self._value = None
        self._doc = dedent(doc).format(name=name, default=default)

    @property
    def settings(self):
        """
        The overall settings that this setting belongs to.
        """
        assert self._settings
        # This is set to a weakref.ref by the Settings initializer (and copy);
        # hence why we call it to return the actual reference.
        return self._settings()

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
        """
        return ()

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
        The default value of this setting. The collection of *settings* is
        provided for calculation of the default in the case of settings that
        are context-dependent.
        """
        return self._default

    @property
    def value(self):
        """
        Returns the current value of the setting (or the :attr:`default` if the
        setting has not been :attr:`modified`).
        """
        # NOTE: Must use self.default here, not self._default as descendents
        # may calculate more complex defaults
        return self.default if self._value is None else self._value

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
        Given a *config* which must be an iterable of :class:`BootLine` items
        (e.g. as obtained by calling :meth:`BootParser.parse`), yields each
        line that affects the setting's value, and the new value that the
        line produces (or :data:`None` indicating that the value is now, or
        is still, the default state).

        .. note::

            Note to implementers: the method must *not* affect :attr:`value`
            directly; the caller will handle this.
        """
        raise NotImplementedError

    def update(self, value):
        """
        Given a *value*, returns it transformed to the setting's native type
        (typically an :class:`int` or :class:`bool` but can be whatever type is
        appropriate).

        The *value* may be a regular type (:class:`str`, :class:`int`,
        :data:`None`, etc.) as deserialized from one of the input formats (JSON
        or YAML). Alternatively, it may be a :class:`UserStr`, indicating that
        the value is a string given by the user on the command line and should
        be interpreted by the setting accordingly.

        .. note::

            Note to implementers: the method must *not* affect :attr:`value`
            directly; the caller will handle this.
        """
        return value

    def validate(self):
        """
        Validates the setting within the context of the other *settings*.
        Raises :exc:`ValueError` in the event that the current value is
        invalid. May optionally use :exc:`ValueWarning` to warn about dangerous
        or inappropriate configurations.
        """
        pass

    def output(self, settings):
        """
        Given the overall *settings* context, yields lines of configuration to
        represent the state of the setting.
        """
        raise NotImplementedError

    @contextmanager
    def _override(self, value):
        """
        Used as a context manager, temporarily overrides the *value* of this
        setting within *settings* until the contextual block ends. Note that
        *value* does **not** pass through :meth:`update` via this route.
        """
        old_value = self._value
        self._value = value
        try:
            yield
        finally:
            self._value = old_value

    def _relative(self, path):
        """
        Internal method which returns the name of this setting with a suffix
        replaced by *path*.

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
                    # NOTE: We can "break" here because there's no way to
                    # "unload" an overlay in the config
                    break

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
                    # NOTE: No break here because later settings override
                    # earlier ones

    def update(self, value):
        return value

    def output(self):
        # NOTE: We don't worry about outputting the dtoverlay; presumably that
        # is represented by another setting and the key property will order
        # our output appropriately after the correct dtoverlay output
        if self.modified:
            yield 'dtparam={self.param}={self.value}'.format(self=self)


class OverlayParamInt(OverlayParam):
    """
    Represents an integer parameter to a device-tree overlay.
    """
    def __init__(self, name, *, overlay='base', param, default=0, doc=''):
        super().__init__(name, overlay=overlay, param=param, default=default,
                         doc=doc)

    def extract(self, config):
        for item, value in super().extract(config):
            yield item, None if value is None else int(value)

    def update(self, value):
        return to_int(super().update(value))


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
    represented, the first will be the "primary" command, and all the rest
    are considered deprecated variants.

    This is also the base class for most simple-valued configuration commands
    (integer, boolean, etc).
    """
    def __init__(self, name, *, command=None, commands=None, default=None,
                 doc='', index=0):
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
                    item.hdmi == self.index):
                yield item, item.params
                # NOTE: No break here because later settings override
                # earlier ones

    def output(self, fmt=''):
        if self.modified:
            if self.index:
                template = '{self.commands[0]}:{self.index}={self.value:{fmt}}'
            else:
                template = '{self.commands[0]}={self.value:{fmt}}'
            yield template.format(self=self, fmt=fmt)


class CommandInt(Command):
    """
    Represents an integer-valued configuration *command* or *commands*.

    The *valid* parameter may optionally provide a dictionary mapping valid
    integer values for the command to string explanations, to be provided by
    the basic :meth:`explain` implementation.
    """
    def __init__(self, name, *, command=None, commands=None, default=0, doc='',
                 index=0, valid=None):
        if valid is None:
            valid = {}
        doc = dedent(doc).format_map(
            TransMap(valid=FormatDict(
                valid, key_title=_('Value'), value_title=_('Meaning'))))
        super().__init__(name, command=command, commands=commands,
                         default=default, doc=doc, index=index)
        self._valid = valid

    @property
    def hint(self):
        return self._valid.get(self.value)

    def extract(self, config):
        for item, value in super().extract(config):
            yield item, to_int(value)

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
            yield item, bool(int(value))

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

    def update(self, value):
        return not super().update(value)

    def output(self, fmt='d'):
        if self.modified:
            with self._override(not value):
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
        for item in config:
            if (
                    isinstance(item, BootCommand) and
                    item.command in self.commands and
                    int(item.params)):
                yield item, (item.command == self.force)
                # NOTE: No break here because later settings override
                # earlier ones

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
        if any(settings[name].modified for name in self._names):
            value = reduce(or_, (
                settings[name].value << settings[name]._shift
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
        return ()


class CommandDisplayGroup(CommandInt):
    """
    Represents settings that control the group of display modes used for the
    configuration of a video output, e.g. ``hdmi_group`` or ``dpi_group``.
    """
    def __init__(self, name, *, command=None, commands=None, default=0, doc='',
                 index=0):
        super().__init__(name, command=command, commands=commands,
                         default=default, doc=doc, index=index, valid={
                             0: 'auto from EDID',
                             1: 'CEA',
                             2: 'DMT',
                         })


class CommandDisplayMode(CommandInt):
    """
    Represents settings that control the mode of a video output, e.g.
    ``hdmi_mode`` or ``dpi_mode``.
    """
    def __init__(self, name, *, command=None, commands=None, default=0, doc='',
                 index=0):
        self._valid_cea = {
            1:  'VGA (640x480)',
            2:  '480p @60Hz',
            3:  '480p @60Hz wide',
            4:  '720p @60Hz',
            5:  '1080i @60Hz',
            6:  '480i @60Hz',
            7:  '480i @60Hz wide',
            8:  '240p @60Hz',
            9:  '240p @60Hz wide',
            10: '480i @60Hz 4x',
            11: '480i @60Hz 4x, wide',
            12: '240p @60Hz 4x',
            13: '240p @60Hz 4x, wide',
            14: '480p @60Hz 2x',
            15: '480p @60Hz 2x, wide',
            16: '1080p @60Hz',
            17: '576p @50Hz',
            18: '576p @50Hz wide',
            19: '720p @50Hz',
            20: '1080i @50Hz',
            21: '576i @50Hz',
            22: '576i @50Hz wide',
            23: '288p @50Hz',
            24: '288p @50Hz wide',
            25: '576i @50Hz 4x',
            26: '576i @50Hz 4x, wide',
            27: '288p @50Hz 4x',
            28: '288p @50Hz 4x, wide',
            29: '576p @50Hz 2x',
            30: '576p @50Hz 2x, wide',
            31: '1080p @50Hz',
            32: '1080p @24Hz',
            33: '1080p @25Hz',
            34: '1080p @30Hz',
            35: '480p @60Hz 4x',
            36: '480p @60Hz 4x, wide',
            37: '576p @50Hz 4x',
            38: '576p @50Hz 4x, wide',
            39: '1080i @50Hz reduced blanking',
            40: '1080i @100Hz',
            41: '720p @100Hz',
            42: '576p @100Hz',
            43: '576p @100Hz wide',
            44: '576i @100Hz',
            45: '576i @100Hz wide',
            46: '1080i @120Hz',
            47: '720p @120Hz',
            48: '480p @120Hz',
            49: '480p @120Hz wide',
            50: '480i @120Hz',
            51: '480i @120Hz wide',
            52: '576p @200Hz',
            53: '576p @200Hz wide',
            54: '576i @200Hz',
            55: '576i @200Hz wide',
            56: '480p @240Hz',
            57: '480p @240Hz wide',
            58: '480i @240Hz',
            59: '480i @240Hz wide',
        }
        self._valid_dmt = {
            1:  '640x350 @85Hz',
            2:  '640x400 @85Hz',
            3:  '720x400 @85Hz',
            4:  '640x480 @60Hz',
            5:  '640x480 @72Hz',
            6:  '640x480 @75Hz',
            7:  '640x480 @85Hz',
            8:  '800x600 @56Hz',
            9:  '800x600 @60Hz',
            10: '800x600 @72Hz',
            11: '800x600 @75Hz',
            12: '800x600 @85Hz',
            13: '800x600 @120Hz',
            14: '848x480 @60Hz',
            15: '1024x768 @43Hz incompatible with the Raspberry Pi',
            16: '1024x768 @60Hz',
            17: '1024x768 @70Hz',
            18: '1024x768 @75Hz',
            19: '1024x768 @85Hz',
            20: '1024x768 @120Hz',
            21: '1152x864 @75Hz',
            22: '1280x768 reduced blanking',
            23: '1280x768 @60Hz',
            24: '1280x768 @75Hz',
            25: '1280x768 @85Hz',
            26: '1280x768 @120Hz reduced blanking',
            27: '1280x800 reduced blanking',
            28: '1280x800 @60Hz',
            29: '1280x800 @75Hz',
            30: '1280x800 @85Hz',
            31: '1280x800 @120Hz reduced blanking',
            32: '1280x960 @60Hz',
            33: '1280x960 @85Hz',
            34: '1280x960 @120Hz reduced blanking',
            35: '1280x1024 @60Hz',
            36: '1280x1024 @75Hz',
            37: '1280x1024 @85Hz',
            38: '1280x1024 @120Hz reduced blanking',
            39: '1360x768 @60Hz',
            40: '1360x768 @120Hz reduced blanking',
            41: '1400x1050 reduced blanking',
            42: '1400x1050 @60Hz',
            43: '1400x1050 @75Hz',
            44: '1400x1050 @85Hz',
            45: '1400x1050 @120Hz reduced blanking',
            46: '1440x900 reduced blanking',
            47: '1440x900 @60Hz',
            48: '1440x900 @75Hz',
            49: '1440x900 @85Hz',
            50: '1440x900 @120Hz reduced blanking',
            51: '1600x1200 @60Hz',
            52: '1600x1200 @65Hz',
            53: '1600x1200 @70Hz',
            54: '1600x1200 @75Hz',
            55: '1600x1200 @85Hz',
            56: '1600x1200 @120Hz reduced blanking',
            57: '1680x1050 reduced blanking',
            58: '1680x1050 @60Hz',
            59: '1680x1050 @75Hz',
            60: '1680x1050 @85Hz',
            61: '1680x1050 @120Hz reduced blanking',
            62: '1792x1344 @60Hz',
            63: '1792x1344 @75Hz',
            64: '1792x1344 @120Hz reduced blanking',
            65: '1856x1392 @60Hz',
            66: '1856x1392 @75Hz',
            67: '1856x1392 @120Hz reduced blanking',
            68: '1920x1200 reduced blanking',
            69: '1920x1200 @60Hz',
            70: '1920x1200 @75Hz',
            71: '1920x1200 @85Hz',
            72: '1920x1200 @120Hz reduced blanking',
            73: '1920x1440 @60Hz',
            74: '1920x1440 @75Hz',
            75: '1920x1440 @120Hz reduced blanking',
            76: '2560x1600 reduced blanking',
            77: '2560x1600 @60Hz',
            78: '2560x1600 @75Hz',
            79: '2560x1600 @85Hz',
            80: '2560x1600 @120Hz reduced blanking',
            81: '1366x768 @60Hz',
            82: '1920x1080 @60Hz 1080p',
            83: '1600x900 reduced blanking',
            84: '2048x1152 reduced blanking',
            85: '1280x720 @60Hz 720p',
            86: '1366x768 reduced blanking',
            87: 'User timings',
        }
        doc = dedent(doc).format_map(
            TransMap(
                valid_cea=FormatDict(self._valid_cea, key_title=_('Mode'),
                                     value_title=_('Meaning')),
                valid_dmt=FormatDict(self._valid_dmt, key_title=_('Mode'),
                                     value_title=_('Meaning'))
            ))
        super().__init__(name, command=command, commands=commands,
                         default=default, doc=doc, index=index)

    @property
    def hint(self):
        return {
            0: 'auto from EDID',
            1: self._valid_cea.get(self.value, '?'),
            2: self._valid_dmt.get(self.value, '?'),
        }.get(self.settings[self._relative('.group')].value, '?')

    def validate(self):
        group = self.settings[self._relative('.group')]
        min_, max_ = {
            0: (0, 0),
            1: (1, 59),
            2: (1, 87),
        }[group.value]
        if not (min_ <= self.value <= max_):
            raise ValueError(_(
                '{self.name} must be between {min} and {max} when '
                '{group.name} is {group.value}'
            ).format(self=self, min=min_, max=max_, group=group))


class CommandDisplayTimings(Command):
    """
    Represents settings that manually specify the timings of a video output,
    e.g. ``hdmi_timings`` or ``dpi_timings``.
    """
    def __init__(self, name, *, command=None, commands=None, default=None,
                 doc='', index=0):
        if default is None:
            default = []
        super().__init__(name, command=command, commands=commands,
                         default=default, doc=doc, index=index)

    def extract(self, config):
        for item, value in super().extract(config):
            value = value.strip()
            if value:
                value = [int(elem) for elem in value.split()]
                yield item, value
            else:
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
        flip = self.settings[self._relative('.flip')]
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
        return ()


class CommandDPIOutput(CommandMaskMaster):
    """
    Represents the format portion of ``dpi_output_format``.
    """
    def output(self):
        if self.settings[self._relative('.enabled')].value:
            # For the DPI LCD display, always output dpi_output_format when
            # enable_dpi_lcd is set (and conversely, don't output it when not
            # set)
            yield from super().output(settings)


class CommandDPIDummy(CommandMaskDummy):
    """
    Represents the non-format portions of ``dpi_output_format``.
    """
    pass


class CommandHDMIBoost(CommandInt):
    """
    Represents the ``config_hdmi_boost`` setting with its custom range of
    valid values.
    """
    def validate(self):
        if not (0 <= self.value <= 11):
            raise ValueError(_(
                '{self.name} must be between 0 and 11 (default 5)'
            ).format(self=self))


class CommandEDIDIgnore(CommandIntHex):
    """
    Represents the ``hdmi_ignore_edid`` "boolean" setting with its bizarre
    "true" value.
    """
    # See hdmi_edid_file in
    # https://www.raspberrypi.org/documentation/configuration/config-txt/video.md
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
                    boot_delay = to_int(item.params)
                    yield item, boot_delay + (boot_delay_ms / 1000)
                elif item.command == 'boot_delay_ms':
                    boot_delay_ms = to_int(item.params)
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
        if self.settings[self._relative('.64bit')].value:
            return 0x80000
        else:
            return 0x8000

    def extract(self, config):
        for item in config:
            if isinstance(item, BootCommand):
                if item.command == 'kernel_address':
                    yield item, to_int(item.params)
                elif item.command == 'kernel_old':
                    if to_int(item.params):
                        yield item, 0


class CommandKernel64(CommandBool):
    """
    Handles the ``arm_64bit`` configuration setting, and the deprecated
    ``arm_control`` setting it replaced.
    """
    def extract(self, config):
        for item in config:
            if isinstance(item, BootCommand):
                if item.command == 'arm_64bit':
                    yield item, to_bool(item.params)
                elif item.command == 'arm_control':
                    yield item, bool(to_int(item.params) & 0x200)


class CommandKernelFilename(Command):
    """
    Handles the ``kernel`` setting and its platform-dependent defaults.
    """
    # TODO os_prefix integration
    @property
    def default(self):
        if self.settings[self._relative('.64bit')].value:
            return 'kernel8.img'
        else:
            board_types = get_board_types()
            if 'pi4' in board_types:
                return 'kernel7l.img'
            elif {'pi2', 'pi3'} & board_types:
                return 'kernel7.img'
            else:
                return 'kernel.img'


class CommandKernelCmdline(Command):
    """
    Handles the ``cmdline`` setting.
    """
    # TODO os_prefix integration
    # TODO modification/tracking of external file


class CommandDeviceTree(Command):
    """
    Handles the ``device_tree`` command.
    """
    # TODO os_prefix integration


class CommandRamFSAddress(CommandIntHex):
    """
    Handles the ``ramfsaddr`` and ``initramfs`` commands.
    """
    @property
    def hint(self):
        if self.value == 0:
            return 'followkernel'
        else:
            # FIXME
            return super().hint

    def extract(self, config):
        for item in config:
            if isinstance(item, BootCommand):
                if item.command == 'ramfsaddr':
                    yield item, to_int(item.params)
                elif item.command == 'initramfs':
                    filename, address = item.params
                    if address == 'followkernel':
                        yield item, None
                    else:
                        yield item, to_int(address)


class CommandRamFSFilename(Command):
    """
    Handles the ``ramfsfile`` and ``initramfs`` commands which can both
    accept multiple files (to be concatenated).
    """
    # TODO os_prefix integration

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
        if self.modified and len(self.name) + len('=') + len(self.value) > 80:
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
        if {'pi3', 'pi4', 'pi0w'} & get_board_types():
            return not self.settings['bluetooth.enabled'].value
        else:
            return True


class OverlaySerialUART(Setting):
    @property
    def default(self):
        if {'pi3', 'pi4', 'pi0w'} & get_board_types():
            if self.settings['bluetooth.enabled'].value:
                return 1
            else:
                return 0
        else:
            return 0

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
        if self.value == 1 and not self.settings['bluetooth.enabled'].value:
            raise ValueError(_(
                'serial.uart must be 0 when bluetooth.enabled is off'))

    def output(self):
        # Output is handled by bluetooth.enabled setting
        return ()


class OverlayBluetoothEnabled(Setting):
    """
    Represents the ``miniuart-bt`` and ``disable-bt`` overlays (via the
    ``bluetooth.enabled`` pseudo-command).
    """
    @property
    def default(self):
        return bool({'pi3', 'pi4', 'pi0w'} & get_board_types())

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
        if self.modified or self.settings['serial.uart'].modified:
            # TODO what about pi3- prefix on systems with deprecated overlays?
            if not self.value:
                yield 'dtoverlay=disable-bt'
            elif self.settings['serial.uart'].value == 0:
                yield 'dtoverlay=miniuart-bt'


class CommandCPUFreqMax(CommandInt):
    """
    Handles the ``arm_freq`` command.
    """
    @property
    def default(self):
        board_types = get_board_types()
        if 'pi0' in board_types:
            return 1000
        if 'pi1' in board_types:
            return 700
        elif 'pi2' in board_types:
            return 900
        elif 'pi3+' in board_types:
            # NOTE: pi3+ must come first here as pi3 & pi3+ appear together
            # in pi3+ specific board-type entries
            return 1400
        elif 'pi3' in board_types:
            return 1200
        elif 'pi4' in board_types:
            return 1500
        else:
            return 0


class CommandCPUFreqMin(CommandInt):
    """
    Handles the ``arm_freq_min`` command.
    """
    @property
    def default(self):
        board_types = get_board_types()
        if {'pi0', 'pi1'} & board_types:
            return 700
        elif {'pi2', 'pi3', 'pi4'} & board_types:
            return 600
        else:
            return 0


class CommandCoreFreqMax(CommandInt):
    """
    Handles the ``core_freq`` command.
    """
    @property
    def default(self):
        board_types = get_board_types()
        if {'pi1', 'pi2'} & board_types:
            return 250
        elif {'pi0', 'pi3'} & board_types:
            return 400
        elif 'pi4' in board_types:
            return 500
        else:
            return 0

    def output(self):
        blocks = [self] + [
            self.settings[self._relative(
                '...{block}.frequency.max'.format(block=block)
            )]
            for block in ('h264', 'isp', 'v3d')
        ]
        if any(block.modified for block in blocks):
            if all(self.value == block.value for block in blocks):
                yield 'gpu_freq={value}'.format(value=self.value)
            else:
                yield from super().output()


class CommandCoreFreqMin(CommandInt):
    """
    Handles the ``core_freq_min`` command.
    """
    @property
    def default(self):
        board_types = get_board_types()
        if (
                ('pi4' in board_types) and
                self._value(settings, 'video.hdmi.mode.4kp60', default=True)):
            return 275
        elif board_types:
            return 250
        else:
            return 0

    def output(self):
        blocks = [self] + [
            self.settings[self._relative(
                '...{block}.frequency.max'.format(block=block)
            )]
            for block in ('h264', 'isp', 'v3d')
        ]
        if any(block.modified for block in blocks):
            if all(self.value == block.value for block in blocks):
                yield 'gpu_freq_min={value}'.format(value=self.value)
            else:
                yield from super().output()


class CommandGPUFreqMax(CommandInt):
    """
    Handles the ``h264_freq``, ``isp_freq``, and ``v3d_freq`` commands.
    """
    @property
    def default(self):
        board_types = get_board_types()
        if {'pi1', 'pi2'} & board_types:
            return 250
        elif {'pi0', 'pi3'} & board_types:
            return 300
        elif 'pi4' in board_types:
            return 500
        else:
            return 0

    def output(self):
        blocks = [self] + [
            self.settings[self._relative(
                '...{block}.frequency.max'.format(block=block)
            )]
            for block in ('h264', 'isp', 'v3d')
        ]
        if any(block.modified for block in blocks):
            if all(self.value == block.value for block in blocks):
                # Handled by gpu.core.frequency.max in this case
                pass
            else:
                yield from super().output()


class CommandGPUFreqMin(CommandInt):
    """
    Handles the ``h264_freq_min``, ``isp_freq_min``, and ``v3d_freq_min``
    commands.
    """
    @property
    def default(self):
        board_types = get_board_types()
        if 'pi4' in board_types:
            return 500
        elif board_types:
            return 250
        else:
            return 0

    def output(self):
        blocks = [self] + [
            self.settings[self._relative(
                '...{block}.frequency.max'.format(block=block)
            )]
            for block in ('h264', 'isp', 'v3d')
        ]
        if any(block.modified for block in blocks):
            if all(self.value == block.value for block in blocks):
                # Handled by gpu.core.frequency.min in this case
                pass
            else:
                yield from super().output()
