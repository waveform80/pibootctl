import zipfile
import warnings
from pathlib import Path
from unittest import mock
from hashlib import sha1

import pytest

from pictl.parser import *


def test_str():
    assert str(BootSection(Path('config.txt'), 1, 'all')) == '[all]'
    assert str(BootCommand(
        Path('config.txt'), 1, 'initramfs', ('initrd.img', 'followkernel')
    )) == 'initramfs initrd.img followkernel'
    assert str(BootCommand(Path('config.txt'), 1, 'hdmi_group', '1')) == 'hdmi_group=1'
    assert str(BootCommand(Path('config.txt'), 1, 'hdmi_group', '2', 1)) == 'hdmi_group:1=2'
    assert str(BootInclude(Path('config.txt'), 1, Path('syscfg.txt'))) == 'include syscfg.txt'
    assert str(BootOverlay(Path('config.txt'), 1, 'foo')) == 'dtoverlay=foo'
    assert str(BootParam(Path('config.txt'), 1, 'base', 'spi', 'on')) == 'dtparam=spi=on'


def test_repr():
    assert repr(BootLine(Path('config.txt'), 2)) == (
        "BootLine(path=PosixPath('config.txt'), lineno=2)")
    assert repr(BootSection(Path('config.txt'), 1, 'all')) == (
        "BootSection(path=PosixPath('config.txt'), lineno=1, section='all')")
    assert repr(BootCommand(
        Path('config.txt'), 1, 'initramfs', ('initrd.img', 'followkernel')
    )) == (
        "BootCommand(path=PosixPath('config.txt'), lineno=1, "
        "command='initramfs', params=('initrd.img', 'followkernel'), "
        "hdmi=None)"
    )
    assert repr(BootCommand(Path('config.txt'), 1, 'hdmi_group', '1')) == (
        "BootCommand(path=PosixPath('config.txt'), lineno=1, "
        "command='hdmi_group', params='1', hdmi=None)")
    assert repr(BootCommand(Path('config.txt'), 1, 'hdmi_group', '2', 1)) == (
        "BootCommand(path=PosixPath('config.txt'), lineno=1, "
        "command='hdmi_group', params='2', hdmi=1)")
    assert repr(BootInclude(Path('config.txt'), 1, Path('syscfg.txt'))) == (
        "BootInclude(path=PosixPath('config.txt'), lineno=1, "
        "include=PosixPath('syscfg.txt'))")
    assert repr(BootOverlay(Path('config.txt'), 1, 'foo')) == (
        "BootOverlay(path=PosixPath('config.txt'), lineno=1, overlay='foo')")
    assert repr(BootParam(Path('config.txt'), 1, 'base', 'spi', 'on')) == (
        "BootParam(path=PosixPath('config.txt'), lineno=1, overlay='base', "
        "param='spi', value='on')")


def test_parse_basic(tmpdir):
    tmpdir.join('config.txt').write("""# This is a comment
kernel=vmlinuz
initramfs initrd.img followkernel
device_tree_address=0x3000000
dtoverlay=vc4-fkms-v3d
""")
    p = BootParser()
    l = p.parse(str(tmpdir))
    assert l == [
        BootCommand(Path('config.txt'), 2, 'kernel', 'vmlinuz', 0),
        BootCommand(Path('config.txt'), 3, 'initramfs', ('initrd.img', 'followkernel')),
        BootCommand(Path('config.txt'), 4, 'device_tree_address', '0x3000000', 0),
        BootOverlay(Path('config.txt'), 5, 'vc4-fkms-v3d'),
    ]


def test_parse_invalid(tmpdir):
    tmpdir.join('config.txt').write("""# This is a comment
This is not
""")
    p = BootParser()
    with pytest.warns(BootInvalid) as w:
        l = p.parse(str(tmpdir))
        assert l == []
        assert len(w) == 1
        assert w[0].message.args[0] == 'config.txt:2 invalid line'


