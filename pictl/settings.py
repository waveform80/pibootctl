import copy
import gettext
from operator import attrgetter
from weakref import ref

from .setting import (
    BaseOverlayBool,
    BaseOverlayInt,
    Command,
    CommandBool,
    CommandDisplayFlip,
    CommandDisplayGroup,
    CommandDisplayMode,
    CommandDisplayRotate,
    CommandDisplayTimings,
    CommandForceIgnore,
    CommandInt,
    CommandHDMIBoost,
)

_ = gettext.gettext


_settings = {
    BaseOverlayBool(
        'i2c.enabled', param='i2c_arm', doc=_(
            """
            Enables the ARM I2C bus on pins 3 (GPIO2) and 5 (GPIO3) of the GPIO
            header (SDA on GPIO2, and SCL on GPIO3).
            """)),
    BaseOverlayInt(
        'i2c.baud', param='i2c_arm_baudrate', default=100000, doc=_(
            """
            The baud-rate of the ARM I2C bus.
            """)),
    BaseOverlayBool(
        'spi.enabled', param='spi', doc=_(
            """
            Enables the SPI bus on pins 19 (GPIO10), 21 (GPIO9), 23 (GPIO11),
            24 (GPIO8), and 25 (GPIO7) of the GPIO header (MOSI on GPIO10, MISO
            on GPIO9, SCLK on GPIO11, CE0 on GPIO8, and CE1 on GPIO7).
            """)),
    BaseOverlayBool(
        'i2s.enabled', param='i2s', doc=_(
            """
            Enables the I2S audio bus on pins 12 (GPIO18), 35 (GPIO19), 38
            (GPIO20), and 40 (GPIO21) on the GPIO header (CLK on GPIO18, FS on
            GPIO19, DIN on GPIO20, and DOUT on GPIO21).
            """)),
    BaseOverlayBool(
        'audio.enabled', param='audio', doc=_(
            """
            Enables the ALSA audio interface.
            """)),
    BaseOverlayBool(
        'watchdog.enabled', param='watchdog', doc=_(
            """
            Enables the hardware watchdog.
            """)),
    CommandBool(
        'video.cec.enabled', command='hdmi_ignore_cec',
        default=True, inverted=True, doc=_(
            """
            Enables CEC (control signals) over the HDMI interface, if supported
            by the connected display. Switch off to pretend CEC is not
            supported at all.
            """)),
    CommandBool(
        'video.cec.init', command='hdmi_ignore_cec_init',
        default=True, inverted=True, doc=_(
            """
            When off, prevents the initial "active source" message being sent
            during bootup. This prevents CEC-enabled displays from coming out
            of standby and/or channel-switching when starting the Pi.
            """)),
    Command(
        'video.cec.osd_name', command='cec_osd_name',
        default='Raspberry Pi', doc=_(
            """
            The name the Pi (as a CEC device) should provide to the connected
            display; defaults to "Raspberry Pi".
            """)),
    CommandBool(
        'video.hdmi.safe', 'hdmi_safe', default=False, doc=_(
            """
            Switch on to attempt "safe mode" settings for maximum HDMI
            compatibility. This is the same as setting:

            * video.hdmi.enabled = on
            * video.hdmi.edid.ignore = on
            * video.hdmi.boost = 4
            * video.hdmi.group = 2
            * video.hdmi.mode = 4
            * video.overscan.enabled = on
            * video.overscan.left = 24
            * video.overscan.right = 24
            * video.overscan.top = 24
            * video.overscan.bottom = 24
            """)),
    CommandBool(
        'video.hdmi.mode.4kp60', command='hdmi_enable_4kp60', doc=_(
            """
            By default, when connected to a 4K monitor, the Raspberry Pi 4B
            will select a 30hz refresh rate. This setting allows selection of
            60Hz refresh rates.

            Note: enabling this will increase power consumption and increase
            the running temperature of the Pi. It is not possible to use 60Hz
            rates on both micro-HDMI ports simultaneously.
            """)),
    CommandInt(
        'video.hdmi.edid.ignore', command='hdmi_ignore_edid', doc=_(
            """
            When on, ignores the display's EDID [1] data; useful when your
            display does not have an accurate EDID.

            [1]: https://en.wikipedia.org/wiki/Extended_Display_Identification_Data
            """)),
    CommandBool(
        'video.hdmi.edid.3d', command='hdmi_force_edid_3d', doc=_(
            """
            When on, pretends that all group 1 (CEA) HDMI modes support 3D even
            when the display's EDID [1] does not indicate this. Defaults to
            off.

            [1]: https://en.wikipedia.org/wiki/Extended_Display_Identification_Data
            """)),
    CommandBool(
        'video.hdmi.powersave', command='hdmi_blanking', doc=_(
            """
            When enabled, if the operating system requests the display enter a
            low-power state using DPMS, the HDMI output will be blanked and
            switched off. When disabled (the default), the output is merely
            blanked.

            Note: this feature is known to cause issues with applications that
            don't use the framebuffer (e.g. omxplayer).

            Note: this feature has not yet been implemented on the Raspberry Pi
            4.
            """)),
    CommandBool(
        'video.overscan.enabled', command='disable_overscan',
        default=True, inverted=True, doc=_(
            """
            When enabled (the default), if a group 1 (CEA) HDMI mode is
            selected (automatically or otherwise), the display output will
            include black borders to align the edges of the output with a
            typical TV display.
            """)),
    CommandInt(
        'video.overscan.left', command='overscan_left', doc=_(
            "The width of the left overscan border. Defaults to 0.")),
    CommandInt(
        'video.overscan.right', command='overscan_right', doc=_(
            "The width of the right overscan border. Defaults to 0.")),
    CommandInt(
        'video.overscan.top', command='overscan_top', doc=_(
            "The height of the top overscan border. Defaults to 0.")),
    CommandInt(
        'video.overscan.bottom', command='overscan_bottom', doc=_(
            "The height of the bottom overscan border. Defaults to 0.")),
    CommandBool(
        'video.overscan.scale', command='overscan_scale', doc=_(
            """
            Switch on to force non-framebuffer layers to conform to the
            overscan settings. The default is off.

            Note: this feature is generally not recommended: it can reduce
            image quality because all layers on the display will be scaled by
            the GPU. Disabling overscan on the display itself is the
            recommended option to avoid images being scaled twice (by the GPU
            and the display).
            """)),
    CommandBool(
        'video.tv.enabled', command='enable_tvout', doc=_(
            """
            On the Pi 4, the composite TV output is disabled by default, as
            driving the TV output slightly impairs the speed of other system
            clocks and slows down the entire computer as a result (older Pi
            models are unaffected).

            Enable this setting to enable TV output on the Pi 4; on older Pi
            models this setting has no effect (composite output is always on
            without performance degradation).
            """)),
    CommandInt(
        'video.tv.mode', command='sdtv_mode', valid={
            0: 'NTSC',
            1: 'NTSC (Japanese)',
            2: 'PAL',
            3: 'PAL (Brazilian)',
            16: 'NTSC (Progressive)',
            18: 'PAL (Progressive)',
        }, doc=_(
            """
            Defines the TV standard used for composite TV output (the 4-pole
            "headphone" socket on newer models). Valid values are as follows:

            {valid}
            """)),
    CommandInt(
        'video.tv.aspect', command='sdtv_aspect', default=1, valid={
            1: '4:3',
            2: '14:9',
            3: '16:9',
        }, doc=_(
            """
            Defines the aspect ratio for the composite TV output. Valid values
            are as follows:

            {valid}
            """)),
    CommandBool(
        'video.tv.colorburst', command='sdtv_disable_colourburst',
        default=True, inverted=True, doc=_(
            """
            Switch off to disable color-burst [1] on the composite TV output.
            The picture will be displayed in monochrome, but may appear
            sharper.

            [1]: https://en.wikipedia.org/wiki/Colorburst
            """)),
}

