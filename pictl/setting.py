import gettext
from textwrap import dedent

from . import parser
from .formatter import FormatDict
from .tools import to_bool, to_tri_bool, int_ranges, TransMap

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


class Setting:
    """
    Represents a single configuration setting.

    Each setting belongs to a group of *settings*, has a *name* which uniquely
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
    def __init__(self, name, default=None, doc=''):
        self._settings = None
        self._name = name
        self._default = default
        self._value = default
        self._doc = dedent(doc).format(name=name, default=default)

    @property
    def settings(self):
        """
        The overall settings that this setting belongs to.
        """
        # This is set to a weakref.ref by the Settings initializer (and copy);
        # hence why we call it to return the actual reference.
        return self._settings()

    @property
    def name(self):
        """
        The name of the setting. This is a dot-delimited list of valid
        Python identifiers.
        """
        return self._name

    @property
    def default(self):
        """
        The default value of this setting. This is typically used to determine
        whether to output anything for the setting's :attr:`value`.
        """
        return self._default

    @property
    def value(self):
        """
        The current value of this setting, as derived from a parsed
        configuration via :meth:`extract`.
        """
        return self._value

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
        :class:`Line` items (e.g. as obtained by calling
        :meth:`Parser.parse`).
        """
        raise NotImplementedError

    def update(self, value):
        """
        Stores a new :attr:`value`; typically this is in response to a user
        request to update the configuration.
        """
        self._value = value

    def validate(self):
        """
        Validates the :attr:`value` within the context of :attr:`settings`, the
        overall configuration.
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
        Otherwise, must return a string.
        """
        return None

    def sibling(self, suffix):
        """
        Utility method which returns the setting with the same name as this
        setting, but for the final part which is replaced with *suffix*.
        """
        return self.settings['.'.join(self.name.split('.')[:-1] + [suffix])]


class BaseOverlayInt(Setting):
    """
    Represents an integer parameter to the base device-tree overlay.

    The *param* is the name of the base device-tree overlay parameter that this
    setting represents.
    """
    def __init__(self, name, param, default=0, doc=''):
        super().__init__(name, default, doc)
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
        return ('overlays', '', self.param)

    def extract(self, config):
        for item in config:
            if isinstance(item, parser.Param):
                if item.overlay == 'base' and item.param == self.param:
                    self._value = int(item.value)
                    # NOTE: No break here because later settings override
                    # earlier ones

    def update(self, value):
        self._value = int(value)

    def output(self):
        if self.value != self.default:
            yield 'dtparam={self.param}={self.value}'.format(self=self)


class BaseOverlayBool(BaseOverlayInt):
    """
    Represents a boolean parameter to the base device-tree overlay.

    The *param* is the name of the base device-tree overlay parameter that this
    setting represents.
    """
    def __init__(self, name, param, default=False, doc=''):
        super().__init__(name, param, default, doc)

    def extract(self, config):
        for item in config:
            if isinstance(item, parser.Param):
                if item.overlay == 'base' and item.param == self.param:
                    self._value = item.value == 'on'
                    # NOTE: No break here because later settings override
                    # earlier ones

    def update(self, value):
        self._value = to_bool(value)

    def output(self):
        if self.value != self.default:
            yield 'dtparam={self.param}={on_off}'.format(
                self=self, on_off='on' if self.value else 'off')


class Command(Setting):
    """
    Represents a string-valued configuration *command*.

    This is also the base class for most simple-valued configuration commands
    (integer, boolean, etc).
    """
    def __init__(self, name, command, default='', doc='', index=0):
        doc = dedent(doc).format_map(TransMap(index=index))
        super().__init__(name, default, doc)
        self._command = command
        self._index = index

    @property
    def command(self):
        """
        The configuration command that this setting represents.
        """
        return self._command

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
                    isinstance(item, parser.Command) and
                    item.command == self.command and
                    item.hdmi == self.index):
                self._value = self.from_file(item.params)
                # NOTE: No break here because later settings override
                # earlier ones

    def update(self, value):
        self._value = self.from_user(value)

    def output(self):
        if self.value != self.default:
            if self.index:
                template = '{self.command}:{self.index}={value}'
            else:
                template = '{self.command}={value}'
            yield template.format(self=self, value=self.to_file(self.value))

    def from_file(self, value):
        """
        Translates the configuration file representation of *value* into an
        actual value of the setting.
        """
        return value

    def to_file(self, value):
        """
        Translates an actual *value* of the setting into the corresponding
        representation in the configuration file.
        """
        return str(value)

    def from_user(self, value):
        """
        Translates a *value* given by the user into an actual value of the
        setting. By default this is the same as the translation performed by
        :meth:`from_file` when *value* is a :class:`str` (as it will be when
        specified on the command line). However, *value* can be any other type
        (as provided by the other formats such as YAML or JSON) in which case
        it will be passed through verbatim.
        """
        if isinstance(value, str):
            return self.from_file(value)
        else:
            return value