def test_parse_overlay_and_params(tmpdir):
    tmpdir.join('config.txt').write("""\
dtparam=audio=on,i2c=on,i2c_baudrate=400000
dtparam=spi,i2c0
dtoverlay=lirc-rpi:gpio_out_pin=16,gpio_in_pin=17,gpio_in_pull=down
""")
    p = BootParser()
    l = p.parse(str(tmpdir))
    assert l == [
        BootParam(Path('config.txt'), 1, 'base', 'audio', 'on'),
        BootParam(Path('config.txt'), 1, 'base', 'i2c_arm', 'on'),
        BootParam(Path('config.txt'), 1, 'base', 'i2c_arm_baudrate', '400000'),
        BootParam(Path('config.txt'), 2, 'base', 'spi', 'on'),
        BootParam(Path('config.txt'), 2, 'base', 'i2c_vc', 'on'),
        BootOverlay(Path('config.txt'), 3, 'lirc-rpi'),
        BootParam(Path('config.txt'), 3, 'lirc-rpi', 'gpio_out_pin', '16'),
        BootParam(Path('config.txt'), 3, 'lirc-rpi', 'gpio_in_pin', '17'),
        BootParam(Path('config.txt'), 3, 'lirc-rpi', 'gpio_in_pull', 'down'),
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
    p = BootParser()
    l = p.parse(str(tmpdir))
    assert l == [
        BootSection(Path('config.txt'), 2, 'none'),
        BootSection(Path('config.txt'), 5, 'all'),
        BootOverlay(Path('config.txt'), 6, 'foo'),
        BootInclude(Path('config.txt'), 7, Path('syscfg.txt')),
        BootParam(Path('syscfg.txt'), 1, 'base', 'i2c_arm', 'on'),
        BootParam(Path('syscfg.txt'), 2, 'base', 'spi', 'on'),
        BootCommand(Path('syscfg.txt'), 4, 'hdmi_group', '1', 0),
        BootCommand(Path('syscfg.txt'), 5, 'hdmi_mode', '4', 0),
    ]


def test_parse_hdmi_section(tmpdir):
    tmpdir.join('config.txt').write("""# This is a comment
hdmi_group=1
hdmi_mode=4

[HDMI:1]
hdmi_group=2
hdmi_mode=28
""")
    p = BootParser()
    l = p.parse(str(tmpdir))
    assert l == [
        BootCommand(Path('config.txt'), 2, 'hdmi_group', '1', 0),
        BootCommand(Path('config.txt'), 3, 'hdmi_mode', '4', 0),
        BootSection(Path('config.txt'), 5, 'HDMI:1'),
        BootCommand(Path('config.txt'), 6, 'hdmi_group', '2', 1),
        BootCommand(Path('config.txt'), 7, 'hdmi_mode', '28', 1),
    ]


def test_parse_hdmi_suffix(tmpdir):
    tmpdir.join('config.txt').write("""\
hdmi_group:0=1
hdmi_mode:1=4
hdmi_mode:a=4
""")
    p = BootParser()
    l = p.parse(str(tmpdir))
    assert l == [
        BootCommand(Path('config.txt'), 1, 'hdmi_group', '1', 0),
        BootCommand(Path('config.txt'), 2, 'hdmi_mode', '4', 1),
        BootCommand(Path('config.txt'), 3, 'hdmi_mode', '4', 0),
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
    p = BootParser()
    l = p.parse(str(tmpdir))
    assert l == [
        BootSection(Path('config.txt'), 2, 'EDID=BNQ-BenQ_GW2270'),
        BootCommand(Path('config.txt'), 3, 'hdmi_group', '1', 0),
        BootCommand(Path('config.txt'), 4, 'hdmi_mode', '16', 0),
        BootSection(Path('config.txt'), 6, 'EDID=VSC-TD2220'),
        BootCommand(Path('config.txt'), 7, 'hdmi_group', '1', 0),
        BootCommand(Path('config.txt'), 8, 'hdmi_mode', '4', 0),
    ]


def test_parse_gpio_section(tmpdir):
    tmpdir.join('config.txt').write("""# This is a comment
[gpio4=1]
dtparam=audio=on
""")
    p = BootParser()
    l = p.parse(str(tmpdir))
    assert l == [
        BootSection(Path('config.txt'), 2, 'gpio4=1'),
        BootParam(Path('config.txt'), 3, 'base', 'audio', 'on'),
    ]


def test_parse_serial_bad_section(tmpdir):
    with mock.patch('pictl.parser.get_board_serial') as get_board_serial:
        tmpdir.join('config.txt').write("""# This is a comment
[0xwtf]
dtparam=audio=on
""")
        p = BootParser()
        l = p.parse(str(tmpdir))
        assert l == [
            BootSection(Path('config.txt'), 2, '0xwtf'),
            BootParam(Path('config.txt'), 3, 'base', 'audio', 'on'),
        ]


def test_parse_serial_section_match(tmpdir):
    with mock.patch('pictl.parser.get_board_serial') as get_board_serial:
        get_board_serial.return_value = 0xdeadd00d
        tmpdir.join('config.txt').write("""# This is a comment
[0xdeadd00d]
dtparam=audio=on
""")
        p = BootParser()
        l = p.parse(str(tmpdir))
        assert l == [
            BootSection(Path('config.txt'), 2, '0xdeadd00d'),
            BootParam(Path('config.txt'), 3, 'base', 'audio', 'on'),
        ]
        get_board_serial.return_value = 0xdeadd00d


def test_parse_serial_section_mismatch(tmpdir):
    with mock.patch('pictl.parser.get_board_serial') as get_board_serial:
        tmpdir.join('config.txt').write("""# This is a comment
[0x12345678]
dtparam=audio=on
""")
        p = BootParser()
        l = p.parse(str(tmpdir))
        assert l == [
            BootSection(Path('config.txt'), 2, '0x12345678'),
        ]


def test_parse_pi_section(tmpdir):
    with mock.patch('pictl.parser.get_board_types') as get_board_types:
        get_board_types.return_value = {'pi3', 'pi3+'}
        tmpdir.join('config.txt').write("""# This is a comment
[pi2]
kernel=uboot_2.bin
[pi3]
kernel=uboot_3_32b.bin
[pi4]
kernel=uboot_4_32b.bin
""")
        p = BootParser()
        l = p.parse(str(tmpdir))
        assert l == [
            BootSection(Path('config.txt'), 2, 'pi2'),
            BootSection(Path('config.txt'), 4, 'pi3'),
            BootCommand(Path('config.txt'), 5, 'kernel', 'uboot_3_32b.bin', 0),
            BootSection(Path('config.txt'), 6, 'pi4'),
        ]


def test_parse_attr(tmpdir):
    with mock.patch('pictl.parser.get_board_types') as get_board_types:
        get_board_types.return_value = {'pi3', 'pi3+'}
        tmpdir.join('config.txt').write("""# This is a comment
[pi2]
kernel=uboot_2.bin
[pi3]
kernel=uboot_3_32b.bin
[pi4]
kernel=uboot_4_32b.bin
""")
        p = BootParser()
        l = p.parse(str(tmpdir))
        content = [
            b"# This is a comment\n",
            b"[pi2]\n",
            b"kernel=uboot_2.bin\n",
            b"[pi3]\n",
            b"kernel=uboot_3_32b.bin\n",
            b"[pi4]\n",
            b"kernel=uboot_4_32b.bin\n",
        ]
        assert p.content == {
            Path('config.txt'): content,
        }
        h = sha1()
        for line in content:
            h.update(line)
        assert p.hash.digest() == h.digest()


def test_parse_store(tmpdir):
    with zipfile.ZipFile(str(tmpdir.join('stored.zip')), 'w') as arc:
        arc.writestr('config.txt', b"""# This is a comment
kernel=vmlinuz
device_tree_address=0x3000000
dtoverlay=vc4-fkms-v3d
""")
    p = BootParser()
    l = p.parse(str(tmpdir.join('stored.zip')))
    assert l == [
        BootCommand(Path('config.txt'), 2, 'kernel', 'vmlinuz', 0),
        BootCommand(Path('config.txt'), 3, 'device_tree_address', '0x3000000', 0),
        BootOverlay(Path('config.txt'), 4, 'vc4-fkms-v3d'),
    ]
