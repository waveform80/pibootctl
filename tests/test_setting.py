# Copyright (c) 2020 Canonical Ltd.
# Copyright (c) 2020 Dave Jones <dave@waveform.org.uk>
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

from unittest import mock
from itertools import chain
from operator import attrgetter

import pytest

from pibootctl.userstr import UserStr
from pibootctl.store import Settings
from pibootctl.parser import *
from pibootctl.setting import *


cond_all = BootConditions()


def make_settings(*specs):
    return Settings({spec.name: spec for spec in specs})


@pytest.fixture()
def fw_settings(request):
    return make_settings(
        CommandFirmwareCamera(
            'camera.enabled', commands=('start_x', 'start_debug')),
        CommandFirmwareDebug(
            'boot.debug.enabled', commands=('start_debug', 'start_file', 'fixup_file')),
        CommandGPUMem(
            'gpu.mem', default=64, commands=('gpu_mem', 'gpu_mem_256',
                                             'gpu_mem_512', 'gpu_mem_1024')),
        CommandFirmwareFilename('boot.firmware.filename', command='start_file'),
        CommandFirmwareFixup('boot.firmware.fixup', command='fixup_file'))


def test_setting_init():
    s = Setting('foo.bar', default='baz')

    assert s.update('quux') == 'quux'
    assert repr(s) == "<Setting name='foo.bar' default='baz' value='baz' modified=False>"
    with pytest.raises(NotImplementedError):
        s.extract(None)
    with pytest.raises(NotImplementedError):
        s.output()
    with pytest.raises(NotImplementedError):
        s.key


def test_setting_override():
    s = Setting('foo.bar', default='baz')

    with s._override('quux'):
        assert s.value == 'quux'
    assert s.value == 'baz'


def test_overlay_init():
    o = Overlay('sense.enabled', overlay='sensehat')

    assert o.overlay == 'sensehat'
    assert o.key == ('overlays', 'sensehat')
    assert o.update(False) is False


def test_overlay_extract():
    o = Overlay('sense.enabled', overlay='sensehat')

    config = [BootParam('config.txt', 3, cond_all, 'base', 'i2c_arm', 'on')]
    assert list(o.extract(config)) == []
    config = [
        BootOverlay('config.txt', 3, cond_all, 'disable-bt'),
        BootOverlay('config.txt', 4, cond_all, 'sensehat')]
    assert list(o.extract(config)) == [(config[1], True)]


def test_overlay_output():
    o = Overlay('sense.enabled', overlay='sensehat')

    assert list(o.output()) == []
    o._value = True
    assert list(o.output()) == ['dtoverlay=sensehat']


def test_param_init():
    p = OverlayParamStr('i2c.enabled', param='i2c_arm')

    assert p.overlay == 'base'
    assert p.param == 'i2c_arm'
    assert p.key == ('overlays', '', 'i2c_arm')
    assert p.update('foo') == 'foo'


def test_param_extract():
    p = OverlayParamStr('i2c.enabled', param='i2c_arm')

    config = [
        BootOverlay('config.txt', 1, cond_all, 'sensehat'),
        BootOverlay('config.txt', 2, cond_all, 'base'),
        BootParam('config.txt', 3, cond_all, 'base', 'i2c_arm', 'on'),
    ]
    assert list(p.extract(config)) == [
        (config[1], None),
        (config[2], 'on'),
    ]


def test_param_output():
    p = OverlayParamStr('i2c.enabled', param='i2c_arm')

    assert list(p.output()) == []
    p._value = 'on'
    assert list(p.output()) == ['dtparam=i2c_arm=on']


def test_param_validate():
    p = OverlayParamStr('usb.dwc2.mode', overlay='dwc2', param='dr_mode', default='otg', valid={
        'host': 'Host mode always',
        'peripheral': 'Device mode always',
        'otg': 'Host/device mode',
    })

    p._value = 'host'
    p.validate()
    assert p.hint == 'Host mode always'
    p._value = 'foo'
    with pytest.raises(ValueError):
        p.validate()


def test_int_param_init():
    p = OverlayParamInt('i2c.baud', param='i2c_baud')

    assert p.update('100000') == 100000
    assert p.update('0x1c200') == 115200


def test_int_param_extract():
    p = OverlayParamInt('i2c.baud', param='i2c_baud')

    config = [
        BootOverlay('config.txt', 1, cond_all, 'sensehat'),
        BootOverlay('config.txt', 2, cond_all, 'base'),
        BootParam('config.txt', 3, cond_all, 'base', 'i2c_baud', '100000'),
        BootParam('config.txt', 3, cond_all, 'base', 'i2c_baud', 'foo'),
    ]
    with warnings.catch_warnings(record=True) as w:
        assert list(p.extract(config)) == [
            (config[1], None),
            (config[2], 100000),
            (config[3], None),
        ]
        assert len(w) == 1
        assert issubclass(w[0].category, ParseWarning)


def test_int_param_validate():
    p = OverlayParamInt('draws.ch4.gain', overlay='draws', param='draws_adc_ch4_gain', valid={
        0: '+/- 6.144V',
        1: '+/- 4.096V',
        2: '+/- 2.048V',
        3: '+/- 1.024V',
        4: '+/- 0.512V',
        5: '+/- 0.256V',
        6: '+/- 0.256V',
        7: '+/- 0.256V',
    })

    p._value = 4
    p.validate()
    assert p.hint == '+/- 0.512V'
    p._value = 8
    with pytest.raises(ValueError):
        p.validate()


def test_bool_param_init():
    p = OverlayParamBool('i2c.enabled', param='i2c_arm')

    assert p.update(UserStr('on')) is True
    assert p.update(1) is True


def test_bool_param_extract():
    p = OverlayParamBool('i2c.enabled', param='i2c_arm')

    config = [
        BootOverlay('config.txt', 1, cond_all, 'sensehat'),
        BootOverlay('config.txt', 2, cond_all, 'base'),
        BootParam('config.txt', 3, cond_all, 'base', 'i2c_arm', 'on'),
    ]
    assert list(p.extract(config)) == [
        (config[1], None),
        (config[2], True),
    ]


def test_bool_param_output():
    p = OverlayParamBool('i2c.enabled', param='i2c_arm')

    assert list(p.output()) == []
    p._value = True
    assert list(p.output()) == ['dtparam=i2c_arm=on']


def test_command_init():
    c = CommandStr('video.cec.name', commands=('foo', 'bar'), default='RPi', index=1)

    assert c.commands == ('foo', 'bar')
    assert c.index == 1
    assert c.hint is None

    c = Command('video.cec.name', command='cec_osd_name', default='RPi')
    assert c.commands == ('cec_osd_name',)
    assert c.index is None
    assert c.key == ('commands', 'video.cec.name')


def test_command_extract():
    c = CommandStr('video.cec.name', command='cec_osd_name', default='RPi')

    config = [
        BootCommand('config.txt', 1, cond_all, 'cec_osd_name', 'FOO', hdmi=0),
    ]
    assert list(c.extract(config)) == [
        (config[0], 'FOO'),
    ]


def test_command_output():
    c = CommandStr('video.cec.name', command='cec_osd_name', default='RPi')

    assert list(c.output()) == []
    c._value = 'FOO'
    assert list(c.output()) == ['cec_osd_name=FOO']
    c = Command('video.cec.name', command='cec_osd_name', default='RPi', index=1)
    c._value = 'FOO'
    assert list(c.output()) == ['cec_osd_name:1=FOO']


def test_str_command_init():
    c = CommandStr('gpio.1.pull', command='gpio0pull', default='np',
                   valid={'up': 'pull up', 'dn': 'pull down', 'np': 'no pull'})

    assert c.commands == ('gpio0pull',)
    assert c.default == 'np'
    assert c.hint == 'no pull'
    c.validate()

    c._value = 'up'
    assert c.hint == 'pull up'
    c.validate()

    c._value = 'foo'
    with pytest.raises(ValueError):
        c.validate()


def test_int_command_init():
    c = CommandInt('video.hdmi1.drive', index=1, command='hdmi_drive',
                   valid={0: 'auto', 1: 'dvi', 2: 'hdmi'})

    assert c.commands == ('hdmi_drive',)
    assert c.index == 1
    assert c.default == 0
    assert c.hint == 'auto'
    c.validate()

    c._value = 1
    assert c.hint == 'dvi'
    c.validate()

    c._value = 4
    with pytest.raises(ValueError):
        c.validate()


def test_int_command_extract():
    c = CommandInt('video.hdmi1.drive', index=1, command='hdmi_drive',
                   valid={0: 'auto', 1: 'dvi', 2: 'hdmi'})

    config = [
        BootCommand('config.txt', 1, cond_all, 'hdmi_drive', '2', hdmi=1),
        BootCommand('config.txt', 1, cond_all, 'hdmi_drive', 'foo', hdmi=1),
    ]
    with warnings.catch_warnings(record=True) as w:
        assert list(c.extract(config)) == [
            (config[0], 2),
            (config[1], None),
        ]
        assert len(w) == 1
        assert issubclass(w[0].category, ParseWarning)


