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
    CommandEDIDIgnore,
    CommandDPIOutput,
    CommandDPIDummy,
    CommandDPIBool,
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
        'video.cec.name', command='cec_osd_name',
        default='Raspberry Pi', doc=_(
            """
            The name the Pi (as a CEC device) should provide to the connected
            display; defaults to "Raspberry Pi".
            """)),
    CommandBool(
        'video.hdmi.safe', command='hdmi_safe', default=False, doc=_(
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
    CommandEDIDIgnore(
        'video.hdmi.edid.ignore', command='hdmi_ignore_edid', doc=_(
            """
            When on, ignores the display's EDID [1] data; useful when your
            display does not have an accurate EDID.

            [1]: https://en.wikipedia.org/wiki/Extended_Display_Identification_Data
            """)),
    CommandBool(
        'video.hdmi.edid.override', command='hdmi_edid_file', doc=_(
            """
            When on, read EDID [1] data from an 'edid.dat' file, located in the
            boot partition, instead of reading it from the monitor. To generate
            an 'edid.dat' file use:

            $ sudo tvservice -d edid.dat

            [1]: https://en.wikipedia.org/wiki/Extended_Display_Identification_Data
            """)),
    CommandBool(
        'video.hdmi.edid.parse', command='disable_fw_kms_setup', default=True,
        inverted=True, doc=_(
            """
            By default, the firmware parses the EDID of any HDMI attached
            display, picks an appropriate video mode, then passes the
            resolution and frame rate of the mode, along with overscan
            parameters, to the Linux kernel via settings on the kernel command
            line. In rare circumstances, this can have the effect of choosing a
            mode that is not in the EDID, and may be incompatible with the
            device.

            You can disable this option to prevent passing these parameters and
            avoid this problem. The Linux video mode system (KMS) will then
            parse the EDID itself and pick an appropriate mode.
            """)),
    CommandInt(
        'video.hdmi.edid.contenttype', command='edid_content_type', valid={
            0: 'default',
            1: 'graphics',
            2: 'photo',
            3: 'cinema',
            4: 'game',
        }, doc=_(
            """
            Forces the EDID content type to the specified value. Valid values
            are:

            {valid}
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
    CommandInt(
        'video.framebuffer.depth', command='framebuffer_depth', default=16,
        valid={
            8:  '8-bit framebuffer; default RGB palette is unreadable',
            16: '16-bit framebuffer',
            24: '24-bit framebuffer; may result in corrupted display',
            32: '32-bit framebuffer; may require video.framebuffer.alpha '
                'to be disabled',
        }, doc=_(
            """
            Specifies the number of bits-per-pixel (bpp) used by the console
            framebuffer. The default value is 16, but other valid values are:

            {valid}
            """)),
    CommandBool(
        'video.framebuffer.alpha', command='framebuffer_ignore_alpha',
        default=True, inverted=True, doc=_(
            """
            Specifies whether the console framebuffer has an alpha channel.
            It may be necessary to switch this off when video.framebuffer.depth
            is set to 32 bpp.
            """)),
    CommandInt(
        'video.framebuffer.priority', command='framebuffer_priority',
        default=0, valid={
            0: 'Main LCD',
            1: 'Secondary LCD',
            2: 'HDMI 0',
            3: 'Composite/TV',
            7: 'HDMI 1',
        }, doc=_(
            """
            On a system with multiple displays, using the legacy (pre-KMS)
            graphics driver, this forces a specific internal display device to
            be the first Linux framebuffer (i.e. /dev/fb0). The values that can
            be specified are:

            {valid}
            """)),
    CommandInt(
        'video.framebuffer.width', command='framebuffer_width', default=0,
        doc=_(
            """
            Specifies the width of the console framebuffer in pixels. The
            default is the display width minus the total horizontal overscan.
            """)),
    CommandInt(
        'video.framebuffer.width.max', command='max_framebuffer_width',
        default=0, doc=_(
            """
            Specifies the maximum width of the console framebuffer in pixels.
            The default is not to limit the size of the framebuffer.
            """)),
    CommandInt(
        'video.framebuffer.height', command='framebuffer_height', default=0,
        doc=_(
            """
            Specifies the height of the console framebuffer in pixels. The
            default is the display height minus the total vertical overscan.
            """)),
    CommandInt(
        'video.framebuffer.height.max', command='max_framebuffer_height',
        default=0, doc=_(
            """
            Specifies the maximum height of the console framebuffer in pixels.
            The default is not to limit the size of the framebuffer.
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
    CommandBool(
        'video.dsi.enabled', command='ignore_lcd',
        default=True, inverted=True, doc=_(
            """
            By default, an LCD display attached to the DSI connector is used
            when it is detected on the I2C bus. If this setting is disabled,
            this detection phase will be skipped and the LCD display will not
            be used.
            """)),
    CommandBool(
        'video.dsi.default', command='display_default_lcd',
        default=True, doc=_(
            """
            If an LCD display is detected on the DSI connector, it will be used
            as the default display and will show the framebuffer. If this
            setting is disabled, then (usually) the HDMI output will be the
            default. The LCD can still be used by choosing its display number
            from supported applications, e.g. omxplayer.
            """)),
    CommandInt(
        'video.dsi.framerate', command='lcd_framerate', default=60, doc=_(
            """
            Specifies the framerate of an LCD display connected to the DSI
            port. Defaults to 60Hz.
            """)),
    CommandBool(
        'video.dsi.touch.enabled', command='disable_touchscreen',
        default=True, inverted=True, doc=_(
            """
            Enables or disables the touchscreen of the official Raspberry Pi
            LCD display.
            """)),
    CommandDisplayRotate(
        'video.dsi.rotate', command='display_hdmi_rotate', lcd=True, doc=_(
            """
            Controls the rotation of an LCD display connected to the DSI port.
            Valid values are 0 (the default), 90, 180, or 270.
            """)),
    CommandDisplayFlip(
        'video.dsi.flip', command='display_hdmi_rotate', valid={
            0: 'none',
            1: 'horizontal',
            2: 'vertical',
            3: 'both',
        },
        doc=_(
            """
            Controls the reflection (flipping) of an LCD display connected to
            the DSI port. Valid values are:

            {valid}
            """)),
    CommandBool(
        'video.dpi.enabled', command='enable_dpi_lcd', doc=_(
            """
            Enables LCD displays attached to the DPI GPIOs. This is to allow
            the use of third-party LCD displays using the parallel display
            interface [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    CommandDisplayGroup(
        'video.dpi.group', command='dpi_group', doc=_(
            """
            Defines which list of modes should be consulted for DPI LCD
            output. The possible values are:

            {valid}

            CEA (Consumer Electronics Association) modes are typically used by
            TVs, hence overscan applies to these modes when enabled. DMT
            (Display Monitor Timings) modes are typically used by monitors,
            hence overscan is implicitly 0 with these modes. The video.dpi.mode
            setting must be set when this is non-zero.
            """)),
    CommandDisplayMode(
        'video.dpi.mode', command='dpi_mode', doc=_(
            """
            Defines which mode will be used for DPI LCD output. This defaults
            to 0 which indicates it should be automatically determined from the
            EDID sent by the connected display. If video.dpi.group is set to 1
            (CEA), this must be one of the following values:

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
    CommandDisplayTimings(
        'video.dpi.timings', command='dpi_timings', doc=_(
            """
            An advanced setting that permits the raw timing values to be
            specified directly for DPI group 2, mode 87. Please refer to the
            "dpi_timings" section in [1] for full details.

            [1]: https://www.raspberrypi.org/documentation/configuration/config-txt/video.md
            """)),
    CommandDPIOutput(
        'video.dpi.format', command='dpi_output_format', default=1,
        mask=0xf, valid={
            1: '9-bit RGB666; unsupported',
            2: '16-bit RGB565; config 1',
            3: '16-bit RGB565; config 2',
            4: '16-bit RGB565; config 3',
            5: '18-bit RGB666; config 1',
            6: '18-bit RGB666; config 2',
            7: '24-bit RGB888',
        }, doc=_(
            """
            Configures which GPIO pins will be used for DPI LCD output, and how
            those pins will be used. Valid values are:

            {valid}

            The various configurations are as follows (in the following table,
            R-7 means the 7th bit of the Red value, B-2 means the 2nd bit of
            the Blue value, etc.), when video.dpi.rgb is set to 'RGB' ordering:

            | GPIO | RGB565 (config 1) | RGB565 (config 2) | RGB565 (config 3) | RGB666 (config 1) | RGB666 (config 2) | RGB888 |
            | 27 | -   | -   | -   | -   | -   | R-7 |
            | 26 | -   | -   | -   | -   | -   | R-6 |
            | 25 | -   | -   | R-7 | -   | R-7 | R-5 |
            | 24 | -   | R-7 | R-6 | -   | R-6 | R-4 |
            | 23 | -   | R-6 | R-5 | -   | R-5 | R-3 |
            | 22 | -   | R-5 | R-4 | -   | R-4 | R-2 |
            | 21 | -   | R-4 | R-3 | R-7 | R-3 | R-1 |
            | 20 | -   | R-3 | -   | R-6 | R-2 | R-0 |
            | 19 | R-7 | -   | -   | R-5 | -   | G-7 |
            | 18 | R-6 | -   | -   | R-4 | -   | G-6 |
            | 17 | R-5 | G-7 | G-7 | R-3 | G-7 | G-5 |
            | 16 | R-4 | G-6 | G-6 | R-2 | G-6 | G-4 |
            | 15 | R-3 | G-5 | G-5 | G-7 | G-5 | G-3 |
            | 14 | G-7 | G-4 | G-4 | G-6 | G-4 | G-2 |
            | 13 | G-6 | G-3 | G-3 | G-5 | G-3 | G-1 |
            | 12 | G-5 | G-2 | G-2 | G-4 | G-2 | G-0 |
            | 11 | G-4 | -   | -   | G-3 | -   | B-7 |
            | 10 | G-3 | -   | -   | G-2 | -   | B-6 |
            | 9  | G-2 | -   | B-7 | B-7 | B-7 | B-5 |
            | 8  | B-7 | B-7 | B-6 | B-6 | B-6 | B-4 |
            | 7  | B-6 | B-6 | B-5 | B-5 | B-5 | B-3 |
            | 6  | B-5 | B-5 | B-4 | B-4 | B-4 | B-2 |
            | 5  | B-4 | B-4 | B-3 | B-3 | B-3 | B-1 |
            | 4  | B-3 | B-3 | B-2 | B-2 | B-2 | B-0 |

            If video.dpi.rgb is set to an order other than 'RGB', swap the
            colors in the table above accordingly. The other GPIOs typically
            used in such displays are as follows, but please refer to your
            boards specific documentation as these may vary:

            | GPIO | Function |
            | 3 | H-Sync |
            | 2 | V-Sync |
            | 1 | Output Enable |
            | 0 | Clock |

            For more information on DPI configuration, please refer to [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    CommandDPIDummy(
        'video.dpi.rgb', command='dpi_output_format', default=0,
        mask=0xf0, valid={
            0: 'RGB',
            1: 'RGB',
            2: 'BGR',
            3: 'GRB',
            4: 'BRG',
        }, doc=_(
            """
            Configures the ordering of RGB data sent to the DPI LCD display.
            Valid values are:

            {valid}

            For more information on DPI configuration, please refer to [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    CommandDPIBool(
        'video.dpi.output.mode', command='dpi_output_format', default=False,
        mask=0x100, doc=_(
            """
            When off (the default), the DPI LCD's output-enable operates in
            "data valid" mode. When on, it operates in "combined sync" mode.

            For more information on DPI configuration, please refer to [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    CommandDPIBool(
        'video.dpi.clock', command='dpi_output_format', default=False,
        mask=0x200, doc=_(
            """
            When off (the default), the DPI LCD's RGB data changes on the
            rising edge, and is stable at the falling edge. Switch this on to
            indicate that RGB data changes on the falling edge and is stable at
            the rising edge.

            For more information on DPI configuration, please refer to [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    CommandDPIBool(
        'video.dpi.hsync.disabled', command='dpi_output_format', default=False,
        mask=0x1000, doc=_(
            """
            Switch this on to disable the horizontal sync of the DPI LCD
            display.

            For more information on DPI configuration, please refer to [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    CommandDPIBool(
        'video.dpi.vsync.disabled', command='dpi_output_format', default=False,
        mask=0x2000, doc=_(
            """
            Switch this on to disable the vertical sync of the DPI LCD display.

            For more information on DPI configuration, please refer to [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    CommandDPIBool(
        'video.dpi.output.disabled', command='dpi_output_format',
        default=False, mask=0x4000, doc=_(
            """
            Switch this on to disable the output-enable of the DPI LCD display.

            For more information on DPI configuration, please refer to [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    CommandDPIBool(
        'video.dpi.hsync.polarity', command='dpi_output_format', default=False,
        mask=0x10000, doc=_(
            """
            Switch this on to invert the polarity of the horizontal sync signal
            for the DPI LCD display. By default this is off, indicating the
            polarity of the signal is the same as that given by the HDMI mode
            driving the display.

            For more information on DPI configuration, please refer to [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    CommandDPIBool(
        'video.dpi.vsync.polarity', command='dpi_output_format', default=False,
        mask=0x20000, doc=_(
            """
            Switch this on to invert the polarity of the vertical sync signal
            for the DPI LCD display. By default this is off, indicating the
            polarity of the signal is the same as that given by the HDMI mode
            driving the display.

            For more information on DPI configuration, please refer to [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    CommandDPIBool(
        'video.dpi.output.polarity', command='dpi_output_format',
        default=False, mask=0x40000, doc=_(
            """
            Switch this on to invert the polarity of the output-enable signal
            for the DPI LCD display. By default this is off, indicating the
            polarity of the signal is the same as that given by the HDMI mode
            driving the display.

            For more information on DPI configuration, please refer to [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    CommandDPIBool(
        'video.dpi.hsync.phase', command='dpi_output_format', default=False,
        mask=0x100000, doc=_(
            """
            Switch this on to invert the phase of the horizontal sync signal
            for the DPI LCD display. By default this is off, indicating the
            signal switches on the "positive" edge (where positive is dictated
            by the polarity of the signal). When on, the signal switches on the
            "negative" edge.

            For more information on DPI configuration, please refer to [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    CommandDPIBool(
        'video.dpi.vsync.phase', command='dpi_output_format', default=False,
        mask=0x200000, doc=_(
            """
            Switch this on to invert the phase of the vertical sync signal
            for the DPI LCD display. By default this is off, indicating the
            signal switches on the "positive" edge (where positive is dictated
            by the polarity of the signal). When on, the signal switches on the
            "negative" edge.

            For more information on DPI configuration, please refer to [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    CommandDPIBool(
        'video.dpi.output.phase', command='dpi_output_format', default=False,
        mask=0x400000, doc=_(
            """
            Switch this on to invert the phase of the output-enable signal for
            the DPI LCD display. By default this is off, indicating the signal
            switches on the "positive" edge (where positive is dictated by the
            polarity of the signal). When on, the signal switches on the
            "negative" edge.

            For more information on DPI configuration, please refer to [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    CommandBool(
        'video.dispmanx.offline', command='dispmanx_offline', default=False,
        doc=_(
            """
            Forces dispmanx composition to be done offline in two offscreen
            framebuffers. This can allow more dispmanx elements to be
            composited, but is slower and may limit screen framerate to
            typically 30fps.
            """)),
    CommandBool(
        'test.enabled', command='test_mode', default=False, doc=_(
            """
            When activated, display a test image and sound during boot (over
            the composite video and analog audio outputs only) for a given
            number of seconds, before continuing to boot the OS as normal. This
            is used as a manufacturing test; the default is off.
            """)),
}

_settings |= {setting for hdmi in (0, 1) for setting in (
    CommandForceIgnore(
        'video.hdmi{}.enabled'.format(hdmi), index=hdmi,
        force='hdmi_force_hotplug', ignore='hdmi_ignore_hotplug', doc=_(
            """
            Switch on to force HDMI output to be used even if no HDMI monitor
            is attached (forces the HDMI hotplug signal to be asserted). Switch
            off to force composite TV output even if an HDMI display is
            detected (ignores the HDMI hotplug signal).
            """)),
    CommandForceIgnore(
        'video.hdmi{}.audio'.format(hdmi), index=hdmi,
        force='hdmi_force_edid_audio', ignore='hdmi_ignore_edid_audio', doc=_(
            """
            Switch on to force the HDMI output to assume that all audio formats
            are supported by the display. Switch off to assume that no audio
            formats are supported by the display (ignoring the EDID [1] data
            given by the attached display).

            [1]: https://en.wikipedia.org/wiki/Extended_Display_Identification_Data
            """)),
    Command(
        'video.hdmi{}.edid.filename'.format(hdmi), index=hdmi,
        default='edid.dat', command='hdmi_edid_filename', doc=_(
            """
            On the Raspberry Pi 4B, you can manually specify the file to read
            for alternate EDID [1] data. Note that this still requires
            video.hdmi.edid.override to be set.

            [1]: https://en.wikipedia.org/wiki/Extended_Display_Identification_Data
            """)),
    CommandHDMIBoost(
        'video.hdmi{}.boost'.format(hdmi), index=hdmi,
        command='config_hdmi_boost', default=5, doc=_(
            """
            Configures the signal strength of the HDMI interface. Must be a
            value between 0 and 11. The default value is 5. Raise this value to
            7 if you are seeing speckling or interference. Very long HDMI
            cables may need 11, but values this high should not be used unless
            absolutely necessary.

            This option is ignored on the Raspberry Pi 4.
            """)),
    CommandDisplayGroup(
        'video.hdmi{}.group'.format(hdmi), index=hdmi, command='hdmi_group',
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
        'video.hdmi{}.mode'.format(hdmi), index=hdmi, command='hdmi_mode',
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
    CommandInt(
        'video.hdmi{}.encoding'.format(hdmi), index=hdmi,
        command='hdmi_pixel_encoding', valid={
            0: 'default; 1 for CEA, 2 for DMT',
            1: 'RGB limited; 16-235',
            2: 'RGB full; 0-255',
            3: 'YCbCr limited; 16-235',
            4: 'YCbCr full; 0-255',
        }, doc=_(
            """
            Defines the pixel encoding mode. By default, it will use the mode
            requested from the EDID, so you shouldn't need to change it. Valid
            values are:

            {valid}
            """)),
    CommandDisplayRotate(
        'video.hdmi{}.rotate'.format(hdmi), index=hdmi,
        command='display_hdmi_rotate', doc=_(
            """
            Controls the rotation of the HDMI output. Valid values are 0 (the
            default), 90, 180, or 270.
            """)),
    CommandDisplayFlip(
        'video.hdmi{}.flip'.format(hdmi), index=hdmi, command='display_hdmi_rotate',
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
        'video.hdmi{}.mode.force'.format(hdmi), index=hdmi,
        command='hdmi_force_mode', doc=_(
            """
            Switching this on forces the mode specified by video.hdmi.group and
            video.hdmi.mode to be used even if they do not appear in the
            enumerated list of modes. This may help if a display seems to be
            ignoring these settings.
            """)),
    CommandDisplayTimings(
        'video.hdmi{}.timings'.format(hdmi), index=hdmi, command='hdmi_timings',
        doc=_(
            """
            An advanced setting that permits the raw HDMI timing values to be
            specified directly for HDMI group 2, mode 87. Please refer to the
            "hdmi_timings" section in [1] for full details.

            [1]: https://www.raspberrypi.org/documentation/configuration/config-txt/video.md
            """)),
    CommandInt(
        'video.hdmi{}.drive'.format(hdmi), index=hdmi, command='hdmi_drive',
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
