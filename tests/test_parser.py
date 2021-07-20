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

import zipfile
import warnings
from pathlib import Path
from unittest import mock
from hashlib import sha1
from datetime import datetime

import pytest

from pibootctl.parser import *


cond_all = BootConditions()
cond_none = cond_all.evaluate('none')


def test_coalesce():
    assert coalesce(1) == 1
    assert coalesce(None, 1) == 1
    assert coalesce(None, None, 1) == 1
    assert coalesce() is None


def test_str():
    assert str(BootSection('config.txt', 1, cond_all, 'all')) == '[all]'
    assert str(BootCommand(
        'config.txt', 1, cond_all, 'initramfs', ('initrd.img', 'followkernel')
    )) == 'initramfs initrd.img followkernel'
    assert str(BootCommand('config.txt', 1, cond_all, 'hdmi_group', '1')) == 'hdmi_group=1'
    assert str(BootCommand('config.txt', 1, cond_all, 'hdmi_group', '2', 1)) == 'hdmi_group:1=2'
    assert str(BootInclude('config.txt', 1, cond_all, 'syscfg.txt')) == 'include syscfg.txt'
    assert str(BootOverlay('config.txt', 1, cond_all, 'foo')) == 'dtoverlay=foo'
    assert str(BootParam('config.txt', 1, cond_all, 'base', 'spi', 'on')) == 'dtparam=spi=on'


def test_repr():
    assert repr(BootComment('config.txt', 2, cond_all)) == (
        "BootComment(filename='config.txt', linenum=2, comment=None)")
    assert repr(BootSection('config.txt', 1, cond_all, 'all')) == (
        "BootSection(filename='config.txt', linenum=1, section='all')")
    assert repr(BootCommand(
        'config.txt', 1, cond_all, 'initramfs', ('initrd.img', 'followkernel')
    )) == (
        "BootCommand(filename='config.txt', linenum=1, "
        "command='initramfs', params=('initrd.img', 'followkernel'), "
        "hdmi=None)"
    )
    assert repr(BootCommand('config.txt', 1, cond_all, 'hdmi_group', '1')) == (
        "BootCommand(filename='config.txt', linenum=1, "
        "command='hdmi_group', params='1', hdmi=None)")
    assert repr(BootCommand('config.txt', 1, cond_all, 'hdmi_group', '2', 1)) == (
        "BootCommand(filename='config.txt', linenum=1, "
        "command='hdmi_group', params='2', hdmi=1)")
    assert repr(BootInclude('config.txt', 1, cond_all, 'syscfg.txt')) == (
        "BootInclude(filename='config.txt', linenum=1, "
        "include='syscfg.txt')")
    assert repr(BootOverlay('config.txt', 1, cond_all, 'foo')) == (
        "BootOverlay(filename='config.txt', linenum=1, overlay='foo')")
    assert repr(BootParam('config.txt', 1, cond_all, 'base', 'spi', 'on')) == (
        "BootParam(filename='config.txt', linenum=1, overlay='base', "
        "param='spi', value='on')")


def test_bootline_comparisons():
    assert BootComment('config.txt', 1, cond_all, 'foo') != 1
    assert BootComment('config.txt', 1, cond_all, 'foo') != \
           BootComment('config.txt', 2, cond_all, 'foo')
    assert BootComment('config.txt', 1, cond_all, 'foo') != \
           BootComment('config.txt', 1, cond_none, 'foo')
    assert BootComment('config.txt', 1, cond_all, 'foo') != \
           BootComment('config.txt', 1, cond_all, 'bar')
    assert BootComment('config.txt', 1, cond_all, 'foo') == \
           BootComment('config.txt', 1, cond_all, 'foo')


def test_bootsection_comparisons():
    assert BootComment('config.txt', 1, cond_all, 'foo') != \
           BootSection('config.txt', 1, cond_all, 'all')
    assert BootSection('config.txt', 1, cond_all, 'all') != \
           BootComment('config.txt', 1, cond_all, 'foo')
    assert BootSection('config.txt', 1, cond_all, 'foo') != \
           BootSection('config.txt', 1, cond_all, 'bar')