def test_int_command_output():
    c = CommandInt('video.hdmi1.drive', index=1, command='hdmi_drive',
                   valid={0: 'auto', 1: 'dvi', 2: 'hdmi'})

    assert list(c.output()) == []
    c._value = 2
    assert list(c.output()) == ['hdmi_drive:1=2']


def test_hex_command_init():
    c = CommandIntHex('boot.dt.address', command='dt_address')

    assert c.commands == ('dt_address',)
    assert c.index == 0
    assert c.default == 0
    assert c.hint == '0x0'

    c._value = 0x3000000
    assert c.hint == '0x3000000'


def test_hex_command_output():
    c = CommandIntHex('boot.dt.address', command='dt_address')

    assert list(c.output()) == []
    c._value = 0x100
    assert list(c.output()) == ['dt_address=0x100']


def test_bool_command_init():
    c = CommandBool('boot.test.enabled', command='test_mode')

    assert c.commands == ('test_mode',)
    assert c.index == 0
    assert c.default is False
    assert c.hint is None
    assert not c.value

    c._value = c.update(UserStr('on'))
    assert c.value


def test_bool_command_extract():
    c = CommandBool('boot.test.enabled', command='test_mode')

    config = [
        BootCommand('config.txt', 1, cond_all, 'test_mode', '1', hdmi=0),
        BootCommand('config.txt', 1, cond_all, 'test_mode', 'foo', hdmi=0),
    ]
    with warnings.catch_warnings(record=True) as w:
        assert list(c.extract(config)) == [
            (config[0], True),
            (config[1], None),
        ]
        assert len(w) == 1
        assert issubclass(w[0].category, ParseWarning)


def test_bool_command_output():
    c = CommandBool('boot.test.enabled', command='test_mode')

    assert list(c.output()) == []
    c._value = True
    assert list(c.output()) == ['test_mode=1']


def test_inv_bool_command_init():
    c = CommandBoolInv('video.overscan.enabled', command='disable_overscan',
                       default=True)

    assert c.commands == ('disable_overscan',)
    assert c.index == 0
    assert c.default is True
    assert c.hint is None
    assert c.value

    c._value = c.update(UserStr('off'))
    assert not c.value


def test_inv_bool_command_extract():
    c = CommandBoolInv('video.overscan.enabled', command='disable_overscan',
                       default=True)

    config = [
        BootCommand('config.txt', 1, cond_all, 'disable_overscan', '1', hdmi=0),
    ]
    assert list(c.extract(config)) == [
        (config[0], False),
    ]


def test_inv_bool_command_output():
    c = CommandBoolInv('video.overscan.enabled', command='disable_overscan',
                       default=True)

    assert list(c.output()) == []
    c._value = False
    assert list(c.output()) == ['disable_overscan=1']


def test_force_ignore_command_extract():
    c = CommandForceIgnore('video.hdmi.enabled', force='hdmi_force',
                           ignore='hdmi_ignore')

    config = [
        BootCommand('config.txt', 1, cond_all, 'hdmi_force', '1', hdmi=0),
        BootCommand('config.txt', 2, cond_all, 'hdmi_ignore', '1', hdmi=0),
        BootCommand('config.txt', 2, cond_all, 'hdmi_ignore', 'blah', hdmi=0),
    ]
    with warnings.catch_warnings(record=True) as w:
        assert list(c.extract(config)) == [
            (config[0], True),
            (config[1], False),
            (config[2], False),
        ]
        assert len(w) == 1
        assert issubclass(w[0].category, ParseWarning)


def test_force_ignore_command_output():
    c = CommandForceIgnore('video.hdmi.enabled', force='hdmi_force',
                           ignore='hdmi_ignore')

    assert c._value is None
    assert list(c.output()) == []

    c._value = False
    assert list(c.output()) == ['hdmi_ignore=1']

    c._value = True
    assert list(c.output()) == ['hdmi_force=1']

    c = CommandForceIgnore('video.hdmi.enabled', force='hdmi_force',
                           ignore='hdmi_ignore', index=1)

    c._value = False
    assert list(c.output()) == ['hdmi_ignore:1=1']

    c._value = True
    assert list(c.output()) == ['hdmi_force:1=1']


def test_mask_command_init():
    cm = CommandMaskMaster('video.dpi.format', command='dpi_format', mask=0xf,
                           dummies={'.clock'})
    cd = CommandMaskDummy('video.dpi.clock', command='dpi_format', mask=0x10)

    assert cm.commands == cd.commands == ('dpi_format',)
    assert cm.index == cd.index == 0
    assert cm.default == cd.default == 0
    assert cm._mask == 0xf
    assert cm._shift == 0
    assert not cm._bool
    assert cm._names == ('video.dpi.format', 'video.dpi.clock')
    assert cd._mask == 0x10
    assert cd._shift == 4
    assert cd._bool
    assert cm.value == 0

    cm._value = cm.update(UserStr('0x8'))
    assert cm.value == 8
    assert cd.value == 0

    cd._value = cd.update(UserStr('on'))
    assert cd.value == 1


def test_mask_command_extract():
    cm = CommandMaskMaster('video.dpi.format', command='dpi_format', mask=0xf,
                           dummies={'.clock'})
    cd = CommandMaskDummy('video.dpi.clock', command='dpi_format', mask=0x10)

    config = [
        BootCommand('config.txt', 1, cond_all, 'dpi_format', '0x18', hdmi=0),
    ]
    assert list(cm.extract(config)) == [
        (config[0], 8),
    ]
    assert list(cd.extract(config)) == [
        (config[0], True),
    ]


def test_mask_command_output():
    settings = make_settings(
        CommandMaskMaster('video.dpi.format', command='dpi_format', mask=0xf,
                          dummies={'.clock'}),
        CommandMaskDummy('video.dpi.clock', command='dpi_format', mask=0x10))
    cm = settings['video.dpi.format']
    cd = settings['video.dpi.clock']

    assert list(cm.output()) == []
    assert list(cd.output()) == []
    cm._value = 8
    assert list(cm.output()) == ['dpi_format=0x8']
    assert list(cd.output()) == []
    cd._value = True
    assert list(cm.output()) == ['dpi_format=0x18']
    with pytest.raises(DelegatedOutput):
        list(cd.output())


def test_filename_command_hint():
    settings = make_settings(
        Command('boot.prefix', command='os_prefix', default=''),
        CommandFilename('fw.filename', command='start_file',
                        default='start.elf'))
    prefix = settings['boot.prefix']
    start = settings['fw.filename']

    assert prefix.value == ''
    assert start.value == 'start.elf'
    assert start.filename == start.value
    assert start.hint is None

    prefix._value = 'boot1/'
    assert start.filename == 'boot1/start.elf'
    assert start.hint == "'boot1/start.elf' with boot.prefix"


def test_display_mode_hint():
    settings = make_settings(
        CommandDisplayGroup('video.hdmi.group', command='hdmi_group'),
        CommandDisplayMode('video.hdmi.mode', command='hdmi_mode'))
    group = settings['video.hdmi.group']
    mode = settings['video.hdmi.mode']

    assert group.hint == 'auto from EDID'
    assert mode.hint == 'auto from EDID'

    group._value = 1
    group.validate()
    with pytest.raises(ValueError):
        mode.validate()

    mode._value = 4
    mode.validate()
    assert group.hint == 'CEA'
    assert mode.hint == '720p @60Hz'

    mode._value = 94
    mode.validate()
    assert group.hint == 'CEA'
    assert mode.hint == '2160p @25Hz (Pi 4)'

    group._value = 2
    mode._value = 87
    mode.validate()
    assert group.hint == 'DMT'
    assert mode.hint == 'user timings'


def test_display_timings_extract():
    t = CommandDisplayTimings('video.timings', command='video_timings')

    config = [
        BootCommand('config.txt', 1, cond_all, 'video_timings', '', hdmi=0),
        BootCommand('config.txt', 2, cond_all, 'video_timings',
                    ' '.join(['0'] * 17), hdmi=0),
        BootCommand('config.txt', 3, cond_all, 'video_timings',
                    '0 1 0 0 foo 1 2 3 4 5', hdmi=0),
    ]
    with warnings.catch_warnings(record=True) as w:
        assert list(t.extract(config)) == [
            (config[0], []),
            (config[1], [0] * 17),
            (config[2], []),
        ]
        assert len(w) == 1
        assert issubclass(w[0].category, ParseWarning)