class CommandInt(Command):
    """
    Represents an integer-valued configuration *command*.

    The *valid* parameter may optionally provide a dictionary mapping valid
    integer values for the command to string explanations, to be provided by
    the basic :meth:`explain` implementation.
    """
    def __init__(self, name, command, default=0, doc='', index=0,
                 valid=None):
        if valid is None:
            valid = {}
        doc = dedent(doc).format_map(
            TransMap(valid=FormatDict(
                valid, key_title=_('Value'), value_title=_('Meaning'))))
        super().__init__(name, command, default, doc, index)
        self._valid = valid

    def from_file(self, value):
        try:
            return int(value)
        except ValueError:
            raise ValueError(_(
                '{self.name} must be an integer number, not {value}'
            ).format(self=self, value=value))

    def validate(self):
        if self._valid and self.value not in self._valid:
            raise ValueError(_(
                '{self.name} must be in the range {valid}'
            ).format(self=self, valid=int_ranges(self._valid)))

    def explain(self):
        return self._valid.get(self.value)


class CommandBool(Command):
    """
    Represents a boolean-valued configuration *command*.

    The *inverted* parameter indicates that the configuration command
    represented by the setting has inverted logic, e.g. video.overscan.enabled
    represents the ``disable_overscan`` setting and therefore its value is
    always the opposite of the actual written value.
    """
    def __init__(self, name, command, default=False, inverted=False,
                 doc='', index=0):
        super().__init__(name, command, default, doc, index)
        self._inverted = inverted

    @property
    def inverted(self):
        """
        True if the meaning of the command disables a setting when activated.
        """
        return self._inverted

    def from_file(self, value):
        return bool(int(value) ^ self.inverted)

    def from_user(self, value):
        if isinstance(value, str):
            return bool(to_bool(value) ^ self.inverted)
        else:
            return bool(value ^ self.inverted)

    def to_file(self, value):
        return str(int(value ^ self.inverted))


class CommandForceIgnore(Setting):
    """
    Represents the tri-valued configuration values with *force* and *ignore*
    commands, e.g. ``hdmi_force_hotplug`` and ``hdmi_ignore_hotplug``.

    For these cases, when both commands are "0" the setting is considered to
    have the value :data:`None` (which in most cases means "determine
    automatically"). When the *force* command is "1", the setting is
    :data:`True` and thus when the *ignore* command is "1", the setting is
    :data:`False`. When both are "1" (a non-sensical setting) the final
    setting encountered takes precedence.
    """
    def __init__(self, name, force, ignore, default=None, doc='', index=0):
        super().__init__(name, default, doc)
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

    @property
    def index(self):
        """
        The index of this setting for multi-valued settings (e.g. settings
        which apply to all HDMI outputs).
        """
        return self._index

    @property
    def key(self):
        return ('commands', self.name)

    def extract(self, config):
        for item in config:
            if (
                    isinstance(item, parser.Command) and
                    item.command in (self.force, self.ignore) and
                    int(item.params)):
                self._value = item.command == self.force
                # NOTE: No break here because later settings override
                # earlier ones

    def update(self, value):
        if isinstance(value, str):
            self._value = to_tri_bool(value)
        else:
            self._value = value

    def output(self):
        if self.value is not self.default:
            if self.index:
                template = '{command}:{self.index}={value}'
            else:
                template = '{command}={value}'
            yield template.format(
                self=self,
                value=int(self.value is not None),
                command={
                    None:  self.force,
                    True:  self.force,
                    False: self.ignore,
                }[self.value],
            )


class CommandDisplayGroup(CommandInt):
    """
    Represents settings that control the group of display modes used for the
    configuration of a video output, e.g. ``hdmi_group`` or ``dpi_group``.
    """
    def __init__(self, name, command, default=0, doc='', index=0):
        super().__init__(name, command, default, doc, index, valid={
            0: 'auto from EDID',
            1: 'CEA',
            2: 'DMT',
        })