def test_bootcommand_comparisons():
    assert BootCommand('config.txt', 1, cond_all, 'disable_overscan', '1') != \
           BootComment('config.txt', 1, cond_all, 'foo')
    assert BootCommand('config.txt', 1, cond_all, 'disable_overscan', '1', 0) != \
           BootCommand('config.txt', 1, cond_all, 'disable_overscan', '1', 1)
    assert BootCommand('config.txt', 1, cond_all, 'disable_overscan', '1') != \
           BootCommand('config.txt', 1, cond_all, 'disable_overscan', '0')
    assert BootCommand('config.txt', 1, cond_all, 'hdmi_mode', '1') != \
           BootCommand('config.txt', 1, cond_all, 'disable_overscan', '1')


def test_bootinclude_comparisons():
    assert BootInclude('config.txt', 1, cond_all, 'foo.txt') != \
           BootComment('config.txt', 1, cond_all, 'foo')
    assert BootInclude('config.txt', 1, cond_all, 'foo.txt') != \
           BootInclude('config.txt', 1, cond_all, 'bar.txt')


def test_bootoverlay_comparisons():
    assert BootOverlay('config.txt', 1, cond_all, 'gpio-shutdown') != \
           BootComment('config.txt', 1, cond_all, 'foo')
    assert BootOverlay('config.txt', 1, cond_all, 'gpio-shutdown') != \
           BootOverlay('config.txt', 1, cond_all, 'gpio-poweroff')
    assert BootParam('config.txt', 1, cond_all, 'gpio-shutdown', 'gpio_pin', 4) != \
           BootOverlay('config.txt', 1, cond_all, 'gpio-shutdown')
    assert BootParam('config.txt', 1, cond_all, 'gpio-shutdown', 'gpio_pin', 4) != \
           BootParam('config.txt', 1, cond_all, 'gpio-poweroff', 'gpiopin', 4)
    assert BootParam('config.txt', 1, cond_all, 'gpio-shutdown', 'gpio_pin', 4) != \
           BootParam('config.txt', 1, cond_all, 'gpio-shutdown', 'gpio_pin', 17)


def test_bootconditions_comparisons():
    cond_pi3 = cond_all.evaluate('pi3')
    cond_pi3p = cond_all.evaluate('pi3+')
    cond_pi400 = cond_all.evaluate('pi400')
    cond_cm4 = cond_all.evaluate('cm4')
    cond_pi4 = cond_all.evaluate('pi4')
    cond_pi4000 = cond_all.evaluate('pi4000')
    cond_gpio = cond_pi3.evaluate('gpio4=1')
    cond_edid = cond_pi3.evaluate('EDID=foo')
    cond_hdmi = cond_pi3.evaluate('HDMI:1')
    cond_serial = cond_pi3.evaluate('0xf000000d')
    assert cond_all != 1
    with pytest.raises(TypeError):
        cond_all < 1
    with pytest.raises(TypeError):
        cond_all > 1
    assert cond_pi3 != cond_all
    assert cond_pi3 != cond_gpio
    assert cond_pi3 != cond_edid
    assert cond_pi3 != cond_hdmi
    assert cond_pi3 != cond_serial
    assert cond_pi3 <= cond_all
    assert cond_pi3 < cond_all
    assert cond_pi3p != cond_pi3
    assert cond_pi3p < cond_pi3
    assert cond_pi400 < cond_pi4
    assert cond_cm4 < cond_pi4
    assert cond_gpio < cond_pi3
    assert cond_edid < cond_pi3
    assert cond_hdmi < cond_pi3
    assert cond_serial < cond_pi3
    assert cond_pi3 > cond_pi3p
    assert cond_pi3 > cond_gpio
    assert cond_pi3 > cond_serial
    assert cond_pi3 > cond_edid
    assert cond_pi3 > cond_hdmi
    assert cond_pi4 > cond_pi400
    assert cond_pi4 > cond_cm4
    assert cond_all == cond_pi4000
    # It's a partial ordering
    assert not cond_pi400 < cond_cm4
    assert not cond_cm4 < cond_pi400


def test_bootconditions_generate():
    cond_pi3 = cond_all.evaluate('pi3')
    cond_pi3p = cond_all.evaluate('pi3+')
    cond_gpio = cond_pi3.evaluate('gpio4=1')
    cond_edid = cond_pi3.evaluate('EDID=foo')
    cond_hdmi = cond_pi3.evaluate('HDMI:1')
    cond_serial = cond_pi3.evaluate('0xf000000d')
    assert list(cond_pi3.generate()) == ['[pi3]']
    assert list(cond_pi3p.generate()) == ['[pi3+]']
    assert list(cond_gpio.generate()) == ['[pi3]', '[gpio4=1]']
    assert list(cond_edid.generate()) == ['[pi3]', '[EDID=foo]']
    assert list(cond_hdmi.generate()) == ['[pi3]', '[HDMI:1]']
    assert list(cond_serial.generate()) == ['[pi3]', '[0xF000000D]']


