import zipfile
import warnings
from pathlib import Path
from unittest import mock
from hashlib import sha1
from datetime import datetime

import pytest

from pibootctl.parser import *


def test_str():
    assert str(BootSection('config.txt', 1, 'all')) == '[all]'
    assert str(BootCommand(
        'config.txt', 1, 'initramfs', ('initrd.img', 'followkernel')
    )) == 'initramfs initrd.img followkernel'
    assert str(BootCommand('config.txt', 1, 'hdmi_group', '1')) == 'hdmi_group=1'
    assert str(BootCommand('config.txt', 1, 'hdmi_group', '2', 1)) == 'hdmi_group:1=2'
    assert str(BootInclude('config.txt', 1, 'syscfg.txt')) == 'include syscfg.txt'
    assert str(BootOverlay('config.txt', 1, 'foo')) == 'dtoverlay=foo'
    assert str(BootParam('config.txt', 1, 'base', 'spi', 'on')) == 'dtparam=spi=on'


def test_repr():
    assert repr(BootLine('config.txt', 2)) == (
        "BootLine(path='config.txt', lineno=2)")
    assert repr(BootSection('config.txt', 1, 'all')) == (
        "BootSection(path='config.txt', lineno=1, section='all')")
    assert repr(BootCommand(
        'config.txt', 1, 'initramfs', ('initrd.img', 'followkernel')
    )) == (
        "BootCommand(path='config.txt', lineno=1, "
        "command='initramfs', params=('initrd.img', 'followkernel'), "
        "hdmi=None)"
    )
    assert repr(BootCommand('config.txt', 1, 'hdmi_group', '1')) == (
        "BootCommand(path='config.txt', lineno=1, "
        "command='hdmi_group', params='1', hdmi=None)")
    assert repr(BootCommand('config.txt', 1, 'hdmi_group', '2', 1)) == (
        "BootCommand(path='config.txt', lineno=1, "
        "command='hdmi_group', params='2', hdmi=1)")
    assert repr(BootInclude('config.txt', 1, 'syscfg.txt')) == (
        "BootInclude(path='config.txt', lineno=1, "
        "include='syscfg.txt')")
    assert repr(BootOverlay('config.txt', 1, 'foo')) == (
        "BootOverlay(path='config.txt', lineno=1, overlay='foo')")
    assert repr(BootParam('config.txt', 1, 'base', 'spi', 'on')) == (
        "BootParam(path='config.txt', lineno=1, overlay='base', "
        "param='spi', value='on')")


def test_parse_basic(tmpdir):
    tmpdir.join('config.txt').write("""# This is a comment
kernel=vmlinuz
initramfs initrd.img followkernel
device_tree_address=0x3000000
dtoverlay=vc4-fkms-v3d
""")
    p = BootParser(Path(str(tmpdir)))
    p.parse()
    assert p.config == [
        BootCommand('config.txt', 2, 'kernel', 'vmlinuz', 0),
        BootCommand('config.txt', 3, 'initramfs', ('initrd.img', 'followkernel')),
        BootCommand('config.txt', 4, 'device_tree_address', '0x3000000', 0),
        BootOverlay('config.txt', 5, 'vc4-fkms-v3d'),
    ]


def test_parse_invalid(tmpdir):
    tmpdir.join('config.txt').write("""# This is a comment
This is not
""")
    p = BootParser(Path(str(tmpdir)))
    with pytest.warns(BootInvalid) as w:
        p.parse()
        assert p.config == []
        assert len(w) == 1
        assert w[0].message.args[0] == 'config.txt:2 invalid line'