def test_display_timings_update():
    t = CommandDisplayTimings('video.timings', command='video_timings')

    assert not t.modified
    assert t.value == []

    t._value = t.update(UserStr(','.join(['0'] * 17)))
    t.validate()
    assert t.modified
    assert t.value == [0] * 17

    t._value = t.update(UserStr(','.join(['15'] * 17)))
    t.validate()
    assert t.value == [15] * 17

    t._value = t.update(list(range(17)))
    assert t.value == list(range(17))

    t._value = t.update(UserStr(''))
    t.validate()
    assert not t.modified
    assert t.value == []

    t._value = [1] * 16
    with pytest.raises(ValueError):
        t.validate()


def test_display_timings_output():
    t = CommandDisplayTimings('video.timings', command='video_timings')

    assert list(t.output()) == []
    t._value = [0] * 17
    assert list(t.output()) == ['video_timings=' + ' '.join(['0'] * 17)]
    t._value = list(range(17))
    assert list(t.output()) == ['video_timings=' + ' '.join(str(i) for i in range(17))]


def test_rotate_flip_extract():
    settings = make_settings(
        CommandDisplayRotate('video.rotate', command='hdmi_rotate'),
        CommandDisplayFlip('video.flip', command='hdmi_rotate'))
    rot = settings['video.rotate']
    flip = settings['video.flip']

    config = [
        BootCommand('config.txt', 1, cond_all, 'hdmi_rotate', '0x10001', hdmi=0),
    ]
    assert list(rot.extract(config)) == [
        (config[0], 90),
    ]
    assert list(flip.extract(config)) == [
        (config[0], 1),
    ]


def test_rotate_flip_update():
    settings = make_settings(
        CommandDisplayRotate('video.rotate', command='hdmi_rotate'),
        CommandDisplayFlip('video.flip', command='hdmi_rotate'))
    rot = settings['video.rotate']
    flip = settings['video.flip']

    rot._value = rot.update(UserStr('90'))
    assert rot.modified
    rot.validate()

    rot._value = rot.update(45)
    assert rot.modified
    with pytest.raises(ValueError):
        rot.validate()

    rot._value = rot.update(UserStr(''))
    assert not rot.modified
    rot.validate()


def test_rotate_flip_output():
    settings = make_settings(
        CommandDisplayRotate('video.rotate', command='hdmi_rotate'),
        CommandDisplayFlip('video.flip', command='hdmi_rotate'))
    rot = settings['video.rotate']
    flip = settings['video.flip']

    assert list(rot.output()) == []
    assert list(flip.output()) == []
    rot._value = 90
    assert list(rot.output()) == ['hdmi_rotate=0x1']
    assert list(flip.output()) == []
    flip._value = 1
    assert list(rot.output()) == ['hdmi_rotate=0x10001']
    with pytest.raises(DelegatedOutput) as exc:
        list(flip.output())
        assert exc.value.master == 'video.rotate'


def test_rotate_flip_indexed_output():
    settings = make_settings(
        CommandDisplayRotate('video.rotate', index=1, command='hdmi_rotate'),
        CommandDisplayFlip('video.flip', index=1, command='hdmi_rotate'))
    rot = settings['video.rotate']
    flip = settings['video.flip']

    assert list(rot.output()) == []
    assert list(flip.output()) == []
    rot._value = 90
    assert list(rot.output()) == ['hdmi_rotate:1=0x1']
    assert list(flip.output()) == []
    flip._value = 1
    assert list(rot.output()) == ['hdmi_rotate:1=0x10001']
    with pytest.raises(DelegatedOutput) as exc:
        list(flip.output())
        assert exc.value.master == 'video.rotate'


def test_rotate_flip_lcd_output():
    settings = make_settings(
        CommandDisplayRotate('video.rotate', commands=('hdmi_rotate', 'lcd_rotate')),
        CommandDisplayFlip('video.flip', commands=('hdmi_rotate', 'lcd_rotate')))
    rot = settings['video.rotate']
    flip = settings['video.flip']

    assert list(rot.output()) == []
    assert list(flip.output()) == []
    rot._value = 90
    assert list(rot.output()) == ['lcd_rotate=1']
    assert list(flip.output()) == []
    flip._value = 1
    assert list(rot.output()) == ['hdmi_rotate=0x10001']
    with pytest.raises(DelegatedOutput) as exc:
        list(flip.output())
        assert exc.value.master == 'video.rotate'


def test_dpi_output():
    settings = make_settings(
        CommandBool('dpi.enabled', command='dpi_enabled'),
        CommandDPIOutput('dpi.format', command='dpi_format', mask=0xf,
                         dummies={ '.color'}),
        CommandDPIDummy('dpi.color', command='dpi_format', mask=0x10))
    enable = settings['dpi.enabled']
    fmt = settings['dpi.format']
    col = settings['dpi.color']

    assert list(chain(enable.output(), fmt.output(), col.output())) == []
    fmt._value = 8
    col._value = True
    assert list(chain(enable.output(), fmt.output())) == []
    with pytest.raises(DelegatedOutput) as exc:
        list(col.output())
        assert exc.value.master == 'video.dpi.format'
    enable._value = True
    assert list(chain(enable.output(), fmt.output())) == [
        'dpi_enabled=1',
        'dpi_format=0x18',
    ]


def test_hdmi_boost_validate():
    boost = CommandHDMIBoost('video.boost', command='hdmi_boost', default=5)

    assert boost.value == 5
    assert not boost.modified
    boost.validate()

    boost._value = 1
    assert boost.value == 1
    assert boost.modified
    boost.validate()

    boost._value = 12
    assert boost.modified
    with pytest.raises(ValueError):
        boost.validate()


def test_edid_ignore():
    ignore = CommandEDIDIgnore('video.edid.ignore', command='hdmi_ignore')

    assert ignore.value is False
    assert not ignore.modified
    assert ignore.hint is None
    assert list(ignore.output()) == []

    ignore._value = ignore.update(UserStr('on'))
    assert ignore.value is True
    assert ignore.modified
    assert ignore.hint is None

    assert list(ignore.output()) == ['hdmi_ignore=0xa5000080']
    config = [BootCommand('config.txt', 1, cond_all, 'hdmi_ignore', '0', hdmi=0)]
    assert list(ignore.extract(config)) == [(config[0], False)]
    config = [BootCommand('config.txt', 1, cond_all, 'hdmi_ignore', '0xa5000080', hdmi=0)]
    assert list(ignore.extract(config)) == [(config[0], True)]


def test_boot_delay2():
    delay = CommandBootDelay2(
        'boot.delay', commands=('boot_delay', 'boot_delay_ms'), default=0)

    assert delay.value == 0.0
    assert not delay.modified
    delay.validate()

    config = [
        BootCommand('config.txt', 1, cond_all, 'boot_delay', '1', hdmi=0),
        BootCommand('config.txt', 2, cond_all, 'boot_delay_ms', '500', hdmi=0),
        BootCommand('config.txt', 3, cond_all, 'boot_delay', '2', hdmi=0),
        BootCommand('config.txt', 4, cond_all, 'boot_delay', 'foo', hdmi=0),
        BootCommand('config.txt', 5, cond_all, 'boot_delay_ms', 'bar', hdmi=0),
    ]
    with warnings.catch_warnings(record=True) as w:
        assert list(delay.extract(config)) == [
            (config[0], 1.0),
            (config[1], 1.5),
            (config[2], 2.5),
            (config[3], 0.5),
            (config[4], 0.0),
        ]
        assert len(w) == 2
        assert issubclass(w[0].category, ParseWarning)
        assert issubclass(w[1].category, ParseWarning)

    assert list(delay.output()) == []
    delay._value = delay.update(UserStr('2.5'))
    assert delay.modified
    delay.validate()
    assert list(delay.output()) == ['boot_delay=2', 'boot_delay_ms=500']
    delay._value = delay.update(UserStr('0.5'))
    delay.validate()
    assert list(delay.output()) == ['boot_delay_ms=500']
    delay._value = delay.update(UserStr('0.0'))
    delay.validate()
    assert list(delay.output()) == []

    delay._value = -1
    with pytest.raises(ValueError):
        delay.validate()


def test_kernel_address():
    settings = make_settings(
        CommandKernel64('kernel.64bit', commands=('arm_64bit', 'arm_control')),
        CommandKernelAddress('kernel.addr', commands=('kernel_address', 'kernel_old')))
    arm8 = settings['kernel.64bit']
    addr = settings['kernel.addr']

    assert not arm8.value
    assert not addr.modified
    assert addr.value == 0x8000

    arm8._value = True
    assert not addr.modified
    assert addr.value == 0x80000

    config = [
        BootCommand('config.txt', 1, cond_all, 'arm_64bit', '0', hdmi=0),
        BootCommand('config.txt', 2, cond_all, 'arm_64bit', 'erm', hdmi=0),
        BootCommand('config.txt', 3, cond_all, 'arm_control', '0x202', hdmi=0),
        BootCommand('config.txt', 4, cond_all, 'kernel_address', 'f00', hdmi=0),
        BootCommand('config.txt', 5, cond_all, 'kernel_address', '0xf00', hdmi=0),
        BootCommand('config.txt', 6, cond_all, 'kernel_old', '0', hdmi=0),
        BootCommand('config.txt', 7, cond_all, 'kernel_old', '1', hdmi=0),
    ]
    with warnings.catch_warnings(record=True) as w:
        assert list(arm8.extract(config)) == [
            (config[0], False),
            (config[1], None),
            (config[2], True),
        ]
        assert list(addr.extract(config)) == [
            (config[3], None),
            (config[4], 0xf00),
            (config[6], 0),
        ]
        assert len(w) == 2
        assert issubclass(w[0].category, ParseWarning)
        assert issubclass(w[1].category, ParseWarning)


