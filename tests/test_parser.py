from pathlib import Path
from unittest import mock

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


def test_parse_simple(tmpdir):
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