def test_parse_overlay_and_params(tmpdir):
    tmpdir.join('config.txt').write("""\
dtparam=audio=on,i2c=on,i2c_baudrate=400000
dtparam=spi,i2c0
dtoverlay=lirc-rpi:gpio_out_pin=16,gpio_in_pin=17,gpio_in_pull=down
""")
    p = BootParser(Path(str(tmpdir)))
    p.parse()
    assert p.config == [
        BootParam('config.txt', 1, 'base', 'audio', 'on'),
        BootParam('config.txt', 1, 'base', 'i2c_arm', 'on'),
        BootParam('config.txt', 1, 'base', 'i2c_arm_baudrate', '400000'),
        BootParam('config.txt', 2, 'base', 'spi', 'on'),
        BootParam('config.txt', 2, 'base', 'i2c_vc', 'on'),
        BootOverlay('config.txt', 3, 'lirc-rpi'),
        BootParam('config.txt', 3, 'lirc-rpi', 'gpio_out_pin', '16'),
        BootParam('config.txt', 3, 'lirc-rpi', 'gpio_in_pin', '17'),
        BootParam('config.txt', 3, 'lirc-rpi', 'gpio_in_pull', 'down'),
    ]


def test_parse_include(tmpdir):
    tmpdir.join('config.txt').write("""# This is a comment
[none]
dtoverlay=vc4-fkms-v3d

[all]
dtoverlay=foo
include syscfg.txt
""")
    tmpdir.join('syscfg.txt').write("""dtparam=i2c=on
dtparam=spi=on

hdmi_group=1
hdmi_mode=4
""")
    p = BootParser(Path(str(tmpdir)))
    p.parse()
    assert p.config == [
        BootSection('config.txt', 2, 'none'),
        BootSection('config.txt', 5, 'all'),
        BootOverlay('config.txt', 6, 'foo'),
        BootInclude('config.txt', 7, 'syscfg.txt'),
        BootParam('syscfg.txt', 1, 'base', 'i2c_arm', 'on'),
        BootParam('syscfg.txt', 2, 'base', 'spi', 'on'),
        BootCommand('syscfg.txt', 4, 'hdmi_group', '1', 0),
        BootCommand('syscfg.txt', 5, 'hdmi_mode', '4', 0),
    ]


def test_parse_hdmi_section(tmpdir):
    tmpdir.join('config.txt').write("""# This is a comment
hdmi_group=1
hdmi_mode=4

[HDMI:1]
hdmi_group=2
hdmi_mode=28
""")
    p = BootParser(Path(str(tmpdir)))
    p.parse()
    assert p.config == [
        BootCommand('config.txt', 2, 'hdmi_group', '1', 0),
        BootCommand('config.txt', 3, 'hdmi_mode', '4', 0),
        BootSection('config.txt', 5, 'HDMI:1'),
        BootCommand('config.txt', 6, 'hdmi_group', '2', 1),
        BootCommand('config.txt', 7, 'hdmi_mode', '28', 1),
    ]


def test_parse_hdmi_suffix(tmpdir):
    tmpdir.join('config.txt').write("""\
hdmi_group:0=1
hdmi_mode:1=4
hdmi_mode:a=4
""")
    p = BootParser(Path(str(tmpdir)))
    p.parse()
    assert p.config == [
        BootCommand('config.txt', 1, 'hdmi_group', '1', 0),
        BootCommand('config.txt', 2, 'hdmi_mode', '4', 1),
        BootCommand('config.txt', 3, 'hdmi_mode', '4', 0),
    ]


def test_parse_edid_section(tmpdir):
    tmpdir.join('config.txt').write("""# This is a comment
[EDID=BNQ-BenQ_GW2270]
hdmi_group=1
hdmi_mode=16

[EDID=VSC-TD2220]
hdmi_group=1
hdmi_mode=4
""")
    p = BootParser(Path(str(tmpdir)))
    p.parse()
    assert p.config == [
        BootSection('config.txt', 2, 'EDID=BNQ-BenQ_GW2270'),
        BootCommand('config.txt', 3, 'hdmi_group', '1', 0),
        BootCommand('config.txt', 4, 'hdmi_mode', '16', 0),
        BootSection('config.txt', 6, 'EDID=VSC-TD2220'),
        BootCommand('config.txt', 7, 'hdmi_group', '1', 0),
        BootCommand('config.txt', 8, 'hdmi_mode', '4', 0),
    ]


def test_parse_gpio_section(tmpdir):
    tmpdir.join('config.txt').write("""# This is a comment
[gpio4=1]
dtparam=audio=on
""")
    p = BootParser(Path(str(tmpdir)))
    p.parse()
    assert p.config == [
        BootSection('config.txt', 2, 'gpio4=1'),
        BootParam('config.txt', 3, 'base', 'audio', 'on'),
    ]