def test_kernel_filename():
    with mock.patch('pibootctl.setting.get_board_types') as get_board_types:
        settings = make_settings(
            CommandKernel64('kernel.64bit', commands=('arm_64bit', 'arm_control')),
            CommandKernelFilename('kernel.filename', command='kernel_filename'))
        arm8 = settings['kernel.64bit']
        filename = settings['kernel.filename']

        assert not filename.modified
        get_board_types.return_value = {'pi0'}
        assert filename.value == 'kernel.img'
        get_board_types.return_value = {'pi4', 'pi400'}
        assert filename.value == 'kernel7l.img'
        get_board_types.return_value = {'pi3', 'pi3+'}
        assert filename.value == 'kernel7.img'
        arm8._value = True
        assert filename.value == 'kernel8.img'

        filename._value = filename.update('vmlinuz')
        assert filename.value == 'vmlinuz'
        filename._value = filename.update(UserStr(''))
        assert filename.value == 'kernel8.img'


def test_camera_firmware(fw_settings):
    with mock.patch('pibootctl.setting.get_board_types') as get_board_types:
        cam = fw_settings['camera.enabled']
        mem = fw_settings['gpu.mem']
        start = fw_settings['boot.firmware.filename']
        fixup = fw_settings['boot.firmware.fixup']

        assert not cam.modified
        assert not cam.value
        cam.validate()

        # camera mode can be enabled (by default) by specifying firmware manually
        get_board_types.return_value = {'pi0'}
        start._value = 'start_x.elf'
        fixup._value = 'fixup_x.dat'
        assert not cam.modified
        assert cam.value
        assert cam.default
        cam.validate()
        assert list(cam.output()) == []

        get_board_types.return_value = {'pi4', 'cm4'}
        assert not cam.value
        assert not cam.default

        start._value = None
        fixup._value = None
        cam._value = True
        cam.validate()
        assert cam.modified
        assert cam.value
        assert start.value == 'start4x.elf'
        assert fixup.value == 'fixup4x.dat'
        assert list(cam.output()) == ['start_x=1']

        mem._value = 32
        get_board_types.return_value = {'pi0'}
        with pytest.raises(ValueError):
            cam.validate()


def test_camera_firmware_extract(fw_settings):
    cam = fw_settings['camera.enabled']
    config = [
        BootCommand('config.txt', 1, cond_all, 'gpu_mem', '192', hdmi=0),
        BootCommand('config.txt', 2, cond_all, 'start_x', '1', hdmi=0),
        BootCommand('config.txt', 3, cond_all, 'start_x', '0', hdmi=0),
        BootCommand('config.txt', 4, cond_all, 'start_debug', '1', hdmi=0),
        BootCommand('syscfg.txt', 1, cond_all, 'start_debug', '1', hdmi=0),
    ]
    assert list(cam.extract(config)) == [
        (config[1], True),
        (config[2], None),
    ]


def test_firmware_file_extract(fw_settings):
    start = fw_settings['boot.firmware.filename']
    fixup = fw_settings['boot.firmware.fixup']
    config = [
        BootCommand('config.txt', 1, cond_all, 'start_file', 'start.elf', hdmi=0),
        BootCommand('config.txt', 2, cond_all, 'fixup_file', 'fixup.dat', hdmi=0),
        BootCommand('usercfg.txt', 1, cond_all, 'start_file', 'start_x.elf', hdmi=0),
        BootCommand('usercfg.txt', 2, cond_all, 'fixup_file', 'fixup_x.dat', hdmi=0),
    ]
    assert list(start.extract(config)) == [(config[0], 'start.elf')]
    assert list(fixup.extract(config)) == [(config[1], 'fixup.dat')]


def test_debug_firmware(fw_settings):
    with mock.patch('pibootctl.setting.get_board_types') as get_board_types:
        debug = fw_settings['boot.debug.enabled']
        start = fw_settings['boot.firmware.filename']
        fixup = fw_settings['boot.firmware.fixup']
        assert not debug.modified
        assert not debug.value
        debug.validate()

        # debug mode can be enabled by specifying firmware manually
        get_board_types.return_value = {'pi0', 'pi0w'}
        start._value = 'start_db.elf'
        fixup._value = 'fixup_db.dat'
        assert not debug.modified
        assert debug.value
        assert debug.default
        debug.validate()
        assert list(debug.output()) == []

        get_board_types.return_value = {'pi4'}
        assert not debug.value
        assert not debug.default

        start._value = None
        fixup._value = None
        debug._value = True
        debug.validate()
        assert debug.modified
        assert debug.value
        assert start.value == 'start4db.elf'
        assert fixup.value == 'fixup4db.dat'
        assert list(debug.output()) == ['start_debug=1']


def test_debug_firmware_extract(fw_settings):
    debug = fw_settings['boot.debug.enabled']
    config = [
        BootCommand('config.txt', 1, cond_all, 'start_debug', '1', hdmi=0),
        BootCommand('config.txt', 2, cond_all, 'start_debug', '0', hdmi=0),
        BootCommand('syscfg.txt', 1, cond_all, 'start_debug', '1', hdmi=0),
    ]
    assert list(debug.extract(config)) == [
        (config[0], True),
        (config[1], None),
    ]


def test_firmware_filename(fw_settings):
    with mock.patch('pibootctl.setting.get_board_types') as get_board_types:
        cam = fw_settings['camera.enabled']
        debug = fw_settings['boot.debug.enabled']
        start = fw_settings['boot.firmware.filename']
        fixup = fw_settings['boot.firmware.fixup']
        mem = fw_settings['gpu.mem']

        get_board_types.return_value = {'pi0'}
        assert not start.modified
        assert not fixup.modified
        assert start.value == 'start.elf'
        assert fixup.value == 'fixup.dat'

        cam._value = True
        assert start.value == 'start_x.elf'
        assert fixup.value == 'fixup_x.dat'
        debug._value = True
        assert start.value == 'start_db.elf'
        assert fixup.value == 'fixup_db.dat'
        mem._value = 16
        assert start.value == 'start_cd.elf'
        assert fixup.value == 'fixup_cd.dat'

        mem._value = None
        cam._value = None
        debug._value = None
        get_board_types.return_value = {'pi4'}
        assert not start.modified
        assert not fixup.modified
        assert start.value == 'start4.elf'
        assert fixup.value == 'fixup4.dat'

        cam._value = True
        assert start.value == 'start4x.elf'
        assert fixup.value == 'fixup4x.dat'
        debug._value = True
        assert start.value == 'start4db.elf'
        assert fixup.value == 'fixup4db.dat'
        mem._value = 16
        assert start.value == 'start4cd.elf'
        assert fixup.value == 'fixup4cd.dat'


def test_dt_addr():
    dt_addr = CommandDeviceTreeAddress('dt.addr', command='device_tree_address')
    assert not dt_addr.modified
    assert dt_addr.value == 0
    assert dt_addr.hint == 'auto'

    dt_addr._value = 0x3000000
    assert dt_addr.modified
    assert dt_addr.value == 0x3000000
    assert dt_addr.hint == '0x3000000'


def test_initrd_addr():
    settings = make_settings(
        Command('boot.prefix', command='os_prefix', default=''),
        CommandRamFSFilename('initrd.filename', commands=('ramfsfile', 'initramfs')),
        CommandRamFSAddress('initrd.address', commands=('ramfsaddr', 'initramfs')),
    )
    prefix = settings['boot.prefix']
    initrd_file = settings['initrd.filename']
    initrd_addr = settings['initrd.address']

    assert not initrd_addr.modified
    assert initrd_addr.value == 0
    assert initrd_addr.hint == '0x0'

    initrd_addr._value = 0x2400000
    assert initrd_addr.modified
    assert initrd_addr.value == 0x2400000
    assert initrd_addr.hint == '0x2400000'

    initrd_addr._value = -1
    assert initrd_addr.modified
    assert initrd_addr.value == -1
    assert initrd_addr.hint == 'auto'

    with pytest.raises(ValueError):
        initrd_addr.validate()
    initrd_file._value = ['initrd.img']
    initrd_addr.validate()


