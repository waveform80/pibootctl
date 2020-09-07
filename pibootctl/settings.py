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
The :mod:`pibootctl.settings` module defines the template of all settings
stored by the :class:`pibootctl.store.Settings` class. Users of the API never
have any need for this module, but developers wishing to extend the set of
settings will need to modify the :data:`SETTINGS` set.

.. data:: SETTINGS

    A :class:`dict` mapping setting names to :class:`pibootctl.setting.Setting`
    instances which represents the complete set of settings that the
    application handles.
"""

import gettext

from . import setting

_ = gettext.gettext


SETTINGS = {
    setting.OverlayParamBool(
        'i2c.enabled', param='i2c_arm', doc=_(
            """
            Enables the ARM I2C bus on pins 3 (GPIO2) and 5 (GPIO3) of the GPIO
            header (SDA on GPIO2, and SCL on GPIO3).
            """)),
    setting.OverlayParamInt(
        'i2c.baud', param='i2c_arm_baudrate', default=100000, doc=_(
            """
            The baud-rate of the ARM I2C bus.
            """)),
    setting.OverlayParamBool(
        'spi.enabled', param='spi', doc=_(
            """
            Enables the SPI bus on pins 19 (GPIO10), 21 (GPIO9), 23 (GPIO11),
            24 (GPIO8), and 25 (GPIO7) of the GPIO header (MOSI on GPIO10, MISO
            on GPIO9, SCLK on GPIO11, CE0 on GPIO8, and CE1 on GPIO7).
            """)),
    setting.OverlayParamBool(
        'i2s.enabled', param='i2s', doc=_(
            """
            Enables the I2S audio bus on pins 12 (GPIO18), 35 (GPIO19), 38
            (GPIO20), and 40 (GPIO21) on the GPIO header (CLK on GPIO18, FS on
            GPIO19, DIN on GPIO20, and DOUT on GPIO21).
            """)),
    setting.OverlayParamBool(
        'audio.enabled', param='audio', doc=_(
            """
            Enables the ALSA audio interface.
            """)),
    setting.CommandForceIgnore(
        'audio.dither',
        force='enable_audio_dither', ignore='disable_audio_dither', doc=_(
            """
            By default, a 1.0LSB dither is applied to the audio stream if it is
            routed to the analogue audio output. This can create audible
            background "hiss" in some situations, for example when the ALSA
            volume is set to a low level. Audio dither is normally disabled
            when audio samples are larger than 16-bits.

            Set this option to either force the use of dithering for all bit
            depths (on), or disable dithering entirely (off).
            """)),
    setting.CommandInt(
        'audio.depth', command='pwm_sample_bits', default=11, doc=_(
            """
            Adjusts the bit depth of the analogue audio output. The default bit
            depth is 11. Selecting bit depths below 8 will result in
            nonfunctional audio, as settings below 8 result in a PLL frequency
            too low to support. This is generally only useful as a
            demonstration of how bit depth affects quantisation noise.
            """)),
    setting.OverlayParamBool(
        'watchdog.enabled', param='watchdog', doc=_(
            """
            Enables the hardware watchdog.
            """)),
    setting.CommandBool(
        'hat.enabled', command='force_eeprom_read', default=True, doc=_(
            """
            Switch this option off to prevent the firmware from trying to read
            an I2C HAT EEPROM (connected to pins GPIO0 and GPIO1) at powerup.
            """)),
    setting.CommandBoolInv(
        'video.cec.enabled', command='hdmi_ignore_cec', default=True, doc=_(
            """
            Enables CEC (control signals) over the HDMI interface, if supported
            by the connected display. Switch off to pretend CEC is not
            supported at all.
            """)),
    setting.CommandBoolInv(
        'video.cec.init', command='hdmi_ignore_cec_init', default=True, doc=_(
            """
            When off, prevents the initial "active source" message being sent
            during bootup. This prevents CEC-enabled displays from coming out
            of standby and/or channel-switching when starting the Pi.
            """)),
    setting.Command(
        'video.cec.name', command='cec_osd_name', default='Raspberry Pi',
        doc=_(
            """
            The name the Pi (as a CEC device) should provide to the connected
            display; defaults to "Raspberry Pi".
            """)),
    setting.CommandVideoLicense(
        'video.license.mpg2', command='decode_MPG2', doc=_(
            """
            On Pi 3 and earlier models, hardware decoding of MPEG-2 can be
            enabled by purchasing [1] a license key which is locked to the
            serial number of a Raspberry Pi. Multiple license keys (up to 8)
            can be specified to permit switching the SD card between Pis.

            On the Raspberry Pi 4, the hardware codecs for MPEG-2 are
            permanently disabled and cannot be enabled even with a licence key;
            on the Pi 4, thanks to its increased processing power compared to
            earlier models, MPEG-2 and VC-1 can be decoded in software via
            applications such as VLC. Therefore, a hardware codec licence key
            is not needed if you're using a Pi 4.

            [1]: http://swag.raspberrypi.org/collections/software
            """)),
    setting.CommandVideoLicense(
        'video.license.vc1', command='decode_WVC1', doc=_(
            """
            On Pi 3 and earlier models, hardware decoding of VC-1 can be
            enabled by purchasing [1] a license key which is locked to the
            serial number of a Raspberry Pi. Multiple license keys (up to 8)
            can be specified to permit switching the SD card between Pis.

            On the Raspberry Pi 4, the hardware codecs for VC-1 are permanently
            disabled and cannot be enabled even with a licence key; on the Pi
            4, thanks to its increased processing power compared to earlier
            models, MPEG-2 and VC-1 can be decoded in software via applications
            such as VLC. Therefore, a hardware codec licence key is not needed
            if you're using a Pi 4.

            [1]: http://swag.raspberrypi.org/collections/software
            """)),
    setting.CommandBool(
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
    setting.CommandBool(
        'video.hdmi.4kp60', command='hdmi_enable_4kp60', doc=_(
            """
            By default, when connected to a 4K monitor, the Raspberry Pi 4B
            will select a 30hz refresh rate. This setting allows selection of
            60Hz refresh rates.

            Note: enabling this will increase power consumption and increase
            the running temperature of the Pi. It is not possible to use 60Hz
            rates on both micro-HDMI ports simultaneously. Nor is it possible
            to enable the TV-out at the same time.
            """)),
    setting.CommandEDIDIgnore(
        'video.hdmi.edid.ignore', command='hdmi_ignore_edid', doc=_(
            """
            When on, ignores the display's EDID [1] data; useful when your
            display does not have an accurate EDID.

            [1]: https://en.wikipedia.org/wiki/Extended_Display_Identification_Data
            """)),
    setting.CommandBool(
        'video.hdmi.edid.override', command='hdmi_edid_file', doc=_(
            """
            When on, read EDID [1] data from an 'edid.dat' file, located in the
            boot partition, instead of reading it from the monitor. To generate
            an 'edid.dat' file use:

            $ sudo tvservice -d edid.dat

            [1]: https://en.wikipedia.org/wiki/Extended_Display_Identification_Data
            """)),
    setting.CommandBoolInv(
        'video.hdmi.edid.parse', command='disable_fw_kms_setup', default=True,
        doc=_(
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
    setting.CommandInt(
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
    setting.CommandBool(
        'video.hdmi.edid.3d', command='hdmi_force_edid_3d', doc=_(
            """
            When on, pretends that all group 1 (CEA) HDMI modes support 3D even
            when the display's EDID [1] does not indicate this. Defaults to
            off.

            [1]: https://en.wikipedia.org/wiki/Extended_Display_Identification_Data
            """)),
    setting.CommandBool(
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
    setting.CommandBoolInv(
        'video.overscan.enabled', command='disable_overscan', default=True,
        doc=_(
            """
            When enabled (the default), if a group 1 (CEA) HDMI mode is
            selected (automatically or otherwise), the display output will
            include black borders to align the edges of the output with a
            typical TV display.
            """)),
    setting.CommandInt(
        'video.overscan.left', command='overscan_left', doc=_(
            "The width of the left overscan border. Defaults to 0.")),
    setting.CommandInt(
        'video.overscan.right', command='overscan_right', doc=_(
            "The width of the right overscan border. Defaults to 0.")),
    setting.CommandInt(
        'video.overscan.top', command='overscan_top', doc=_(
            "The height of the top overscan border. Defaults to 0.")),
    setting.CommandInt(
        'video.overscan.bottom', command='overscan_bottom', doc=_(
            "The height of the bottom overscan border. Defaults to 0.")),
    setting.CommandBool(
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
    setting.CommandInt(
        'video.framebuffer.max', command='max_framebuffers', default=1,
        doc=_(
            """
            Specifies the maximum number of framebuffers in the video firmware.
            If you have more than one display attached, you need to increase
            this setting to match the number of physical displays.

            When video.firmware.mode is 0 (legacy mode) you get one linux
            framebuffer per display; when it is 1 (FKMS) you still need to set
            this setting to match the number of physical displays but FKMS
            takes over the system and simulates a single framebuffer over those
            multiple displays. [1]

            [1]: https://www.raspberrypi.org/forums/viewtopic.php?t=245789
            """)),
    setting.OverlayKMS(
        'video.firmware.mode', doc=_(
            """
            Specifies the means by which the Linux kernel communicates with the
            video firmware. By default this is 'legacy' (no kernel mode
            setting).

            When this is 'fkms' ("fake" kernel mode setting), the fkms overlay
            is loaded and the Linux kernel talks to the video firmware via the
            mailbox APIs for composition and output.

            When this is 'kms' (kernel mode setting), the full kms overlay is
            loaded and the Linux kernel drives the video hardware registers
            directly, bypassing the firmware. However, this means that
            facilities still running on the firmware (e.g. the camera) no
            longer operate correctly. [1]

            [1]: https://www.raspberrypi.org/forums/viewtopic.php?t=243564
            """)),
    setting.CommandInt(
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
    setting.CommandBoolInv(
        'video.framebuffer.alpha', command='framebuffer_ignore_alpha',
        default=True, doc=_(
            """
            Specifies whether the console framebuffer has an alpha channel.
            It may be necessary to switch this off when video.framebuffer.depth
            is set to 32 bpp.
            """)),
    setting.CommandInt(
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
    setting.CommandInt(
        'video.framebuffer.width', command='framebuffer_width', default=0,
        doc=_(
            """
            Specifies the width of the console framebuffer in pixels. The
            default is the display width minus the total horizontal overscan.
            """)),
    setting.CommandInt(
        'video.framebuffer.width.max', command='max_framebuffer_width',
        default=0, doc=_(
            """
            Specifies the maximum width of the console framebuffer in pixels.
            The default is not to limit the size of the framebuffer.
            """)),
    setting.CommandInt(
        'video.framebuffer.height', command='framebuffer_height', default=0,
        doc=_(
            """
            Specifies the height of the console framebuffer in pixels. The
            default is the display height minus the total vertical overscan.
            """)),
    setting.CommandInt(
        'video.framebuffer.height.max', command='max_framebuffer_height',
        default=0, doc=_(
            """
            Specifies the maximum height of the console framebuffer in pixels.
            The default is not to limit the size of the framebuffer.
            """)),
    setting.CommandTVOut(
        'video.tv.enabled', command='enable_tvout', doc=_(
            """
            On the Pi 4, the composite TV output is disabled by default, as
            driving the TV output slightly impairs the speed of other system
            clocks and slows down the entire computer as a result (older Pi
            models are unaffected).

            Enable this setting to enable TV output on the Pi 4; on older Pi
            models this setting has no effect (composite output is always on
            without performance degradation). Note that it is not possible to
            enable this and the video.hdmi.4kp60 option simultaneously.
            """)),
    setting.CommandInt(
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
    setting.CommandInt(
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
    setting.CommandBoolInv(
        'video.tv.colorburst', command='sdtv_disable_colourburst',
        default=True, doc=_(
            """
            Switch off to disable color-burst [1] on the composite TV output.
            The picture will be displayed in monochrome, but may appear
            sharper.

            [1]: https://en.wikipedia.org/wiki/Colorburst
            """)),
    setting.CommandBoolInv(
        'video.dsi.enabled', command='ignore_lcd', default=True, doc=_(
            """
            By default, an LCD display attached to the DSI connector is used
            when it is detected on the I2C bus. If this setting is disabled,
            this detection phase will be skipped and the LCD display will not
            be used.
            """)),
    setting.CommandBool(
        'video.dsi.default', command='display_default_lcd',
        default=True, doc=_(
            """
            If an LCD display is detected on the DSI connector, it will be used
            as the default display and will show the framebuffer. If this
            setting is disabled, then (usually) the HDMI output will be the
            default. The LCD can still be used by choosing its display number
            from supported applications, e.g. omxplayer.
            """)),
    setting.CommandInt(
        'video.dsi.framerate', command='lcd_framerate', default=60, doc=_(
            """
            Specifies the framerate of an LCD display connected to the DSI
            port. Defaults to 60Hz.
            """)),
    setting.CommandBoolInv(
        'video.dsi.touch.enabled', command='disable_touchscreen', default=True,
        doc=_(
            """
            Enables or disables the touchscreen of the official Raspberry Pi
            LCD display.
            """)),
    setting.CommandDisplayRotate(
        'video.dsi.rotate',
        commands=('display_lcd_rotate', 'display_rotate', 'lcd_rotate'),
        doc=_(
            """
            Controls the rotation of an LCD display connected to the DSI port.
            Valid values are 0 (the default), 90, 180, or 270.
            """)),
    setting.CommandDisplayFlip(
        'video.dsi.flip',
        commands=('display_lcd_rotate', 'display_rotate', 'lcd_rotate'),
        doc=_(
            """
            Controls the reflection (flipping) of an LCD display connected to
            the DSI port. Valid values are:

            {valid}
            """)),
    setting.CommandBool(
        'video.dpi.enabled', command='enable_dpi_lcd', doc=_(
            """
            Enables LCD displays attached to the DPI GPIOs. This is to allow
            the use of third-party LCD displays using the parallel display
            interface [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    setting.CommandDisplayGroup(
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
    setting.CommandDisplayMode(
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

            Note that there is a pixel clock limit [1]. The highest supported
            mode is 1920x1200 at 60Hz which reduced blanking.

            [1]: https://www.raspberrypi.org/forums/viewtopic.php?f=26&t=20155&p=195443#p195443
            """)),
    setting.CommandDisplayTimings(
        'video.dpi.timings', command='dpi_timings', doc=_(
            """
            An advanced setting that permits the raw timing values to be
            specified directly for DPI group 2, mode 87. Please refer to the
            "dpi_timings" section in [1] for full details.

            [1]: https://www.raspberrypi.org/documentation/configuration/config-txt/video.md
            """)),
    setting.CommandDPIOutput(
        'video.dpi.format', command='dpi_output_format', default=1,
        mask=0xf, valid={
            1: '9-bit RGB666; unsupported',
            2: '16-bit RGB565; config 1',
            3: '16-bit RGB565; config 2',
            4: '16-bit RGB565; config 3',
            5: '18-bit RGB666; config 1',
            6: '18-bit RGB666; config 2',
            7: '24-bit RGB888',
        }, dummies={
            '.rgb',
            '.clock',
            '.hsync.disabled',
            '.hsync.polarity',
            '.hsync.phase',
            '.vsync.disabled',
            '.vsync.polarity',
            '.vsync.phase',
            '.output.mode',
            '.output.disabled',
            '.output.polarity',
            '.output.phase',
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
            board's specific documentation as these may vary:

            | GPIO | Function |
            | 3 | H-Sync |
            | 2 | V-Sync |
            | 1 | Output Enable |
            | 0 | Clock |

            For more information on DPI configuration, please refer to [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    setting.CommandDPIDummy(
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
    setting.CommandDPIDummy(
        'video.dpi.output.mode', command='dpi_output_format', default=False,
        mask=0x100, doc=_(
            """
            When off (the default), the DPI LCD's output-enable operates in
            "data valid" mode. When on, it operates in "combined sync" mode.

            For more information on DPI configuration, please refer to [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    setting.CommandDPIDummy(
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
    setting.CommandDPIDummy(
        'video.dpi.hsync.disabled', command='dpi_output_format', default=False,
        mask=0x1000, doc=_(
            """
            Switch this on to disable the horizontal sync of the DPI LCD
            display.

            For more information on DPI configuration, please refer to [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    setting.CommandDPIDummy(
        'video.dpi.vsync.disabled', command='dpi_output_format', default=False,
        mask=0x2000, doc=_(
            """
            Switch this on to disable the vertical sync of the DPI LCD display.

            For more information on DPI configuration, please refer to [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    setting.CommandDPIDummy(
        'video.dpi.output.disabled', command='dpi_output_format',
        default=False, mask=0x4000, doc=_(
            """
            Switch this on to disable the output-enable of the DPI LCD display.

            For more information on DPI configuration, please refer to [1].

            [1]: https://www.raspberrypi.org/documentation/hardware/raspberrypi/dpi/README.md
            """)),
    setting.CommandDPIDummy(
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
    setting.CommandDPIDummy(
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
    setting.CommandDPIDummy(
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
    setting.CommandDPIDummy(
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
    setting.CommandDPIDummy(
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
    setting.CommandDPIDummy(
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
    setting.CommandBool(
        'video.dispmanx.offline', command='dispmanx_offline', default=False,
        doc=_(
            """
            Forces dispmanx composition to be done offline in two offscreen
            framebuffers. This can allow more dispmanx elements to be
            composited, but is slower and may limit screen framerate to
            typically 30fps.
            """)),
    setting.Command(
        'boot.prefix', command='os_prefix', default='', doc=_(
            """
            The string to prefix all filenames (e.g. boot.kernel.filename,
            boot.devicetree.filename, etc.) with.

            Note that this is literally a prefix, not a directory. For example,
            if boot.prefix is "foo-" and boot.kernel.filename is "kernel.img"
            then "foo-kernel.img" will be used as the kernel's filename. Hence,
            if you wish to specify a directory, make sure to end the value with
            "/".
            """)),
    setting.CommandBool(
        'boot.test.enabled', command='test_mode', default=False, doc=_(
            """
            When activated, display a test image and sound during boot (over
            the composite video and analog audio outputs only) for a given
            number of seconds, before continuing to boot the OS as normal. This
            is used as a manufacturing test; the default is off.
            """)),
    setting.CommandKernelAddress(
        'boot.kernel.address', commands=('kernel_address', 'kernel_old'),
        default=None, doc=_(
            """
            Specifies the address at which the bootloader should place the
            kernel (typically Linux). Defaults to 0x80000 when boot.arm.64bit
            is enabled, or 0x8000 otherwise.
            """)),
    setting.CommandKernel64(
        'boot.kernel.64bit', commands=('arm_64bit', 'arm_control'), doc=_(
            """
            Controls whether the bootloader assumes that a 64-bit kernel is to
            be loaded. Note that this setting affects the defaults for
            boot.kernel.filename and boot.kernel.address.
            """)),
    setting.CommandKernelFilename(
        'boot.kernel.filename', command='kernel', doc=_(
            """
            Specifies the kernel that the bootloader should load and execute.
            The defaults for the various Pi models are:

            | Models | Default |
            | Pi 1, Pi Zero, Compute Module | kernel.img |
            | Pi 2, Pi 3, Pi 3+, Compute Module 3+ | kernel7.img |
            | Pi 4 | kernel7l.img |

            However, if boot.kernel.64bit is on (only valid on the Pi 2 rev 1.2
            and above), the default is 'kernel8.img'.
            """)),
    setting.CommandKernelCmdline(
        # TODO What about cmdline content?
        'boot.kernel.cmdline', command='cmdline', default='cmdline.txt', doc=_(
            """
            Specifies the alternative filename on the boot partition from which
            to read the kernel command line string.
            """)),
    setting.CommandBoolInv(
        'boot.kernel.atags', command='disable_commandline_tags', default=True,
        doc=_(
            """
            Switch this off to stop the bootloader from filling in ATAGS
            (memory from 0x100) before launching the kernel.
            """)),
    setting.CommandDeviceTreeAddress(
        'boot.devicetree.address', command='device_tree_address', default=0,
        doc=_(
            """
            Used to override the address where the bootloader loads the device
            tree (not dt-blob). By default the firmware will choose a suitable
            place.
            """)),
    setting.CommandInt(
        'boot.devicetree.limit', command='device_tree_end', doc=_(
            """
            Sets an (exclusive) limit to the loaded device tree. By default the
            device tree can grow to the end of usable memory, which is almost
            certainly what is required.
            """)),
    setting.CommandDeviceTree(
        'boot.devicetree.filename', command='device_tree', default='', doc=_(
            """
            Specifies the particular device tree that the bootloader should
            load and pass to the kernel.

            The default is for the bootloader to automatically select a device
            tree for the platform that it is running on (it is unusual to
            require a specific device tree).
            """)),
    setting.CommandFirmwareDebug(
        'boot.debug.enabled',
        commands=('start_debug', 'start_file', 'fixup_file'), doc=_(
            """
            Enables loading the debugging firmware. This implies that
            start_db.elf (or start4db.elf) will be loaded as the GPU firmware
            rather than the default start.elf (or start4.elf). Note that the
            debugging firmware incorporates the camera firmware so this will
            implicitly switch camera.enabled on if it is not already.

            The debugging firmware performs considerably more logging than the
            default firmware but at a performance cost, ergo it should only be
            used when required.
            """)),
    # TODO uart_2ndstage is only valid in config.txt
    setting.CommandBool(
        'boot.debug.serial', command='uart_2ndstage', doc=_(
            """
            Setting boot.debug.serial to on causes the second-stage loader
            (bootcode.bin on devices prior to the Raspberry Pi 4, or the boot
            code in the EEPROM for Raspberry Pi 4 devices) and the main
            firmware (start*.elf) to output diagnostic information to UART0.

            Be aware that output is likely to interfere with Bluetooth
            operation unless it is disabled (bluetooth.enabled is off) or
            switched to the other UART (serial.uart is 0), and if the UART is
            accessed simultaneously to output from Linux then data loss can
            occur leading to corrupted output. This feature should only be
            required when trying to diagnose an early boot loading problem.
            """)),
    setting.CommandTotalMem(
        'boot.mem', command='total_mem',
        doc=_(
            """
            This parameter, which is primarily intended for debugging, can be
            used to force a Raspberry Pi to limit its memory capacity: specify
            the total amount of RAM, in megabytes, you wish the Pi to use. For
            example, to make a 4GB Raspberry Pi 4B behave as though it were a
            1GB model, use 1024.

            This value will be clamped between a minimum of 128MB, and a
            maximum of the total memory installed on the board.
            """)),
    setting.CommandFirmwareFilename(
        'boot.firmware.filename', command='start_file', doc=_(
            """
            The filename of the GPU firmware that the bootloader should load
            The GPU firmware is also the tertiary bootloader which is
            responsible for launching the kernel (specified by
            boot.kernel.filename).

            Usually there is no need to modify this setting directly; if you
            require the camera firmware simply set camera.enabled. However, if
            you require the specialized debugging (start_db.elf) or lightweight
            (start_cd.elf) firmwares you may need to specify them manually
            here.

            Please note that if you manually specify a GPU firmware, you should
            also manually specify an appropriate boot.firmware.fixup file.
            """)),
    setting.CommandFirmwareFixup(
        'boot.firmware.fixup', command='fixup_file', doc=_(
            """
            The filename of the fixup file for the GPU firmware specified in
            boot.firmware.filename.

            Usually there is no need to modify this setting directly; if you
            require the camera firmware simply set camera.enabled. However, if
            you require the specialized debugging (start_db.elf) or lightweight
            (start_cd.elf) firmwares you may need to specify them manually
            here.
            """)),
    setting.CommandRamFSAddress(
        'boot.initramfs.address', commands=('ramfsaddr', 'initramfs'), doc=_(
            """
            The address at which the bootloader should place the initramfs. By
            default this is 0, which causes the bootloader to place the
            initramfs immediately after the kernel in memory.
            """)),
    setting.CommandRamFSFilename(
        'boot.initramfs.filename', commands=('ramfsfile', 'initramfs'),
        default='', doc=_(
            """
            The filename of the (optional) initramfs that the bootloader should
            load and pass to the kernel. By default this is unset and no
            initramfs is loaded. Sufficiently new firmwares support the loading
            of multiple ramfs files; specify a list of filenames in this case.
            All loaded files are concatenated in memory and treated as a single
            ramfs blob.

            Note: the bootloader has a strict line-length of 80 characters. If
            many ramfs files are specified, it's possible to exceed this limit.
            """)),
    # TODO bootcode_delay is only valid in config.txt
    setting.CommandInt(
        'boot.delay.1', command='bootcode_delay', default=0, doc=_(
            """
            Specifies the number of seconds to delay during "bootcode.bin"
            (actually the second stage bootloader, despite the setting's name,
            but the first configurable by the boot configuration).

            This is particularly useful to insert a delay before reading the
            EDID of the monitor, for example if the Pi and monitor are powered
            from the same source, but the monitor takes longer to start up than
            the Pi. Try setting this value if the display detection is wrong on
            initial boot, but is correct if you soft-reboot the Pi without
            removing power from the monitor.
            """)),
    setting.CommandBootDelay2(
        'boot.delay.2', commands=('boot_delay', 'boot_delay_ms'), default=0,
        doc=_(
            """
            Specifies the number of seconds to delay during "start.elf"
            (actually the third stage bootloader prior to the kernel itself).

            This can be useful if your SD card needs a while to get ready
            before Linux is able to boot from it.
            """)),
    setting.CommandBoolInv(
        'boot.splash.enabled', command='disable_splash', default=True, doc=_(
            """
            If this is switched off, the rainbow splash screen will not be
            shown on boot.
            """)),
    setting.CommandSerialEnabled(
        'serial.enabled', command='enable_uart', doc=_(
            """
            Enable the primary/console UART (ttyS0 on a Pi 3, ttyAMA0
            otherwise, unless swapped with an overlay such as miniuart-bt). If
            the primary UART is UART0 (the PL011, or ttyAMA0 in Linux) then
            this setting defaults to on, otherwise it defaults to off.

            This is because, when the primary UART is UART1 (the mini-UART, or
            ttyS0 in Linux), it is necessary to stop the core VPU frequency
            from changing which would make the UART unusable. Under these
            circumstances, activating serial.enabled implies
            gpu.core.frequency.max=250 (unless cpu.turbo.force is on). In some
            cases this is a performance hit, so it is off by default.

            More details on UARTs can be found at [1].

            [1]: https://www.raspberrypi.org/documentation/configuration/uart.md
            """)),
    setting.CommandInt(
        'serial.baud', command='init_uart_baud', default=115200, doc=_(
            """
            Sets the initial baud rate for the primary UART.
            """)),
    setting.CommandInt(
        'serial.clock', command='init_uart_clock', default=48000000, doc=_(
            """
            Sets the initial UART clock frequency.

            Note that this clock only applies to UART0 (the PL011, or
            /dev/ttyAMA0 in Linux), and that the maximum baud-rate for the UART
            is limited to 1/16th of the clock. The default UART on the Pi 3 and
            Pi Zero is UART1 (the mini-UART, or ttyS0 in Linux), and its clock
            is the core VPU clock: at least 250MHz.
            """)),
    setting.OverlaySerialUART(
        'serial.uart', doc=_(
            """
            Controls whether the primary UART is UART1 (the mini-UART, or ttyS0
            in Linux) or UART0 (the PL011, ttyAMA0 in Linux).

            By default, on Raspberry Pis equipped with the wireless/Bluetooth
            module (Raspberry Pi 3 and later, and the Raspberry Pi Zero W),
            UART0 is connected to the Bluetooth module, while UART1 is used as
            the primary UART and may have a Linux console on it. On all other
            models, UART0 is used as the primary UART.

            More details on UARTs can be found at [1].

            [1]: https://www.raspberrypi.org/documentation/configuration/uart.md
            """)),
    setting.OverlayBluetoothEnabled(
        'bluetooth.enabled', doc=_(
            """
            Controls whether the Bluetooth module (Raspberry Pi 3 and later,
            and the Raspberry Pi Zero W), is enabled (which it is by default).

            Note that disabling the module can affect the default state of
            serial.enabled and serial.uart.
            """)),
    setting.OverlayDWC2(
        'usb.dwc2.enabled', doc=_(
            """
            Selects the USB controller driver for the DWC2 driven USB port.

            On the Raspberry Pi 4 this is the USB-C (power) port. On the A+ and
            3A+ this is the single USB type A ("full size") port. On the Pi
            Zero this is the micro-USB port labelled "USB". On all other
            models, this USB port is not (directly) accessible as it sits
            behind the combined USB hub and ethernet controller.

            On the Raspberry Pi Zero, this setting defaults to enabled meaning
            the "dwc2" driver is selected permitting dual-role (gadget)
            operation (depending on the setting of usb.dwc2.mode). On all other
            models, this setting defaults to disabled which results in the
            "dwc-otg" driver (which supports fast interrupts) being used.
            """)),
    setting.OverlayParamStr(
        'usb.dwc2.mode', overlay='dwc2', param='dr_mode', default='otg',
        valid={
            'host':       'Host mode always',
            'peripheral': 'Device mode always',
            'otg':        'Dual-role host/device',
        }, doc=_(
            """
            Selects the dual-role mode of the DWC2 USB port, when
            usb.dwc2.enabled is true.

            This can be one of:

            {valid}
            """)),
    setting.CommandFirmwareCamera(
        'camera.enabled',
        commands=('start_x', 'start_debug', 'start_file', 'fixup_file'),
        doc=_(
            """
            Enables loading the Pi camera module firmware. This implies that
            start_x.elf (or start4x.elf) will be loaded as the GPU firmware
            rather than the default start.elf (and the corresponding fixup
            file).

            Note: with the camera firmware loaded, gpu.mem must be 64Mb or
            larger (128Mb is recommended for most purposes; 256Mb may be
            required for complex processing pipelines).
            """)),
    setting.CommandBoolInv(
        'camera.led.enabled', command='disable_camera_led', default=True,
        doc=_(
            """
            Switch this off to disable the red power LED on the Pi Camera
            Module version 1. This is useful for preventing reflections when
            the camera is facing a window, for example.
            """)),
    setting.CommandCPUL2Cache(
        'cpu.l2.enabled', command='disable_l2cache', doc=_(
            """
            Switching this off disables the CPU's access to the GPU's L2 cache
            and requires a corresponding L2 disabled kernel. Default value on
            the Pi Zero and Pi 1 is on. On all other models (currently Pi 2, Pi
            3, Pi 3+, and Pi 4), the ARMs have their own L2 cache and therefore
            the default is off.

            The standard Pi kernel.img and kernel7.img builds reflect this
            difference in cache setting.
            """)),
    setting.CommandBool(
        'cpu.gic.enabled', command='enable_gic', default=True, doc=_(
            """
            On the Raspberry Pi 4B, if this setting is switched off then
            interrupts will be routed to the ARM cores using the legacy
            interrupt controller, rather than via the GIC-400.
            """)),
    setting.CommandBool(
        'cpu.turbo.force', command='force_turbo', default=False, doc=_(
            """
            Forces turbo mode frequencies even when the ARM cores are not busy.
            Enabling this may set the warranty bit if certain overvolt.*
            settings are also set.
            """)),
    setting.CommandInt(
        'cpu.turbo.initial', command='initial_turbo', default=0, doc=_(
            """
            Enables turbo mode from boot for the given number of seconds, or
            until cpufreq sets a frequency. For more information see [1]. The
            maximum value is 60 seconds.

            [1]: https://www.raspberrypi.org/forums/viewtopic.php?f=29&t=6201&start=425#p180099
            """)),
    setting.CommandCPUFreqMax(
        'cpu.frequency.max', command='arm_freq', doc=_(
            """
            The maximum frequency of the ARM CPU in MHz. The default values for
            various models are as follows:

            | Model | Frequency (MHz) |
            | Pi 0 | 1000 |
            | Pi 1 | 700 |
            | Pi 2 | 900 |
            | Pi 3 | 1200 |
            | Pi 3+ | 1400 |
            | Pi 4 | 1500 |
            """)),
    setting.CommandCPUFreqMin(
        'cpu.frequency.min', command='arm_freq_min', doc=_(
            """
            The minimum value of cpu.frequency.max used for dynamic frequency
            clocking.
            """)),
    setting.CommandCoreFreqMax(
        'gpu.core.frequency.max', commands=('core_freq', 'gpu_freq'), doc=_(
            """
            Frequency of the GPU processor core in MHz. Influences CPU
            performance because it drives the L2 cache and memory bus. The
            default values for various models are as follows:

            | Model | Frequency (Mhz) |
            | Pi 0 | 400 |
            | Pi 1 | 250 |
            | Pi 2 | 250 |
            | Pi 3 | 400 |
            | Pi 3+ | 400 |
            | Pi 4 | 500 |

            600 is the only other accepted value. The L2 cache benefits only Pi
            Zero / Pi Zero W / Pi 1, there is a small benefit for SDRAM on Pi 2
            / Pi 3 and Pi 4B.
            """)),
    setting.CommandCoreFreqMin(
        'gpu.core.frequency.min', commands=('core_freq_min', 'gpu_freq_min'),
        doc=_(
            """
            Minimum value of gpu.frequency.core.max used for dynamic frequency
            clocking. The default value is 250Mhz. On Pi 4B the default is
            275Mhz when video.hdmi.mode.4kp60 is on.
            """)),
    setting.CommandGPUFreqMax(
        'gpu.h264.frequency.max', commands=('h264_freq', 'gpu_freq'), doc=_(
            """
            Frequency of the GPU's hardware video block in MHz. The default
            values for various models are as follows:

            | Model | Frequency (Mhz) |
            | Pi 0 | 400 |
            | Pi 1 | 250 |
            | Pi 2 | 250 |
            | Pi 3 | 300 |
            | Pi 3+ | 300 |
            | Pi 4 | 500 |

            600Mhz is the only other accepted value.
            """)),
    setting.CommandGPUFreqMin(
        'gpu.h264.frequency.min', commands=('h264_freq_min', 'gpu_freq_min'),
        doc=_(
            """
            Minimum value of gpu.frequency.h264.max used for dynamic frequency
            clocking. The default value is 250, or 500 on Pi 4B.
            """)),
    setting.CommandGPUFreqMax(
        'gpu.isp.frequency.max', commands=('isp_freq', 'gpu_freq'), doc=_(
            """
            Frequency of the GPU's image sensor pipeline block in MHz. The
            default values for various models are as follows:

            | Model | Frequency (Mhz) |
            | Pi 0 | 400 |
            | Pi 1 | 250 |
            | Pi 2 | 250 |
            | Pi 3 | 300 |
            | Pi 3+ | 300 |
            | Pi 4 | 500 |

            600Mhz is the only other accepted value.
            """)),
    setting.CommandGPUFreqMin(
        'gpu.isp.frequency.min', commands=('isp_freq_min', 'gpu_freq_min'),
        doc=_(
            """
            Minimum value of gpu.frequency.isp.max used for dynamic frequency
            clocking. The default value is 250, or 500 on Pi 4B.
            """)),
    setting.CommandGPUFreqMax(
        'gpu.v3d.frequency.max', commands=('v3d_freq', 'gpu_freq'), doc=_(
            """
            Frequency of the GPU's 3D block in MHz. The default values for
            various models are as follows:

            | Model | Frequency (Mhz) |
            | Pi 0 | 400 |
            | Pi 1 | 250 |
            | Pi 2 | 250 |
            | Pi 3 | 300 |
            | Pi 3+ | 300 |
            | Pi 4 | 500 |

            600Mhz is the only other accepted value.
            """)),
    setting.CommandGPUFreqMin(
        'gpu.v3d.frequency.min', commands=('v3d_freq_min', 'gpu_freq_min'),
        doc=_(
            """
            Minimum value of gpu.frequency.v3d.max used for dynamic frequency
            clocking. The default value is 250, or 500 on Pi 4B.
            """)),
    setting.CommandGPUMem(
        'gpu.mem',
        commands=('gpu_mem', 'gpu_mem_256', 'gpu_mem_512', 'gpu_mem_1024'),
        doc=_(
            """
            Specifies how much memory, in megabytes, to reserve for the
            exclusive use of the GPU: the remaining memory is allocated to the
            CPU. For models with less than 1GB of memory, the default is 64;
            for model with 1GB or more of memory the default is 76. To ensure
            the best performance of Linux, you should set this to the lowest
            possible value. If a particular graphics feature is not working
            correctly, try increasing the value, being mindful of the
            recommended maximums shown below. There is no performance advantage
            from specifying values larger than is necessary.

            The maximum values are as follows:

            | Total RAM | Maximum |
            | 256MB | 128 |
            | 512MB | 384 |
            | 1GB+ | 512 |

            The minimum value is 16, however this disables certain GPU
            features.

            On the Raspberry Pi 4 the 3D component of the GPU has its own
            memory management unit (MMU), and does not use memory from this
            allocation. Instead memory is allocated dynamically within Linux.
            This may allow a smaller value to be specified for on the Pi 4,
            compared to previous models.
            """)),
}

SETTINGS |= {spec for gpio in range(28) for spec in (
    setting.CommandGPIOMode(
        'gpio{}.mode'.format(gpio), index=gpio, command='gpio', doc=_(
            """
            Allows GPIO pins to be set to specific modes at boot time in a way
            that would previously have needed a custom device-tree blob. The
            valid modes are:

            {valid}

            The associated gpio{index}.state can be used to set pulls (for
            inputs) or drives (for outputs).

            GPIO changes made through this mechanism do not have any direct
            effect on the kernel; they don't cause GPIO pins to be exported to
            the sysfs interface, and they can be overridden by pinctrl entries
            in the Device Tree as well as utilities like raspi-gpio.
            """)),
    setting.CommandGPIOState(
        'gpio{}.state'.format(gpio), index=gpio, command='gpio', doc=_(
            """
            Allows GPIO pins to be set to specific modes at boot time in a way
            that would previously have needed a custom device-tree blob. The
            valid states are:

            {valid}

            Pulls are only valid if the corresponding gpio{index}.mode is set
            to "in". Likewise drives are only valid when the corresponding
            mode is "out".

            GPIO changes made through this mechanism do not have any direct
            effect on the kernel; they don't cause GPIO pins to be exported to
            the sysfs interface, and they can be overridden by pinctrl entries
            in the Device Tree as well as utilities like raspi-gpio.
            """)),
)}

SETTINGS |= {spec for hdmi in (0, 1) for spec in (
    setting.CommandForceIgnore(
        'video.hdmi{}.enabled'.format(hdmi), index=hdmi,
        force='hdmi_force_hotplug', ignore='hdmi_ignore_hotplug', doc=_(
            """
            Switch on to force HDMI output to be used even if no HDMI monitor
            is attached (forces the HDMI hotplug signal to be asserted). Switch
            off to force composite TV output even if an HDMI display is
            detected (ignores the HDMI hotplug signal).
            """)),
    setting.CommandForceIgnore(
        'video.hdmi{}.audio'.format(hdmi), index=hdmi,
        force='hdmi_force_edid_audio', ignore='hdmi_ignore_edid_audio', doc=_(
            """
            Switch on to force the HDMI output to assume that all audio formats
            are supported by the display. Switch off to assume that no audio
            formats are supported by the display (ignoring the EDID [1] data
            given by the attached display).

            [1]: https://en.wikipedia.org/wiki/Extended_Display_Identification_Data
            """)),
    setting.CommandIncludedFile(
        'video.hdmi{}.edid.filename'.format(hdmi), index=hdmi,
        default='edid.dat', command='hdmi_edid_filename', doc=_(
            """
            On the Raspberry Pi 4B, you can manually specify the file to read
            for alternate EDID [1] data. Note that this still requires
            video.hdmi.edid.override to be set.

            [1]: https://en.wikipedia.org/wiki/Extended_Display_Identification_Data
            """)),
    setting.CommandHDMIBoost(
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
    setting.CommandDisplayGroup(
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
    setting.CommandDisplayMode(
        'video.hdmi{}.mode'.format(hdmi), index=hdmi, command='hdmi_mode',
        doc=_(
            """
            Defines which mode will be used on the HDMI output. This defaults
            to 0 which indicates it should be automatically determined from the
            EDID sent by the connected display. If video.hdmi{index}.group is
            set to 1 (CEA), this must be one of the following values:

            {valid_cea}

            Pixel doubling and quadrupling indicates a higher clock rate, with
            each pixel repeated two or four times respectively.

            The following values are valid if video.hdmi.group is set to 2
            (DMT):

            {valid_dmt}

            Note that there is a pixel clock limit [1]. The highest supported
            mode on models prior to the Raspberry Pi 4 is 1920x1200 at 60Hz
            with reduced blanking, whilst the Raspberry Pi 4 can support up to
            4096x2160 (known as 4k) at 60Hz. Also note that if you are using
            both HDMI ports of the Raspberry Pi 4 for 4k output, then you are
            limited to 30Hz on both.

            [1]: https://www.raspberrypi.org/forums/viewtopic.php?f=26&t=20155&p=195443#p195443
            """)),
    setting.CommandInt(
        'video.hdmi{}.encoding'.format(hdmi), index=hdmi,
        command='hdmi_pixel_encoding', valid={
            0: 'auto; 1 for CEA, 2 for DMT',
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
    setting.CommandDisplayRotate(
        'video.hdmi{}.rotate'.format(hdmi), index=hdmi,
        commands=('display_hdmi_rotate', 'display_rotate'), doc=_(
            """
            Controls the rotation of the HDMI output. Valid values are 0 (the
            default), 90, 180, or 270.
            """)),
    setting.CommandDisplayFlip(
        'video.hdmi{}.flip'.format(hdmi), index=hdmi,
        commands=('display_hdmi_rotate', 'display_rotate'), doc=_(
            """
            Controls the reflection (flipping) of the HDMI output. Valid values
            are:

            {valid}
            """)),
    setting.CommandBool(
        'video.hdmi{}.mode.force'.format(hdmi), index=hdmi,
        command='hdmi_force_mode', doc=_(
            """
            Switching this on forces the mode specified by video.hdmi.group and
            video.hdmi.mode to be used even if they do not appear in the
            enumerated list of modes. This may help if a display seems to be
            ignoring these settings.
            """)),
    setting.CommandDisplayTimings(
        'video.hdmi{}.timings'.format(hdmi), index=hdmi, command='hdmi_timings',
        doc=_(
            """
            An advanced setting that permits the raw HDMI timing values to be
            specified directly for HDMI group 2, mode 87. Please refer to the
            "hdmi_timings" section in [1] for full details.

            [1]: https://www.raspberrypi.org/documentation/configuration/config-txt/video.md
            """)),
    setting.CommandInt(
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

SETTINGS = {spec.name: spec for spec in SETTINGS}