def test_parse_serial_bad_section(tmpdir):
    with mock.patch('pibootctl.parser.get_board_serial') as get_board_serial:
        tmpdir.join('config.txt').write("""# This is a comment
[0xwtf]
dtparam=audio=on
""")
        p = BootParser(Path(str(tmpdir)))
        p.parse()
        assert p.config == [
            BootSection('config.txt', 2, '0xwtf'),
            BootParam('config.txt', 3, 'base', 'audio', 'on'),
        ]


def test_parse_unknown_section(tmpdir, recwarn):
    tmpdir.join('config.txt').write("""# This is a comment
[foo]
dtparam=audio=on
""")
    p = BootParser(Path(str(tmpdir)))
    p.parse()
    assert p.config == [
        BootSection('config.txt', 2, 'foo'),
        BootParam('config.txt', 3, 'base', 'audio', 'on'),
    ]
    assert len(recwarn) == 1
    assert recwarn.pop(BootInvalid)


def test_parse_serial_section_match(tmpdir):
    with mock.patch('pibootctl.parser.get_board_serial') as get_board_serial:
        get_board_serial.return_value = 0xdeadd00d
        tmpdir.join('config.txt').write("""# This is a comment
[0xdeadd00d]
dtparam=audio=on
""")
        p = BootParser(Path(str(tmpdir)))
        p.parse()
        assert p.config == [
            BootSection('config.txt', 2, '0xdeadd00d'),
            BootParam('config.txt', 3, 'base', 'audio', 'on'),
        ]
        get_board_serial.return_value = 0xdeadd00d


def test_parse_serial_section_mismatch(tmpdir):
    with mock.patch('pibootctl.parser.get_board_serial') as get_board_serial:
        tmpdir.join('config.txt').write("""# This is a comment
[0x12345678]
dtparam=audio=on
""")
        p = BootParser(Path(str(tmpdir)))
        p.parse()
        assert p.config == [
            BootSection('config.txt', 2, '0x12345678'),
        ]


def test_parse_pi_section(tmpdir):
    with mock.patch('pibootctl.parser.get_board_types') as get_board_types:
        get_board_types.return_value = {'pi3', 'pi3+'}
        tmpdir.join('config.txt').write("""# This is a comment
[pi2]
kernel=uboot_2.bin
[pi3]
kernel=uboot_3_32b.bin
[pi4]
kernel=uboot_4_32b.bin
""")
        p = BootParser(Path(str(tmpdir)))
        p.parse()
        assert p.config == [
            BootSection('config.txt', 2, 'pi2'),
            BootSection('config.txt', 4, 'pi3'),
            BootCommand('config.txt', 5, 'kernel', 'uboot_3_32b.bin', 0),
            BootSection('config.txt', 6, 'pi4'),
        ]


def test_parse_attr(tmpdir):
    tmpdir = Path(str(tmpdir))
    content = b"""# This is a comment
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
    data1 = b"""# This is a comment
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
            BootCommand('config.txt', 2, 'kernel', 'vmlinuz', 0),
            BootCommand('config.txt', 3, 'device_tree_address', '0x3000000', 0),
            BootOverlay('config.txt', 4, 'vc4-fkms-v3d'),
        ]
        assert p.hash == h.hexdigest().lower()


def test_parse_dict(tmpdir):
    tmpdir = Path(str(tmpdir))
    (tmpdir / 'config.txt').write_text("""# This is a comment
[all]
dtoverlay=foo
include syscfg.txt
""")
    (tmpdir / 'syscfg.txt').write_text("""dtparam=i2c=on
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
        BootSection('config.txt', 2, 'all'),
        BootOverlay('config.txt', 3, 'foo'),
        BootInclude('config.txt', 4, 'syscfg.txt'),
    ]


def test_parse_empty(tmpdir):
    p = BootParser(Path(str(tmpdir)))
    p.parse()
    assert p.config == []
    assert p.hash == hashlib.sha1().hexdigest().lower()