_settings |= {s for i in (0, 1) for s in (
    CommandForceIgnore(
        'video.hdmi{}.enabled'.format(i), index=i, force='hdmi_force_hotplug',
        ignore='hdmi_ignore_hotplug', doc=_(
            """
            Switch on to force HDMI output to be used even if no HDMI monitor
            is attached (forces the HDMI hotplug signal to be asserted). Switch
            off to force composite TV output even if an HDMI display is
            detected (ignores the HDMI hotplug signal).
            """)),
    Command(
        'video.hdmi{}.edid.filename'.format(i), index=i,
        command='hdmi_edid_filename', doc=_(
            """
            On the Raspberry Pi 4B, you can manually specify the file to read
            for alternate EDID [1] data.

            [1]: https://en.wikipedia.org/wiki/Extended_Display_Identification_Data
            """)),
    CommandHDMIBoost(
        'video.hdmi{}.boost'.format(i), index=i, command='config_hdmi_boost',
        default=5, doc=_(
            """
            Configures the signal strength of the HDMI interface. Must be a
            value between 0 and 11. The default value is 5. Raise this value to
            7 if you are seeing speckling or interference. Very long HDMI
            cables may need 11, but values this high should not be used unless
            absolutely necessary.

            This option is ignored on the Raspberry Pi 4.
            """)),
    CommandDisplayGroup(
        'video.hdmi{}.group'.format(i), index=i, command='hdmi_group',
        doc=_(
            """
            Defines which list of modes should be consulted for the HDMI
            output. The possible values are:

            {valid}

            CEA (Consumer Electronics Association) modes are typically used by
            TVs, hence overscan applies to these modes when enabled. DMT
            (Display Monitor Timings) modes are typically used by monitors,
            hence overscan is implicitly 0 with these modes. The
            video.hdmi{index}.mode setting must be set when this is non-zero.
            """)),
    CommandDisplayMode(
        'video.hdmi{}.mode'.format(i), index=i, command='hdmi_mode',
        doc=_(
            """
            Defines which mode will be used on the HDMI output. This defaults
            to 0 which indicates it should be automatically determined from the
            EDID sent by the connected display. If video.hdmi{index}.group is
            set to 1 (CEA), this must be one of the following values:

            {valid_cea}

            In the table above, "wide" indicates a 16:9 wide-screen variant of
            a mode which usually has a 4:3 aspect ratio. "2x" and "4x" indicate
            a higher clock rate with pixel doubling or quadrupling
            respectively.

            The following values are valid if video.hdmi.group is set to 2
            (DMT):

            {valid_dmt}

            Note that there is a pixel clock limit [2]. The highest supported
            mode is 1920x1200 at 60Hz which reduced blanking.

            [1]: https://www.raspberrypi.org/documentation/configuration/config-txt/video.md
            [2]: https://www.raspberrypi.org/forums/viewtopic.php?f=26&t=20155&p=195443#p195443
            """)),
            # XXX Numbered lists...
    CommandDisplayRotate(
        'video.hdmi{}.rotate'.format(i), index=i,
        command='display_hdmi_rotate', doc=_(
            """
            Controls the rotation of the HDMI output. Valid values are 0 (the
            default), 90, 180, or 270.
            """)),
    CommandDisplayFlip(
        'video.hdmi{}.flip'.format(i), index=i, command='display_hdmi_rotate',
        valid={
            0: 'none',
            1: 'horizontal',
            2: 'vertical',
            3: 'both',
        },
        doc=_(
            """
            Controls the reflection (flipping) of the HDMI output. Valid values
            are:

            {valid}
            """)),
    CommandBool(
        'video.hdmi{}.mode.force'.format(i), index=i,
        command='hdmi_force_mode', doc=_(
            """
            Switching this on forces the mode specified by video.hdmi.group and
            video.hdmi.mode to be used even if they do not appear in the
            enumerated list of modes. This may help if a display seems to be
            ignoring these settings.
            """)),
    CommandDisplayTimings(
        'video.hdmi{}.timings'.format(i), index=i, command='hdmi_timings',
        doc=_(
            """
            An advanced setting that permits the raw HDMI timing values to be
            specified directly for HDMI group 2, mode 87. Please refer to the
            "hdmi_timings" section in [1] for full details.

            [1]: https://www.raspberrypi.org/documentation/configuration/config-txt/video.md
            """)),
    CommandInt(
        'video.hdmi{}.drive'.format(i), index=i, command='hdmi_drive',
        valid={
            0: 'auto',
            1: 'dvi',
            2: 'hdmi',
        }, doc=_(
            """
            Selects the HDMI output mode from the following values:

            {valid}

            In 'dvi' mode, audio output is disabled over HDMI.
            """
        )),
)}