def test_parse_basic(tmpdir):
    tmpdir.join('config.txt').write("""\
# This is a comment
kernel=vmlinuz
initramfs initrd.img followkernel
device_tree_address=0x3000000
dtoverlay=vc4-fkms-v3d
""")
    p = BootParser(str(tmpdir))
    p.parse()
    assert p.config == [
        BootComment('config.txt', 1, cond_all, comment=' This is a comment'),
        BootCommand('config.txt', 2, cond_all, 'kernel', 'vmlinuz'),
        BootCommand('config.txt', 3, cond_all, 'initramfs', ('initrd.img', 'followkernel')),
        BootCommand('config.txt', 4, cond_all, 'device_tree_address', '0x3000000'),
        BootOverlay('config.txt', 5, cond_all, 'vc4-fkms-v3d'),
    ]


def test_parse_invalid(tmpdir):
    tmpdir.join('config.txt').write("""\
# This is a comment
This is not
""")
    p = BootParser(str(tmpdir))
    with pytest.warns(BootInvalid) as w:
        p.parse()
        assert p.config == [
            BootComment('config.txt', 1, cond_all, comment=' This is a comment'),
        ]
        assert len(w) == 1
        assert w[0].message.args[0] == 'config.txt:2 invalid line'


def test_parse_overlay_and_params(tmpdir):
    tmpdir.join('config.txt').write("""\
dtparam=audio=on,i2c=on,i2c_baudrate=400000
dtparam=spi,i2c0
dtoverlay=lirc-rpi:gpio_out_pin=16,gpio_in_pin=17,gpio_in_pull=down
""")
    p = BootParser(str(tmpdir))
    p.parse()
    assert p.config == [
        BootParam('config.txt', 1, cond_all, 'base', 'audio', 'on'),
        BootParam('config.txt', 1, cond_all, 'base', 'i2c_arm', 'on'),
        BootParam('config.txt', 1, cond_all, 'base', 'i2c_arm_baudrate', '400000'),
        BootParam('config.txt', 2, cond_all, 'base', 'spi', 'on'),
        BootParam('config.txt', 2, cond_all, 'base', 'i2c_vc', 'on'),
        BootOverlay('config.txt', 3, cond_all, 'lirc-rpi'),
        BootParam('config.txt', 3, cond_all, 'lirc-rpi', 'gpio_out_pin', '16'),
        BootParam('config.txt', 3, cond_all, 'lirc-rpi', 'gpio_in_pin', '17'),
        BootParam('config.txt', 3, cond_all, 'lirc-rpi', 'gpio_in_pull', 'down'),
    ]


def test_parse_include(tmpdir):
    tmpdir.join('config.txt').write("""\
# This is a comment
[none]
dtoverlay=vc4-fkms-v3d

[all]
dtoverlay=foo
include syscfg.txt
""")
    tmpdir.join('syscfg.txt').write("""\
dtparam=i2c=on
dtparam=spi=on

hdmi_group=1
hdmi_mode=4
""")
    p = BootParser(str(tmpdir))
    p.parse()
    assert p.config == [
        BootComment('config.txt', 1, cond_all, comment=' This is a comment'),
        BootSection('config.txt', 2, cond_none, 'none'),
        BootOverlay('config.txt', 3, cond_none, 'vc4-fkms-v3d'),
        BootSection('config.txt', 5, cond_all, 'all'),
        BootOverlay('config.txt', 6, cond_all, 'foo'),
        BootInclude('config.txt', 7, cond_all, 'syscfg.txt'),
        BootParam('syscfg.txt', 1, cond_all, 'base', 'i2c_arm', 'on'),
        BootParam('syscfg.txt', 2, cond_all, 'base', 'spi', 'on'),
        BootCommand('syscfg.txt', 4, cond_all, 'hdmi_group', '1'),
        BootCommand('syscfg.txt', 5, cond_all, 'hdmi_mode', '4'),
    ]