def test_initrd_addr_extract():
    initrd_addr = CommandRamFSAddress('initrd.addr', commands=('ramfsaddr', 'initramfs'))
    config = [
        BootCommand('config.txt', 1, cond_all, 'initramfs', ('initrd.img', 'followkernel'), hdmi=0),
        BootCommand('config.txt', 2, cond_all, 'initramfs', ('initrd.img', '0'), hdmi=0),
        BootCommand('config.txt', 3, cond_all, 'initramfs', ('initrd.img', '0x2400000'), hdmi=0),
        BootCommand('config.txt', 4, cond_all, 'ramfsaddr', '0x2700000', hdmi=0),
        BootCommand('config.txt', 5, cond_all, 'ramfsaddr', 'f000000', hdmi=0)
    ]
    with warnings.catch_warnings(record=True) as w:
        assert list(initrd_addr.extract(config)) == [
            (config[0], -1),
            (config[1], -1),
            (config[2], 0x2400000),
            (config[3], 0x2700000),
            (config[4], None),
        ]
        assert len(w) == 1
        assert issubclass(w[0].category, ParseWarning)


def test_initrd_filename():
    settings = make_settings(
        Command('boot.prefix', command='os_prefix', default=''),
        CommandRamFSFilename('initrd.file', commands=('ramfsfile', 'initramfs')))
    prefix = settings['boot.prefix']
    initrd = settings['initrd.file']

    initrd.validate()
    assert not initrd.modified
    assert initrd.value == []
    assert initrd.filename == []
    assert initrd.hint is None

    initrd._value = initrd.update(['initrd.img'])
    initrd.validate()
    assert initrd.modified
    assert initrd.value == ['initrd.img']
    assert initrd.filename == ['initrd.img']
    assert initrd.hint is None

    initrd._value = initrd.update(UserStr(' initrd.img,splash.img'))
    initrd.validate()
    assert initrd.modified
    assert initrd.value == ['initrd.img', 'splash.img']
    assert initrd.filename == ['initrd.img', 'splash.img']
    assert initrd.hint is None

    prefix._value = 'boot/'
    assert initrd.modified
    assert initrd.value == ['initrd.img', 'splash.img']
    assert initrd.filename == ['boot/initrd.img', 'boot/splash.img']
    assert initrd.hint == "['boot/initrd.img', 'boot/splash.img'] with boot.prefix"
    initrd._value = initrd.update(['initrd{}.img'.format(i) for i in range(10)])
    with pytest.raises(ValueError):
        initrd.validate()


def test_initrd_filename_extract():
    initrd = CommandRamFSFilename('initrd.file', commands=('ramfsfile', 'initramfs'))
    config = [
        BootCommand('config.txt', 1, cond_all, 'initramfs', ('initrd.img', 'followkernel'), hdmi=0),
        BootCommand('config.txt', 2, cond_all, 'initramfs', ('initrd.img,splash.img', '0x2400000'), hdmi=0),
        BootCommand('config.txt', 3, cond_all, 'ramfsfile', 'initrd.img,net.img', hdmi=0),
    ]
    assert list(initrd.extract(config)) == [
        (config[0], ['initrd.img']),
        (config[1], ['initrd.img', 'splash.img']),
        (config[2], ['initrd.img', 'net.img']),
    ]


def test_initrd_filename_output():
    settings = make_settings(
        CommandRamFSFilename('initrd.filename', commands=('ramfsfile', 'initramfs')),
        CommandRamFSAddress('initrd.address', commands=('ramfsaddr', 'initramfs')),
    )
    initfn = settings['initrd.filename']
    initaddr = settings['initrd.address']
    assert list(initfn.output()) == []
    assert list(initaddr.output()) == []
    initfn._value = ['initrd.img']
    assert list(chain(initfn.output(), initaddr.output())) == ['ramfsfile=initrd.img']
    initaddr._value = -1
    with pytest.raises(DelegatedOutput) as exc:
        list(initaddr.output())
        assert exc.value.master == 'initrd.filename'
    assert list(initfn.output()) == ['initramfs initrd.img followkernel']
    initfn._value = ['initrd.img', 'splash.img']
    assert list(initfn.output()) == ['initramfs initrd.img,splash.img followkernel']
    with pytest.raises(DelegatedOutput) as exc:
        list(initaddr.output())
        assert exc.value.master == 'initrd.filename'
    initaddr._value = 0x2400000
    assert list(chain(initfn.output(), initaddr.output())) == [
        'ramfsfile=initrd.img,splash.img', 'ramfsaddr=0x2400000']


def test_serial_bt():
    with mock.patch('pibootctl.setting.get_board_types') as get_board_types:
        settings = make_settings(
            CommandSerialEnabled('serial.enabled', command='enable_uart'),
            OverlayBluetoothEnabled('bluetooth.enabled'),
            OverlaySerialUART('serial.uart'))
        enable = settings['serial.enabled']
        bt = settings['bluetooth.enabled']
        uart = settings['serial.uart']

        get_board_types.return_value = set()
        enable.validate()
        uart.validate()
        assert not enable.modified
        assert not uart.modified
        assert enable.value
        assert enable.default
        assert uart.value == 0
        assert uart.default == 0
        assert uart.hint == '/dev/ttyAMA0; PL011'

        # Pi3 (and above) moves serial to mini-UART
        get_board_types.return_value = {'pi3', 'pi3+'}
        enable.validate()
        uart.validate()
        assert not enable.value
        assert not enable.default
        assert uart.value == 1
        assert uart.default == 1
        assert uart.hint == '/dev/ttyS0; mini-UART'

        # ... but can be forced back to PL011
        enable._value = enable.update(UserStr('on'))
        uart._value = uart.update(UserStr('0'))
        enable.validate()
        uart.validate()
        assert enable.modified
        assert enable.value
        assert not enable.default
        assert uart.modified
        assert uart.value == 0
        assert uart.default == 1

        # ... and will default to that if Bluetooth is disabled
        uart._value = None
        bt._value = bt.update(UserStr('off'))
        enable.validate()
        uart.validate()
        assert enable.value
        assert enable.default
        assert uart.value == 0
        assert uart.default == 0

        # Can't use mini-UART with BT disabled (because what would be the point)
        uart._value = 1
        with pytest.raises(ValueError):
            uart.validate()


def test_serial_bt_extract():
    settings = make_settings(
        CommandSerialEnabled('serial.enabled', command='enable_uart'),
        OverlayBluetoothEnabled('bluetooth.enabled'),
        OverlaySerialUART('serial.uart'))
    enable = settings['serial.enabled']
    bt = settings['bluetooth.enabled']
    uart = settings['serial.uart']

    config = [
        BootCommand('config.txt', 1, cond_all, 'enable_uart', '1', hdmi=0),
        BootOverlay('config.txt', 2, cond_all, 'pi3-miniuart-bt'),
        BootOverlay('config.txt', 3, cond_all, 'disable-bt'),
        BootOverlay('config.txt', 4, cond_all, 'foo'),
    ]
    assert list(enable.extract(config)) == [(config[0], True)]
    assert list(bt.extract(config)) == [(config[1], True), (config[2], False)]
    assert list(uart.extract(config)) == [(config[1], 0)]


def test_serial_bt_output():
    with mock.patch('pibootctl.setting.get_board_types') as get_board_types:
        settings = make_settings(
            CommandSerialEnabled('serial.enabled', command='enable_uart'),
            OverlayBluetoothEnabled('bluetooth.enabled'),
            OverlaySerialUART('serial.uart'))
        enable = settings['serial.enabled']
        bt = settings['bluetooth.enabled']
        uart = settings['serial.uart']

        get_board_types.return_value = {'pi3'}
        assert list(chain(enable.output(), bt.output(), uart.output())) == []
        bt._value = True
        assert list(chain(enable.output(), bt.output(), uart.output())) == []
        enable._value = True
        assert list(chain(enable.output(), bt.output(), uart.output())) == ['enable_uart=1']
        uart._value = 0
        assert list(chain(enable.output(), bt.output())) == [
            'enable_uart=1',
            'dtoverlay=miniuart-bt',
        ]
        with pytest.raises(DelegatedOutput) as exc:
            list(uart.output())
            assert exc.value.master == 'bluetooth.enabled'
        bt._value = False
        assert list(chain(enable.output(), bt.output())) == [
            'enable_uart=1',
            'dtoverlay=disable-bt',
        ]
        with pytest.raises(DelegatedOutput) as exc:
            list(uart.output())
            assert exc.value.master == 'bluetooth.enabled'


def test_l2_cache():
    with mock.patch('pibootctl.setting.get_board_types') as get_board_types:
        cache = CommandCPUL2Cache('l2.enabled', command='disable_l2_cache')

        get_board_types.return_value = set()
        assert not cache.modified
        assert cache.default is False
        get_board_types.return_value = {'pi0'}
        assert cache.default is True
        get_board_types.return_value = {'pi4', 'pi400'}
        assert cache.default is False