class CommandDisplayMode(CommandInt):
    """
    Represents settings that control the mode of a video output, e.g.
    ``hdmi_mode`` or ``dpi_mode``.
    """
    def __init__(self, name, command, default=0, doc='', index=0):
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
        }
        doc = dedent(doc).format_map(
            TransMap(
                valid_cea=FormatDict(
                    self._valid_cea, key_title=_('Mode'), value_title=_('Meaning')),
                valid_dmt=FormatDict(
                    self._valid_dmt, key_title=_('Mode'), value_title=_('Meaning'))
            ))
        super().__init__(name, command, default, doc, index)

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
    def __init__(self, name, command, default=None, doc='', index=0):
        if default is None:
            default = []
        super().__init__(name, command, default, doc, index)

    def from_file(self, value):
        value = value.strip()
        if value:
            value = [int(elem) for elem in value.split()]
            if len(value) != 17:
                raise ValueError(_(
                    '{self.name} takes 17 space-separated integers'
                ).format(self=self))
            return value
        return ()

    def from_user(self, value):
        if isinstance(value, str):
            value = value.strip()
            if value:
                value = [int(elem) for elem in value.split(',')]
                if len(value) != 17:
                    raise ValueError(_(
                        '{self.name} takes 17 comma-separated integers'
                    ).format(self=self))
                return value
            return ()
        else:
            return value

    def to_file(self, value):
        return ' '.join(str(i) for i in value)

    def output(self):
        if self.value:
            yield '{self.command}={value}'.format(
                self=self, value=' '.join(str(elem) for elem in self.value))


class CommandDisplayRotate(CommandInt):
    """
    Represents settings that control the rotation of a video output. This is
    expected to work in concert with a :class:`CommandDisplayFlip` setting
    (both rotate and flip are usually conflated into a single command, e.g.
    ``display_hdmi_rotate`` or ``display_lcd_rotate``).

    Also handles the deprecated ``display_rotate`` command.
    """
    def extract(self, config):
        for item in config:
            if (
                    isinstance(item, parser.Command) and
                    item.command in (self.command, 'display_rotate') and
                    item.hdmi == self.index):
                self._value = self.from_file(item.params)
                # NOTE: No break here because later settings override
                # earlier ones

    def validate(self):
        if self.value not in (0, 90, 180, 270):
            raise ValueError(_(
                '{self.name} must be 0, 90, 180, or 270'
            ).format(self=self))

    def output(self):
        flip = self.sibling('flip')
        value = (
            (self.value // 90) |
            (0x10000 if flip.value in {3, 1} else 0) |
            (0x20000 if flip.value in {3, 2} else 0)
        )
        if value != self.default:
            if self.index:
                template = '{self.command}:{self.index}={value:#x}'
            else:
                template = '{self.command}={value:#x}'
            yield template.format(self=self, value=value)

    def from_file(self, value):
        if isinstance(value, str) and value.lower().startswith('0x'):
            value = int(value, base=16)
        else:
            value = int(value)
        return (value & 0x3) * 90

    def from_user(self, value):
        return int(value)


class CommandDisplayFlip(CommandInt):
    """
    Represents settings that control reflection (flipping) of a video output.
    See :class:`CommandDisplayRotate` for further information.
    """
    def extract(self, config):
        for item in config:
            if (
                    isinstance(item, parser.Command) and
                    item.command in (self.command, 'display_rotate') and
                    item.hdmi == self.index):
                self._value = self.from_file(item.params)
                # NOTE: No break here because later settings override
                # earlier ones

    def validate(self):
        if not (0 <= self.value <= 3):
            raise ValueError(_(
                '{self.name} must be between 0 and 3'
            ).format(self=self))

    def output(self):
        # See CommandDisplayRotate.output above
        return ()

    def from_file(self, value):
        if isinstance(value, str) and value.lower().startswith('0x'):
            value = int(value, base=16)
        else:
            value = int(value)
        return (value >> 16) & 0x3

    def from_user(self, value):
        return int(value)


class CommandHDMIBoost(CommandInt):
    def validate(self):
        if not (0 <= self.value <= 11):
            raise ValueError(_(
                '{self.name} must be between 0 and 11 (default 5)'
            ).format(self=self))