Missing = object()

class Settings:
    def __init__(self):
        self._settings = {
            setting.name: setting
            for setting in copy.deepcopy(_settings)
        }
        for setting in self._settings.values():
            setting._settings = ref(self)

    def __len__(self):
        return len(self._settings)

    def __iter__(self):
        return iter(sorted(
            self._settings.values(), key=attrgetter('key')
        ))

    def __contains__(self, key):
        return key in self._settings

    def __getitem__(self, key):
        return self._settings[key]

    def copy(self):
        new = copy.deepcopy(self)
        for setting in new:
            setting._settings = ref(new)
        return new

    def diff(self, other):
        """
        Returns a set of (self, other) setting tuples for all settings that
        differ between *self* and *other* (another :class:`Settings` instance).
        If a particular setting is missing from either side, its entry will be
        given as :data:`Missing`.
        """
        return {
            (setting, other[setting.name]
                      if setting.name in other else
                      Missing)
            for setting in self
            if setting.name not in other or
            other[setting.name].value != setting.value
        } | {
            (Missing, setting)
            for setting in other
            if setting.name not in self
        }

    def extract(self, config):
        for setting in self:
            setting.extract(config)

    def validate(self):
        for setting in self:
            setting.validate()

    def output(self):
        output = """\
# This file is intended to contain system-made configuration changes. User
# configuration changes should be placed in "usercfg.txt". Please refer to the
# README file for a description of the various configuration files on the boot
# partition.

""".splitlines()
        for setting in self:
            for line in setting.output():
                output.append(line)
        return '\n'.join(output)