def test_cpu_volt():
    with mock.patch('pibootctl.setting.get_board_type') as get_board_type:
        settings = make_settings(
            CommandCPUVoltMax('cpu.max', command='over_voltage'),
            CommandVoltage('cpu.min', command='over_voltage_min'),
            CommandBool('cpu.turbo.force', command='force_turbo'))
        volt_max = settings['cpu.max']
        volt_min = settings['cpu.min']
        turbo = settings['cpu.turbo.force']

        get_board_type.return_value = None
        assert not turbo.modified
        assert not turbo.value
        assert not volt_min.modified
        assert not volt_max.modified
        assert volt_min.hint == '1.2V'
        assert volt_max.hint == '1.35V'
        assert (volt_min.default, volt_max.default) == (0, 0)

        get_board_type.return_value = 'pi1'
        assert volt_min.hint == '1.2V'
        assert volt_max.hint == '1.2V'
        volt_min._value = -1
        volt_max._value = 1
        assert volt_min.hint == '1.175V'
        assert volt_max.hint == '1.225V'

        get_board_type.return_value = 'pi3'
        volt_min._value = -4
        volt_max._value = 4
        assert volt_min.hint == '1.1V'
        assert volt_max.hint == '1.45V'

        get_board_type.return_value = 'pi4'
        volt_min._value = -16
        volt_max._value = 8
        turbo._value = True
        assert volt_min.hint == '0.8V'
        assert volt_max.hint == '1.55V'

        volt_min.validate()
        volt_max.validate()

        # volt_max > 6 requires turbo
        turbo._value = False
        with pytest.raises(ValueError):
            volt_max.validate()

        # volt_max must be >= volt_min
        volt_min._value = 0
        volt_max._value = -1
        with pytest.raises(ValueError):
            volt_max.validate()

        # voltage must be in range -16..8
        volt_max._value = 255
        with pytest.raises(ValueError):
            volt_max.validate()


def test_sdram_volt_output():
    settings = make_settings(
        CommandSDRAMVoltage('mem.ctrl.voltage', commands=('over_voltage_sdram_c', 'over_voltage_sdram')),
        CommandSDRAMVoltage('mem.io.voltage', commands=('over_voltage_sdram_i', 'over_voltage_sdram')),
        CommandSDRAMVoltage('mem.phy.voltage', commands=('over_voltage_sdram_p', 'over_voltage_sdram')),
    )

    def get_volt_output():
        lines = []
        errors = []
        for setting in sorted(settings.values(), key=attrgetter('key')):
            if setting.name.startswith('mem.'):
                try:
                    lines.extend(setting.output())
                except DelegatedOutput as exc:
                    errors.append(exc)
        return lines, errors

    lines, errors = get_volt_output()
    assert lines == []
    assert errors == []

    settings['mem.ctrl.voltage']._value = 2
    lines, errors = get_volt_output()
    assert lines == ['over_voltage_sdram_c=2']
    assert errors == []

    settings['mem.io.voltage']._value = -4
    lines, errors = get_volt_output()
    assert lines == ['over_voltage_sdram_c=2', 'over_voltage_sdram_i=-4']
    assert errors == []

    settings['mem.io.voltage']._value = 2
    settings['mem.phy.voltage']._value = 2
    lines, errors = get_volt_output()
    assert lines == ['over_voltage_sdram=2']
    assert len(errors) == 2
    assert all(isinstance(exc, DelegatedOutput) for exc in errors)
    assert {exc.master for exc in errors} == {'mem.ctrl.voltage'}


def test_cpu_temp_limit():
    limit = CommandCPUTempLimit('cpu.temp.limit', command='temp_limit')

    assert limit.value == 85
    assert not limit.modified
    assert limit.hint == '°C'

    limit.validate()
    limit._value = 90
    with pytest.raises(ValueError):
        limit.validate()

    limit._value = limit.update(UserStr('80'))
    assert limit.modified
    assert limit.value == 80
    limit.validate()

    assert list(limit.output()) == ['temp_limit=80']
    config = [BootCommand('config.txt', 1, cond_all, 'temp_limit', '90', hdmi=0)]
    assert list(limit.extract(config)) == [(config[0], 85)]
    config = [BootCommand('config.txt', 1, cond_all, 'temp_limit', '80', hdmi=0)]
    assert list(limit.extract(config)) == [(config[0], 80)]


def test_cpu_freq():
    with mock.patch('pibootctl.setting.get_board_type') as get_board_type:
        settings = make_settings(
            CommandCPUFreqMax('cpu.max', command='arm_freq'),
            CommandCPUFreqMin('cpu.min', command='arm_freq_min'),
            CommandBool('cpu.turbo.force', command='force_turbo'))
        cpu_max = settings['cpu.max']
        cpu_min = settings['cpu.min']
        turbo = settings['cpu.turbo.force']

        get_board_type.return_value = None
        assert not turbo.modified
        assert not turbo.value
        assert not cpu_min.modified
        assert not cpu_max.modified
        assert cpu_min.hint == cpu_max.hint == 'MHz'
        assert (cpu_min.default, cpu_max.default) == (0, 0)

        get_board_type.return_value = 'pi0'
        assert (cpu_min.default, cpu_max.default) == (700, 1000)

        get_board_type.return_value = 'pi1'
        assert (cpu_min.default, cpu_max.default) == (700, 700)

        get_board_type.return_value = 'pi2'
        assert (cpu_min.default, cpu_max.default) == (600, 900)

        get_board_type.return_value = 'pi3'
        assert (cpu_min.default, cpu_max.default) == (600, 1200)

        get_board_type.return_value = 'pi3+'
        assert (cpu_min.default, cpu_max.default) == (600, 1400)

        get_board_type.return_value = 'pi4'
        assert (cpu_min.default, cpu_max.default) == (600, 1500)
        cpu_min.validate()
        cpu_max.validate()

        # Turbo locks min to max
        turbo._value = True
        assert (cpu_min.default, cpu_max.default) == (1500, 1500)
        cpu_min.validate()
        cpu_max.validate()

        # ... on all models
        get_board_type.return_value = 'pi3'
        assert (cpu_min.default, cpu_max.default) == (1200, 1200)
        cpu_min.validate()
        cpu_max.validate()

        # max can't be less than min
        turbo._value = False
        cpu_max._value = 600
        cpu_min._value = 1200
        with pytest.raises(ValueError):
            cpu_max.validate()