def test_parse_suppressed_includes(tmpdir):
    tmpdir.join('config.txt').write("""\
# This is a comment
[none]
dtoverlay=vc4-fkms-v3d
include inc1.txt

[all]
dtoverlay=foo
""")
    tmpdir.join('inc1.txt').write("""\
[all]
dtparam=i2c=on
dtparam=spi=on
include inc2.txt
""")
    tmpdir.join('inc2.txt').write("""\
hdmi_group=1
hdmi_mode=4
""")
    p = BootParser(str(tmpdir))
    p.parse()
    cond_inc1 = cond_all._replace(suppress_count=1)
    cond_inc2 = cond_all._replace(suppress_count=2)
    assert p.config == [
        BootComment('config.txt', 1, cond_all, comment=' This is a comment'),
        BootSection('config.txt', 2, cond_none, 'none'),
        BootOverlay('config.txt', 3, cond_none, 'vc4-fkms-v3d'),
        BootInclude('config.txt', 4, cond_none, 'inc1.txt'),
        BootSection('inc1.txt', 1, cond_inc1, 'all'),
        BootParam('inc1.txt', 2, cond_inc1, 'base', 'i2c_arm', 'on'),
        BootParam('inc1.txt', 3, cond_inc1, 'base', 'spi', 'on'),
        BootInclude('inc1.txt', 4, cond_inc2, 'inc2.txt'),
        BootCommand('inc2.txt', 1, cond_inc2, 'hdmi_group', '1'),
        BootCommand('inc2.txt', 2, cond_inc2, 'hdmi_mode', '4'),
        BootSection('config.txt', 6, cond_all, 'all'),
        BootOverlay('config.txt', 7, cond_all, 'foo'),
    ]



def test_parse_hdmi_section(tmpdir):
    tmpdir.join('config.txt').write("""\
# This is a comment
hdmi_group=1
hdmi_mode=4

[HDMI:1]
hdmi_group=2
hdmi_mode=28

[HDMI:foo]
""")
    p = BootParser(str(tmpdir))
    p.parse()
    cond_hdmi1 = cond_all._replace(hdmi=1)
    assert p.config == [
        BootComment('config.txt', 1, cond_all, comment=' This is a comment'),
        BootCommand('config.txt', 2, cond_all, 'hdmi_group', '1'),
        BootCommand('config.txt', 3, cond_all, 'hdmi_mode', '4'),
        BootSection('config.txt', 5, cond_hdmi1, 'HDMI:1'),
        BootCommand('config.txt', 6, cond_hdmi1, 'hdmi_group', '2', 1),
        BootCommand('config.txt', 7, cond_hdmi1, 'hdmi_mode', '28', 1),
        BootSection('config.txt', 9, cond_hdmi1, 'HDMI:foo'),
    ]


def test_parse_hdmi_suffix(tmpdir):
    tmpdir.join('config.txt').write("""\
hdmi_group:0=1
hdmi_mode:1=4
hdmi_mode:a=4
""")
    p = BootParser(str(tmpdir))
    p.parse()
    assert p.config == [
        BootCommand('config.txt', 1, cond_all, 'hdmi_group', '1', 0),
        BootCommand('config.txt', 2, cond_all, 'hdmi_mode', '4', 1),
        BootCommand('config.txt', 3, cond_all, 'hdmi_mode', '4'),
    ]


def test_parse_edid_section(tmpdir):
    tmpdir.join('config.txt').write("""\
# This is a comment
[EDID=BNQ-BenQ_GW2270]
hdmi_group=1
hdmi_mode=16

[EDID=VSC-TD2220]
hdmi_group=1
hdmi_mode=4
""")
    p = BootParser(str(tmpdir))
    p.parse()
    cond_edid1 = cond_all._replace(edid='BNQ-BenQ_GW2270')
    cond_edid2 = cond_all._replace(edid='VSC-TD2220')
    assert p.config == [
        BootComment('config.txt', 1, cond_all, comment=' This is a comment'),
        BootSection('config.txt', 2, cond_edid1, 'EDID=BNQ-BenQ_GW2270'),
        BootCommand('config.txt', 3, cond_edid1, 'hdmi_group', '1'),
        BootCommand('config.txt', 4, cond_edid1, 'hdmi_mode', '16'),
        BootSection('config.txt', 6, cond_edid2, 'EDID=VSC-TD2220'),
        BootCommand('config.txt', 7, cond_edid2, 'hdmi_group', '1'),
        BootCommand('config.txt', 8, cond_edid2, 'hdmi_mode', '4'),
    ]


