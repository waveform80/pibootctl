import gettext
from textwrap import dedent
from operator import or_
from functools import reduce

from .formatter import FormatDict
from .parser import BootParam, BootCommand
from .tools import int_ranges, TransMap
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


class ExtractError(ValueError):
    """
    Exception raised when an invalid setting is encountered while extracting
    setting values from a configuration. The *line* parameter is the
    :class:`BootLine` instance that caused the original *exc*.
    """
    def __init__(self, line, exc):
        super().__init__(
            _('Invalid setting on line {line.lineno} of {line.path}: {exc}').
            format(line=line, exc=exc))
        self._line = line
        self._exc = exc

    @property
    def line(self):
        return self._line

    @property
    def exc(self):
        return self._exc


class Setting:
    """
    Represents a single configuration setting.

    Each setting belongs to a group of settings, has a *name* which uniquely
    identifies it, a *default* value, and an optional *doc* string.

    The currently configured :attr:`value` can be set by calling
    :meth:`extract` with a parsed configuration (otherwise it holds the
    *default* value). It can be changed by calling :meth:`update` with the
    desired value. The :meth:`validate` method can be called to check the value
    in the context of the whole configuration (for co-dependent values).
    Finally, :meth:`output` is used to generate new lines for the re-written
    configuration file, and :meth:`explain` is used to provide human readable
    information about values for the setting.

    In other words, the typical life-cycle of a setting is:

    * Construction
    * :meth:`extract` called with parsed configuration lines
    * :meth:`update` called with a new value (if any)
    * :meth:`validate` called with the set of all settings
    * :meth:`output` called to generate new configuration lines
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
    def default(self):
        """
        The default value of this setting.
        """
        return self._default

    @property
    def value(self):
        """
        The current value of this setting, as derived from a parsed
        configuration via :meth:`extract`.
        """
        if self.modified:
            return self._value
        else:
            # NOTE: Must be self.default, not self._default; sub-ordinate
            # classes may override the property for complex cases (e.g.
            # platform specific defaults)
            return self.default

    @property
    def modified(self):
        """
        Returns :data:`True` if this setting has been changed in a
        configuration.
        """
        return self._value is not None

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

    def extract(self, config):
        """
        Sets :attr:`value` from *config* which must be an iterable of
        :class:`BootLine` items (e.g. as obtained by calling
        :meth:`BootParser.parse`).
        """
        raise NotImplementedError

    def update(self, value):
        """
        Stores a new *value*; typically this is in response to a user request
        to update the configuration.
        """
        self._value = self._from_user(value)

    def validate(self):
        """
        Validates the :attr:`value` within the context of :attr:`settings`, the
        overall configuration. Raises :exc:`ValueError` in the event that the
        current value is invalid.
        """
        pass

    def output(self):
        """
        Yields lines of configuration for output to the system configuration
        file.
        """
        raise NotImplementedError

    def explain(self):
        """
        Provides a human-readable interpretation of :attr:`value`. Used by the
        "dump" and "show" commands to provide translations of default and
        current values.

        Returns :data:`None` if no explanation is available or necessary.
        Otherwise, must return a :class:`str`.
        """
        return None

    def sibling(self, suffix):
        """
        Utility method which returns the setting with the same name as this
        setting, but for the final part which is replaced with *suffix*.
        """
        return self.settings['.'.join(self.name.split('.')[:-1] + [suffix])]

    def _from_user(self, value):
        """
        Internal method for converting values given by the user into the native
        type of the setting (typically :class:`bool`, :class:`int`, etc.).

        The *value* may be a regular type (:class:`str`, :class:`int`,
        :data:`None`, etc.) as deserialized from one of the input formats (JSON
        or YAML). Alternatively, it may be a :class:`UserStr`, indicating that
        the value is a string given by the user on the command line and should
        be interpreted by the setting accordingly.

        By default, this conversion defers to the :meth:`_from_file` method.
        """
        return self._from_file(value)

    def _from_file(self, value):
        """
        Internal method for converting values read from the boot configuration
        file into the native type of the setting.

        The *value* will be a :class:`str`, and the method must return whatever
        type is native for the setting or :data:`None` to indicate that the
        setting is to be reset to its default state.
        """
        return str(value)

    def _to_file(self, value):
        """
        Internal method for converting values to the format expected in the
        boot configuration file.

        The *value* will be of the type native to the setting (typically
        :class:`int` or :class:`bool`), and the method must return a
        :class:`str`.
        """
        # XXX Can *value* ever be None?
        return str(value)


class BaseOverlayInt(Setting):
    """
    Represents an integer parameter to the base device-tree overlay.

    The *param* is the name of the base device-tree overlay parameter that this
    setting represents.
    """
    def __init__(self, name, *, param, default=0, doc=''):
        super().__init__(name, default=default, doc=doc)
        self._param = param

    @property
    def overlay(self):
        """
        The name of the overlay this parameter affects.
        """
        return 'base'

    @property
    def param(self):
        """
        The name of the parameter within the base overlay that this setting
        represents.
        """
        return self._param

    @property
    def key(self):
        return ('overlays', '', self.param)

    def extract(self, config):
        for item in config:
            if isinstance(item, BootParam):
                if item.overlay == 'base' and item.param == self.param:
                    self._value = self._from_file(item.value)
                    # NOTE: No break here because later settings override
                    # earlier ones

    def update(self, value):
        self._value = to_int(value)

    def output(self):
        if self.value != self.default:
            yield 'dtparam={self.param}={value}'.format(
                self=self, value=self._to_file(self.value))

    def _from_file(self, value):
        return int(value)


class BaseOverlayBool(BaseOverlayInt):
    """
    Represents a boolean parameter to the base device-tree overlay.

    The *param* is the name of the base device-tree overlay parameter that this
    setting represents.
    """
    def __init__(self, name, *, param, default=False, doc=''):
        super().__init__(name, param=param, default=default, doc=doc)

    def _from_user(self, value):
        return to_bool(value)

    def _from_file(self, value):
        return value == 'on'

    def _to_file(self, value):
        return 'on' if value else 'off'


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
                try:
                    self._value = self._from_file(item.params)
                except ExtractError as e:
                    raise e  # don't re-wrap ExtractError
                except ValueError as e:
                    raise ExtractError(item, e)
                # NOTE: No break here because later settings override
                # earlier ones

    def output(self):
        if self.value != self.default:
            if self.index:
                template = '{self.commands[0]}:{self.index}={value}'
            else:
                template = '{self.commands[0]}={value}'
            yield template.format(self=self, value=self._to_file(self.value))


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

    def _from_file(self, value):
        return to_int(value)

    def validate(self):
        if self._valid and self.value not in self._valid:
            raise ValueError(_(
                '{self.name} must be in the range {valid}'
            ).format(self=self, valid=int_ranges(self._valid)))

    def explain(self):
        return self._valid.get(self.value)


class CommandBool(Command):
    """
    Represents a boolean-valued configuration *command* or *commands*.

    The *inverted* parameter indicates that the configuration command
    represented by the setting has inverted logic, e.g. video.overscan.enabled
    represents the ``disable_overscan`` setting and therefore its value is
    always the opposite of the actual written value.
    """
    def __init__(self, name, *, command=None, commands=None, default=False,
                 inverted=False, doc='', index=0):
        super().__init__(name, command=command, commands=commands,
                         default=default, doc=doc, index=index)
        self._inverted = inverted

    @property
    def inverted(self):
        """
        True if the meaning of the command disables a setting when activated.
        """
        return self._inverted

    def _from_file(self, value):
        return bool(int(value) ^ self.inverted)

    def _from_user(self, value):
        return bool(to_bool(value) ^ self.inverted)

    def _to_file(self, value):
        return str(int(value ^ self.inverted))


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
                self._value = item.command == self.force
                # NOTE: No break here because later settings override
                # earlier ones

    def output(self):
        if self.value is not None:
            if self.index:
                template = '{command}:{self.index}={value}'
            else:
                template = '{command}={value}'
            yield template.format(
                self=self,
                value=1,
                command={
                    True:  self.force,
                    False: self.ignore,
                }[self.value],
            )


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

    def validate(self):
        group = self.sibling('group')
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

    def explain(self):
        group = self.sibling('group')
        return {
            0: 'auto from EDID',
            1: self._valid_cea.get(self.value, '?'),
            2: self._valid_dmt.get(self.value, '?'),
        }.get(group.value, '?')


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

    def _from_user(self, value):
        if isinstance(value, UserStr):
            value = value.strip()
            if value:
                value = [int(elem) for elem in value.split(',')]
                if len(value) != 17:
                    raise ValueError(_(
                        '{self.name} takes 17 comma-separated integers'
                    ).format(self=self))
                return value
            return None
        else:
            return value

    def _from_file(self, value):
        value = value.strip()
        if value:
            value = [int(elem) for elem in value.split()]
            if len(value) != 17:
                raise ValueError(_(
                    '{self.name} takes 17 space-separated integers'
                ).format(self=self))
            return value
        return ()

    def _to_file(self, value):
        return ' '.join(str(i) for i in value)


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

    def validate(self):
        if self.value not in (0, 90, 180, 270):
            raise ValueError(_(
                '{self.name} must be 0, 90, 180, or 270'
            ).format(self=self))

    def output(self):
        flip = self.sibling('flip')
        value = (self.value // 90) | (flip.value << 16)
        if value != self.default:
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

    def _from_user(self, value):
        return to_int(value)

    def _from_file(self, value):
        return (super()._from_file(value) & 0x3) * 90


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

    def output(self):
        # See CommandDisplayRotate.output above
        return ()

    def _from_user(self, value):
        return to_int(value)

    def _from_file(self, value):
        return (super()._from_file(value) >> 16) & 0x3


class CommandDPIOutput(CommandInt):
    """
    Represents the setting for the format and output of the DPI pins. This
    works in concert with :class:`CommandDPIDummy` settings which break out
    bits of the bit-mask but do not produce output themselves.
    """
    def __init__(self, name, *, mask, command=None, commands=None, default=0,
                 doc='', index=0, valid=None):
        super().__init__(name, command=command, commands=commands,
                         default=default, doc=doc, index=index, valid=valid)
        assert mask
        self._mask = mask
        self._shift = (mask & -mask).bit_length() - 1  # ffs(3)

    @property
    def mask(self):
        return self._mask

    @property
    def shift(self):
        return self._shift

    def output(self):
        settings = (
            self,
            self.sibling('rgb'),
            self.sibling('clock'),
            self.sibling('hsync.disabled'),
            self.sibling('hsync.polarity'),
            self.sibling('hsync.phase'),
            self.sibling('vsync.disabled'),
            self.sibling('vsync.polarity'),
            self.sibling('vsync.phase'),
            self.sibling('output.mode'),
            self.sibling('output.disabled'),
            self.sibling('output.polarity'),
            self.sibling('output.phase'),
        )
        value = reduce(or_, (
            setting.value << setting.shift
            for setting in settings
        ))
        if self.sibling('enabled').value:
            # For the DPI LCD display, always output dpi_output_format when
            # enable_dpi_lcd is set (and conversely, don't output it when not
            # set)
            template = '{self.commands[0]}={value:#x}'
            yield template.format(self=self, value=value)

    def _from_user(self, value):
        return to_int(value)

    def _from_file(self, value):
        return (super()._from_file(value) & self._mask) >> self._shift


class CommandDPIDummy(CommandDPIOutput):
    """
    Represents portions of the ``dpi_output_format`` bit-mask which do not
    themselves produce output. The :class:`CommandDPIOutput` setting collates
    all values from :class:`CommandDPIDummy` settings.
    """
    def output(self):
        # See CommandDPIOutput.output above
        return ()


class CommandDPIBool(CommandDPIDummy):
    """
    Derivative of :class:`CommandDPIDummy` which represents single-bit
    components of the ``dpi_output_format`` bit-mask.
    """
    def _from_user(self, value):
        return to_bool(value)

    def _from_file(self, value):
        return bool(super()._from_file(value))


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


class CommandEDIDIgnore(CommandBool):
    """
    Represents the ``hdmi_ignore_edid`` "boolean" setting with its bizarre
    "true" value.
    """
    # See hdmi_edid_file in
    # https://www.raspberrypi.org/documentation/configuration/config-txt/video.md
    def __init__(self, name, *, command=None, commands=None, default=False,
                 doc='', index=0):
        super().__init__(name, command=command, commands=commands,
                         default=default, doc=doc, index=index)

    def _from_user(self, value):
        return to_bool(value)

    def _from_file(self, value):
        return to_int(value) == 0xa5000080

    def _to_file(self, value):
        return '0xa5000080' if value else '0'


class CommandKernelAddress(CommandInt):
    """
    Represents the ``kernel_address`` setting, and implements its
    context-sensitive default values. Also handles the deprecated
    ``kernel_old`` configuration parameter.
    """
    @property
    def default(self):
        if self.sibling('64bit').value:
            return 0x80000
        else:
            return 0x8000

    def extract(self, config):
        for item in config:
            if isinstance(item, BootCommand):
                if item.command == self.commands[0]:
                    self._value = self.from_file(item.params)
                elif item.command == 'kernel_old':
                    if self.from_file(item.params):
                        self._value = 0
                # NOTE: No break here because later settings override
                # earlier ones

    def explain(self):
        return self._to_file(self.value)

    def _to_file(self, value):
        return '{:#x}'.format(value)


class CommandKernel64(CommandBool):
    """
    Handles the ``arm_64bit`` configuration setting, and the deprecated
    ``arm_control`` setting it replaced.
    """
    def extract(self, config):
        for item in config:
            if isinstance(item, BootCommand):
                if item.command == self.commands[0]:
                    self._value = self.from_file(item.params)
                elif item.command == 'arm_control':
                    ctrl = int(item.params, base=0)
                    self._value = bool(ctrl & 0x200)
                # NOTE: No break here because later settings override
                # earlier ones


class CommandKernelFilename(Command):
    """
    Handles the ``kernel`` setting and its platform-dependant defaults.
    """
    @property
    def default(self):
        if self.sibling('64bit').value:
            return 'kernel8.img'
        else:
            board_types = get_board_types()
            if 'pi4' in board_types:
                return 'kernel7l.img'
            elif {'pi2', 'pi3'} ^ board_types:
                return 'kernel7.img'
            else:
                return 'kernel.img'