def test_gpu_freq():
    with mock.patch('pibootctl.setting.get_board_types') as get_board_types, \
            mock.patch('pibootctl.setting.get_board_type') as get_board_type:
        # There are an absolute ton of cross-dependencies on GPU frequencies:
        # between the different blocks, the enabled video-outs (on the 4), and
        # whether or not mini-UART serial is enabled (which in turn depends on
        # Bluetooth) ... urgh!
        settings = make_settings(
            CommandCoreFreqMax('gpu.core.frequency.max', commands=('core_freq', 'gpu_freq')),
            CommandCoreFreqMin('gpu.core.frequency.min', commands=('core_freq_min', 'gpu_freq_min')),
            CommandGPUFreqMax('gpu.h264.frequency.max', commands=('h264_freq', 'gpu_freq')),
            CommandGPUFreqMin('gpu.h264.frequency.min', commands=('h264_freq_min', 'gpu_freq_min')),
            CommandGPUFreqMax('gpu.isp.frequency.max', commands=('isp_freq', 'gpu_freq')),
            CommandGPUFreqMin('gpu.isp.frequency.min', commands=('isp_freq_min', 'gpu_freq_min')),
            CommandGPUFreqMax('gpu.v3d.frequency.max', commands=('v3d_freq', 'gpu_freq')),
            CommandGPUFreqMin('gpu.v3d.frequency.min', commands=('v3d_freq_min', 'gpu_freq_min')),
            CommandHEVCFreqMax('gpu.hevc.frequency.max', commands=('hevc_freq', 'gpu_freq')),
            CommandHEVCFreqMin('gpu.hevc.frequency.min', commands=('hevc_freq_min', 'gpu_freq_min')),
            CommandBool('cpu.turbo.force', command='force_turbo'),
            CommandBool('video.hdmi.4kp60', command='hdmi_enable_4kp60'),
            CommandTVOut('video.tv.enabled', command='enable_tvout'),
            OverlayBluetoothEnabled('bluetooth.enabled'),
            OverlaySerialUART('serial.uart'),
            CommandSerialEnabled('serial.enabled', command='enable_uart'))

        get_board_type.return_value = None
        get_board_types.return_value = set()
        assert settings['serial.enabled'].value
        assert settings['serial.uart'].value == 0
        assert not settings['video.tv.enabled'].modified
        assert settings['video.tv.enabled'].value
        assert not settings['video.hdmi.4kp60'].modified
        assert not settings['cpu.turbo.force'].value
        assert not settings['gpu.core.frequency.min'].modified
        assert not settings['gpu.core.frequency.max'].modified
        for setting in settings.values():
            if 'frequency' in setting.name:
                assert setting.hint == 'MHz'
                assert setting.default == 0

        get_board_type.return_value = 'pi0w'
        get_board_types.return_value = {'pi0', 'pi0w'}
        assert (
            settings['gpu.core.frequency.min'].value,
            settings['gpu.core.frequency.max'].value,
        ) == (250, 400)
        assert (
            settings['gpu.h264.frequency.min'].value,
            settings['gpu.h264.frequency.max'].value,
        ) == (250, 300)

        get_board_type.return_value = 'pi2'
        get_board_types.return_value = {'pi2'}
        assert (
            settings['gpu.core.frequency.min'].value,
            settings['gpu.core.frequency.max'].value,
        ) == (250, 250)
        assert (
            settings['gpu.h264.frequency.min'].value,
            settings['gpu.h264.frequency.max'].value,
        ) == (250, 250)
        assert (
            settings['gpu.hevc.frequency.min'].value,
            settings['gpu.hevc.frequency.max'].value,
        ) == (0, 0)

        get_board_type.return_value = 'pi4'
        get_board_types.return_value = {'pi4'}
        assert not settings['video.tv.enabled'].modified
        assert not settings['video.tv.enabled'].value
        assert (
            settings['gpu.core.frequency.min'].value,
            settings['gpu.core.frequency.max'].value,
        ) == (250, 500)
        assert (
            settings['gpu.h264.frequency.min'].value,
            settings['gpu.h264.frequency.max'].value,
        ) == (500, 500)
        assert (
            settings['gpu.hevc.frequency.min'].value,
            settings['gpu.hevc.frequency.max'].value,
        ) == (500, 500)

        # Turbo locks min to max
        settings['cpu.turbo.force']._value = True
        assert (
            settings['gpu.core.frequency.min'].value,
            settings['gpu.core.frequency.max'].value,
        ) == (500, 500)
        settings['gpu.h264.frequency.max']._value = 600
        assert (
            settings['gpu.h264.frequency.min'].value,
            settings['gpu.h264.frequency.max'].value,
        ) == (600, 600)
        settings['gpu.h264.frequency.max']._value = None

        # Serial over mini-UART locks core frequency
        settings['cpu.turbo.force']._value = None
        settings['serial.enabled']._value = True
        assert settings['serial.uart'].value == 1
        assert (
            settings['gpu.core.frequency.min'].default,
            settings['gpu.core.frequency.max'].default,
        ) == (250, 250)

        # TV lowers max
        settings['serial.enabled']._value = None
        settings['video.tv.enabled']._value = True
        settings['video.tv.enabled'].validate()
        settings['gpu.core.frequency.max'].validate()
        assert (
            settings['gpu.core.frequency.min'].default,
            settings['gpu.core.frequency.max'].default,
        ) == (250, 360)

        # Can't have TV and HDMI4kp60
        settings['video.hdmi.4kp60']._value = True
        with pytest.raises(ValueError):
            settings['video.tv.enabled'].validate()

        # 4kp60 raises min and max
        settings['video.tv.enabled']._value = False
        settings['video.tv.enabled'].validate()
        settings['gpu.core.frequency.max'].validate()
        assert (
            settings['gpu.core.frequency.min'].default,
            settings['gpu.core.frequency.max'].default,
        ) == (275, 550)

        # max can't be less than min
        settings['gpu.core.frequency.max']._value = 250
        with pytest.raises(ValueError):
            settings['gpu.core.frequency.max'].validate()
        settings['gpu.h264.frequency.max']._value = 250
        with pytest.raises(ValueError):
            settings['gpu.h264.frequency.max'].validate()


def test_gpu_freq_output():
    with mock.patch('pibootctl.setting.get_board_types') as get_board_types, \
            mock.patch('pibootctl.setting.get_board_type') as get_board_type:
        settings = make_settings(
            CommandCoreFreqMax('gpu.core.frequency.max', commands=('core_freq', 'gpu_freq')),
            CommandCoreFreqMin('gpu.core.frequency.min', commands=('core_freq_min', 'gpu_freq_min')),
            CommandGPUFreqMax('gpu.h264.frequency.max', commands=('h264_freq', 'gpu_freq')),
            CommandGPUFreqMin('gpu.h264.frequency.min', commands=('h264_freq_min', 'gpu_freq_min')),
            CommandGPUFreqMax('gpu.isp.frequency.max', commands=('isp_freq', 'gpu_freq')),
            CommandGPUFreqMin('gpu.isp.frequency.min', commands=('isp_freq_min', 'gpu_freq_min')),
            CommandGPUFreqMax('gpu.v3d.frequency.max', commands=('v3d_freq', 'gpu_freq')),
            CommandGPUFreqMin('gpu.v3d.frequency.min', commands=('v3d_freq_min', 'gpu_freq_min')),
            CommandHEVCFreqMax('gpu.hevc.frequency.max', commands=('hevc_freq', 'gpu_freq')),
            CommandHEVCFreqMin('gpu.hevc.frequency.min', commands=('hevc_freq_min', 'gpu_freq_min')),
            CommandBool('cpu.turbo.force', command='force_turbo'),
            OverlayBluetoothEnabled('bluetooth.enabled'),
            OverlaySerialUART('serial.uart'),
            CommandSerialEnabled('serial.enabled', command='enable_uart'))

        def get_gpu_output():
            lines = []
            errors = []
            for setting in sorted(settings.values(), key=attrgetter('key')):
                if setting.name.startswith('gpu.'):
                    try:
                        lines.extend(setting.output())
                    except DelegatedOutput as exc:
                        errors.append(exc)
            return lines, errors

        get_board_type.return_value = None
        get_board_types.return_value = set()
        lines, errors = get_gpu_output()
        assert lines == []
        assert errors == []

        get_board_type.return_value = 'pi3'
        get_board_types.return_value = {'pi3'}
        settings['gpu.h264.frequency.max']._value = 600
        lines, errors = get_gpu_output()
        assert lines == ['h264_freq=600']
        assert errors == []

        settings['gpu.core.frequency.max']._value = 600
        lines, errors = get_gpu_output()
        assert lines == ['core_freq=600', 'h264_freq=600']
        assert errors == []

        settings['gpu.isp.frequency.max']._value = 600
        settings['gpu.v3d.frequency.max']._value = 600
        settings['gpu.hevc.frequency.max']._value = 600
        lines, errors = get_gpu_output()
        assert lines == ['gpu_freq=600']
        assert len(errors) == 4
        assert all(isinstance(exc, DelegatedOutput) for exc in errors)
        assert {exc.master for exc in errors} == {'gpu.core.frequency.max'}

        settings['gpu.core.frequency.min']._value = 400
        settings['gpu.h264.frequency.min']._value = 400
        lines, errors = get_gpu_output()
        assert lines == ['gpu_freq=600', 'core_freq_min=400', 'h264_freq_min=400']
        assert len(errors) == 4
        assert all(isinstance(exc, DelegatedOutput) for exc in errors)
        assert {exc.master for exc in errors} == {'gpu.core.frequency.max'}

        settings['gpu.isp.frequency.min']._value = 400
        settings['gpu.v3d.frequency.min']._value = 400
        settings['gpu.hevc.frequency.min']._value = 400
        lines, errors = get_gpu_output()
        assert lines == ['gpu_freq=600', 'gpu_freq_min=400']
        assert len(errors) == 8
        assert all(isinstance(exc, DelegatedOutput) for exc in errors)
        assert {exc.master for exc in errors} == {
            'gpu.core.frequency.max', 'gpu.core.frequency.min'}


def test_gpu_mem():
    with mock.patch('pibootctl.setting.get_board_mem') as get_board_mem:
        mem = CommandGPUMem(
            'gpu.mem', default=64,
            commands=('gpu_mem', 'gpu_mem_256', 'gpu_mem_512', 'gpu_mem_1024'))
        assert mem.hint == 'Mb'

        config = [
            BootCommand('config.txt', 1, cond_all, 'gpu_mem_1024', '256', hdmi=0),
            BootCommand('config.txt', 2, cond_all, 'gpu_mem_512', '192', hdmi=0),
            BootCommand('config.txt', 3, cond_all, 'gpu_mem', '96', hdmi=0),
            BootCommand('config.txt', 4, cond_all, 'gpu_mem_256', '64', hdmi=0),
            BootCommand('config.txt', 5, cond_all, 'gpu_mem', 'a0', hdmi=0),
        ]

        with warnings.catch_warnings(record=True) as w:
            get_board_mem.return_value = 1024
            assert list(mem.extract(config)) == [
                (config[0], 256),
                (config[2], 256),
                (config[4], 256),
            ]
            assert len(w) == 1
            assert issubclass(w[0].category, ParseWarning)
        mem._value = 8
        with pytest.raises(ValueError):
            mem.validate()

        with warnings.catch_warnings(record=True) as w:
            get_board_mem.return_value = 512
            assert list(mem.extract(config)) == [
                (config[1], 192),
                (config[2], 192),
                (config[4], 192),
            ]
            assert len(w) == 1
            assert issubclass(w[0].category, ParseWarning)
        mem._value = 256
        mem.validate()

        with warnings.catch_warnings(record=True) as w:
            get_board_mem.return_value = 256
            assert list(mem.extract(config)) == [
                (config[2], 96),
                (config[3], 64),
                (config[4], 64),
            ]
            assert len(w) == 1
            assert issubclass(w[0].category, ParseWarning)
        mem._value = 256
        with pytest.raises(ValueError):
            mem.validate()