def test_parse_gpio_section(tmpdir):
    tmpdir.join('config.txt').write("""\
# This is a comment
[gpio4=1]
dtparam=audio=on

[gpiofoo=bar]
""")
    p = BootParser(str(tmpdir))
    p.parse()
    cond_gpio = cond_all._replace(gpio=(4, True))
    assert p.config == [
        BootComment('config.txt', 1, cond_all, comment=' This is a comment'),
        BootSection('config.txt', 2, cond_gpio, 'gpio4=1'),
        BootParam('config.txt', 3, cond_gpio, 'base', 'audio', 'on'),
        BootSection('config.txt', 5, cond_gpio, 'gpiofoo=bar'),
    ]


def test_parse_serial_bad_section(tmpdir):
    with mock.patch('pibootctl.parser.get_board_serial') as get_board_serial:
        tmpdir.join('config.txt').write("""\
# This is a comment
[0xwtf]
dtparam=audio=on
""")
        p = BootParser(str(tmpdir))
        p.parse()
        assert p.config == [
            BootComment('config.txt', 1, cond_all, comment=' This is a comment'),
            BootSection('config.txt', 2, cond_all, '0xwtf'),
            BootParam('config.txt', 3, cond_all, 'base', 'audio', 'on'),
        ]


def test_parse_unknown_section(tmpdir, recwarn):
    tmpdir.join('config.txt').write("""\
# This is a comment
[foo]
dtparam=audio=on
""")
    p = BootParser(str(tmpdir))
    p.parse()
    assert p.config == [
        BootComment('config.txt', 1, cond_all, comment=' This is a comment'),
        BootSection('config.txt', 2, cond_all, 'foo'),
        BootParam('config.txt', 3, cond_all, 'base', 'audio', 'on'),
    ]
    assert len(recwarn) == 1
    assert recwarn.pop(BootInvalid)


def test_parse_serial_section_match(tmpdir):
    with mock.patch('pibootctl.parser.get_board_serial') as get_board_serial:
        get_board_serial.return_value = 0xdeadd00d
        tmpdir.join('config.txt').write("""\
# This is a comment
[0xdeadd00d]
dtparam=audio=on
""")
        p = BootParser(str(tmpdir))
        p.parse()
        cond_serial = cond_all._replace(serial=0xdeadd00d)
        assert p.config == [
            BootComment('config.txt', 1, cond_all, comment=' This is a comment'),
            BootSection('config.txt', 2, cond_serial, '0xdeadd00d'),
            BootParam('config.txt', 3, cond_serial, 'base', 'audio', 'on'),
        ]
        assert cond_serial.enabled


def test_parse_serial_section_mismatch(tmpdir):
    with mock.patch('pibootctl.parser.get_board_serial') as get_board_serial:
        get_board_serial.return_value = 0xdeadd00d
        tmpdir.join('config.txt').write("""\
# This is a comment
[0x12345678]
dtparam=audio=on
""")
        p = BootParser(str(tmpdir))
        p.parse()
        cond_serial = cond_all._replace(serial=0x12345678)
        assert p.config == [
            BootComment('config.txt', 1, cond_all, comment=' This is a comment'),
            BootSection('config.txt', 2, cond_serial, '0x12345678'),
            BootParam('config.txt', 3, cond_serial, 'base', 'audio', 'on'),
        ]
        assert not cond_serial.enabled


def test_parse_pi_section(tmpdir):
    with mock.patch('pibootctl.parser.get_board_types') as get_board_types:
        get_board_types.return_value = {'pi3', 'pi3+'}
        tmpdir.join('config.txt').write("""\
# This is a comment
[pi2]
kernel=uboot_2.bin
[pi3]
kernel=uboot_3_32b.bin
[pi4]
kernel=uboot_4_32b.bin
[pi400]
""")
        p = BootParser(str(tmpdir))
        p.parse()
        cond_pi2 = cond_all._replace(pi='pi2')
        cond_pi3 = cond_all._replace(pi='pi3')
        cond_pi4 = cond_all._replace(pi='pi4')
        cond_pi400 = cond_all._replace(pi='pi400')
        assert p.config == [
            BootComment('config.txt', 1, cond_all, comment=' This is a comment'),
            BootSection('config.txt', 2, cond_pi2, 'pi2'),
            BootCommand('config.txt', 3, cond_pi2, 'kernel', 'uboot_2.bin'),
            BootSection('config.txt', 4, cond_pi3, 'pi3'),
            BootCommand('config.txt', 5, cond_pi3, 'kernel', 'uboot_3_32b.bin'),
            BootSection('config.txt', 6, cond_pi4, 'pi4'),
            BootCommand('config.txt', 7, cond_pi4, 'kernel', 'uboot_4_32b.bin'),
            BootSection('config.txt', 8, cond_pi400, 'pi400'),
        ]
        assert not cond_pi2.enabled
        assert not cond_pi4.enabled
        assert not cond_pi400.enabled
        assert cond_pi3.enabled