def test_total_mem():
    with mock.patch('pibootctl.setting.get_board_mem') as get_board_mem:
        mem = CommandTotalMem('total.mem', command='total_mem')
        assert mem.hint == 'Mb'

        config = [
            BootCommand('config.txt', 1, cond_all, 'total_mem', '256', hdmi=0),
            BootCommand('syscfg.txt', 1, cond_all, 'total_mem', '512', hdmi=0),
        ]

        get_board_mem.return_value = 1024
        assert list(mem.extract(config)) == [(config[0], 256)]
        mem._value = 8
        with pytest.raises(ValueError):
            mem.validate()


def test_overlay_dwc2():
    with mock.patch('pibootctl.setting.get_board_type') as get_board_type:
        settings = make_settings(OverlayDWC2('usb.dwc2.enabled'))
        dwc2 = settings['usb.dwc2.enabled']

        get_board_type.return_value = 'pi2'
        assert not dwc2.default
        assert not dwc2.value
        dwc2.validate()

        get_board_type.return_value = 'pi0w'
        assert dwc2.default
        assert dwc2.value
        dwc2._value = dwc2.update(UserStr('no'))
        assert not dwc2.value
        dwc2.validate()


def test_overlay_dwc2_extract():
    settings = make_settings(OverlayDWC2('usb.dwc2.enabled'))
    dwc2 = settings['usb.dwc2.enabled']
    config = [BootOverlay('config.txt', 1, cond_all, 'miniuart-bt')]
    assert list(dwc2.extract(config)) == []
    config = [BootOverlay('config.txt', 1, cond_all, 'dwc-otg')]
    assert list(dwc2.extract(config)) == [(config[0], False)]
    config = [BootOverlay('config.txt', 1, cond_all, 'dwc2')]
    assert list(dwc2.extract(config)) == [(config[0], True)]


def test_overlay_dwc2_output():
    settings = make_settings(OverlayDWC2('usb.dwc2.enabled'))
    dwc2 = settings['usb.dwc2.enabled']
    assert list(dwc2.output()) == []
    dwc2._value = False
    assert list(dwc2.output()) == ['dtoverlay=dwc-otg']
    dwc2._value = True
    assert list(dwc2.output()) == ['dtoverlay=dwc2']


def test_overlay_kms():
    settings = make_settings(OverlayKMS('video.firmware.mode'))
    kms = settings['video.firmware.mode']

    assert kms.default == 'legacy'
    assert kms.value == 'legacy'
    assert kms.hint == 'no KMS'
    kms.validate()

    kms._value = kms.update('fkms')
    assert kms.hint == 'Fake KMS'
    kms.validate()

    kms._value = 'blah'
    with pytest.raises(ValueError):
        kms.validate()


def test_overlay_kms_extract():
    settings = make_settings(OverlayKMS('video.firmware.mode'))
    kms = settings['video.firmware.mode']
    config = [BootOverlay('config.txt', 1, cond_all, 'miniuart-bt')]
    assert list(kms.extract(config)) == []
    config = [BootOverlay('config.txt', 1, cond_all, 'vc4-kms-v3d')]
    assert list(kms.extract(config)) == [(config[0], 'kms')]
    config = [BootOverlay('config.txt', 1, cond_all, 'vc4-fkms-v3d')]
    assert list(kms.extract(config)) == [(config[0], 'fkms')]


def test_overlay_kms_output():
    settings = make_settings(OverlayKMS('video.firmware.mode'))
    kms = settings['video.firmware.mode']
    assert list(kms.output()) == []
    kms._value = 'fkms'
    assert list(kms.output()) == ['dtoverlay=vc4-fkms-v3d']
    kms._value = 'kms'
    assert list(kms.output()) == ['dtoverlay=vc4-kms-v3d']


def test_output_order():
    settings = Settings()
    settings['spi.enabled']._value = True
    settings['i2c.enabled']._value = True
    settings['bluetooth.enabled']._value = False
    settings['boot.initramfs.address']._value = -1
    settings['boot.initramfs.filename']._value = ['initrd.img']

    def get_output():
        lines = []
        errors = []
        for setting in sorted(settings.values(), key=attrgetter('key')):
            try:
                lines.extend(setting.output())
            except DelegatedOutput as exc:
                errors.append(exc)
        return lines, errors

    lines, errors = get_output()
    assert lines == [
        'initramfs initrd.img followkernel',
        # base overlay params must come first
        'dtparam=i2c_arm=on',
        'dtparam=spi=on',
        'dtoverlay=disable-bt',
    ]
    assert len(errors) == 1
    assert isinstance(errors[0], DelegatedOutput)
    assert errors[0].master == 'boot.initramfs.filename'


def test_video_license():
    lic = CommandVideoLicense('video.license.mpg2', command='decode_MPG2')

    config = [
        BootCommand('config.txt', 1, cond_all, 'decode_MPG2', '0x12345678', hdmi=0),
    ]

    assert list(lic.extract(config)) == [(config[0], ['0x12345678'])]

    assert list(lic.output()) == []
    lic._value = lic.update(UserStr('1,2,3'))
    assert lic.value == ['1', '2', '3']
    assert list(lic.output()) == ['decode_MPG2=1,2,3']
    lic._value = [0] * 10
    with pytest.raises(ValueError):
        lic.validate()


def test_gpio_settings():
    s = make_settings(*(
        spec
        for index in range(28)
        for spec in (
            CommandGPIOMode('gpio{}.mode'.format(index), command='gpio', index=index),
            CommandGPIOState('gpio{}.state'.format(index), command='gpio', index=index),
        )
    ))

    config = [
        BootCommand('config.txt', 1, cond_all, 'gpio', '2,5-7=op,dh'),
        BootCommand('config.txt', 2, cond_all, 'gpio', '2,3=ip,op,ip,pu'),
        BootCommand('config.txt', 3, cond_all, 'gpio', '4,0xf=ip'),  # only applies to 4
        BootCommand('config.txt', 4, cond_all, 'gpio', '0-7=ip,foo'),  # ignored
    ]

    with warnings.catch_warnings(record=True) as w:
        assert list(s['gpio0.mode'].extract(config)) == []
        assert list(s['gpio0.state'].extract(config)) == []
        assert list(s['gpio2.mode'].extract(config)) == [
            (config[0], 'out'),
            (config[1], 'in'),
        ]
        assert list(s['gpio2.state'].extract(config)) == [
            (config[0], 'high'),
            (config[1], 'up'),
        ]
        assert len(w) == 2
        assert issubclass(w[0].category, ParseWarning)
        assert issubclass(w[1].category, ParseWarning)

    for g in (2, 3, 4):
        s['gpio{}.mode'.format(g)]._value = 'in'
        s['gpio{}.state'.format(g)]._value = 'up'
    s['gpio4.state']._value = 'none'
    for g in (5, 6, 7):
        s['gpio{}.mode'.format(g)]._value = 'out'
        s['gpio{}.state'.format(g)]._value = 'high'
    assert set(s['gpio0.mode'].output()) == {
        'gpio=2,3=ip,pu',
        'gpio=4=ip,np',
        'gpio=5-7=op,dh',
    }
    assert list(s['gpio0.state'].output()) == []
    with pytest.raises(DelegatedOutput) as exc:
        list(s['gpio2.mode'].output())
        assert exc.value.master == 'gpio0.mode'
    with pytest.raises(DelegatedOutput) as exc:
        list(s['gpio2.state'].output())
        assert exc.value.master == 'gpio0.mode'


def test_parse_gpio():
    with pytest.raises(ValueError):
        parse_gpio('0')
    with pytest.raises(ValueError):
        parse_gpio('4=foo')
    assert parse_gpio('0=op,dh') == ({0}, 'out', 'high')
    assert parse_gpio('0=op,np') == ({0}, 'out', 'low')
    assert parse_gpio('0=ip,dh') == ({0}, 'in', 'none')
    assert parse_gpio('1,2- 3=op,dh') == ({1}, 'out', 'high')
    assert parse_gpio('1,2-a=op,dh') == ({1}, 'out', 'high')
    assert parse_gpio('1,2--3=op,dh') == ({1}, 'out', 'high')
    assert parse_gpio('1,2, 3=op,dh') == ({1, 2}, 'out', 'high')
    assert parse_gpio('1,2,-3=op,dh') == ({1, 2}, 'out', 'high')
    assert parse_gpio('1,2,-3--4=op,dh') == ({1, 2}, 'out', 'high')