def test_parse_attr(tmpdir):
    tmpdir = Path(str(tmpdir))
    content = b"""\
# This is a comment
[pi2]
kernel=uboot_2.bin
[pi3]
kernel=uboot_3_32b.bin
[pi4]
kernel=uboot_4_32b.bin
"""
    with mock.patch('pibootctl.parser.get_board_types') as get_board_types:
        get_board_types.return_value = {'pi3', 'pi3+'}
        (tmpdir / 'config.txt').write_bytes(content)
        p = BootParser(tmpdir)
        p.parse()
        assert p.files == {
            'config.txt': BootFile(
                'config.txt',
                datetime.fromtimestamp((tmpdir / 'config.txt').stat().st_mtime),
                content, 'ascii', 'replace'
            )
        }
        h = sha1()
        h.update(content)
        assert p.hash == h.hexdigest().lower()


def test_parse_store(tmpdir):
    data1 = b"""\
# This is a comment
kernel=vmlinuz
device_tree_address=0x3000000
dtoverlay=vc4-fkms-v3d
"""
    data2 = b'quiet splash'
    with zipfile.ZipFile(str(tmpdir.join('stored.zip')), 'w') as arc:
        arc.writestr('config.txt', data1)
        arc.writestr('cmdline.txt', data2)
    h = hashlib.sha1()
    h.update(data1)
    h.update(data2)
    with zipfile.ZipFile(str(tmpdir.join('stored.zip')), 'r') as arc:
        p = BootParser(arc)
        p.parse()
        p.add('cmdline.txt')
        assert p.config == [
            BootComment('config.txt', 1, cond_all, comment=' This is a comment'),
            BootCommand('config.txt', 2, cond_all, 'kernel', 'vmlinuz'),
            BootCommand('config.txt', 3, cond_all, 'device_tree_address', '0x3000000'),
            BootOverlay('config.txt', 4, cond_all, 'vc4-fkms-v3d'),
        ]
        assert p.hash == h.hexdigest().lower()


def test_add_to_zip(tmpdir):
    tmpdir.join('config.txt').write("""\
# This is a comment
kernel=vmlinuz
device_tree_address=0x3000000
dtoverlay=vc4-fkms-v3d
""")
    tmpdir.join('cmdline.txt').write("quiet splash")
    p1 = BootParser(str(tmpdir))
    p1.parse()
    with zipfile.ZipFile(str(tmpdir.join('stored.zip')), 'w') as arc:
        for f in p1.files.values():
            f.add_to_zip(arc)
    with zipfile.ZipFile(str(tmpdir.join('stored.zip')), 'r') as arc:
        p2 = BootParser(arc)
        p2.parse()
        assert p1.hash == p2.hash
        assert p1.files.keys() == p2.files.keys()
        for f in p1.files:
            assert p1.files[f].content == p2.files[f].content


def test_parse_dict(tmpdir):
    tmpdir = Path(str(tmpdir))
    (tmpdir / 'config.txt').write_text("""\
# This is a comment
[all]
dtoverlay=foo
include syscfg.txt
""")
    (tmpdir / 'syscfg.txt').write_text("""\
dtparam=i2c=on
dtparam=spi=on
hdmi_group=1
hdmi_mode=4
""")
    (tmpdir / 'edid.dat').write_bytes(b'\x00\x00\x00\xFF')
    p1 = BootParser(tmpdir)
    p1.parse()
    p1.add('edid.dat')
    masked = p1.files.copy()
    del masked['syscfg.txt']
    p2 = BootParser(masked)
    p2.parse()
    p2.add('edid.dat')
    assert p2.config == [
        BootComment('config.txt', 1, cond_all, comment=' This is a comment'),
        BootSection('config.txt', 2, cond_all, 'all'),
        BootOverlay('config.txt', 3, cond_all, 'foo'),
        BootInclude('config.txt', 4, cond_all, 'syscfg.txt'),
    ]


def test_parse_empty(tmpdir):
    p = BootParser(str(tmpdir))
    p.parse()
    assert p.config == []
    assert p.hash == hashlib.sha1().hexdigest().lower()
