import pytest

from pictl.parser import *
from pictl.setting import *


def test_settings_container():
    settings = Settings()
    assert len([s for s in settings]) == len(settings)
    assert 'video.hdmi0.mode' in settings
    assert isinstance(settings['video.hdmi0.mode'], CommandDisplayMode)


def test_settings_copy():
    settings = Settings()
    copy = settings.copy()
    assert len(settings) == len(copy)
    assert settings is not copy
    assert set(s for s in settings) == set(s for s in copy)
    assert all(settings[name] is not copy[name] for name in settings)


def test_settings_extract(tmpdir):
    tmpdir.join('config.txt').write("""\
dtparam=i2c=on
dtparam=spi=on
hdmi_group=1
hdmi_mode=4
""")
    parser = BootParser()
    settings = Settings()
    settings.extract(parser.parse(str(tmpdir)))
    assert settings['i2c.enabled'].value
    assert settings['spi.enabled'].value
    assert not settings['audio.enabled'].value
    assert settings['video.hdmi0.group'].value == 1
    assert settings['video.hdmi0.mode'].value == 4
    assert settings['video.hdmi1.group'].value == 0
    assert settings['video.hdmi1.mode'].value == 0


def test_settings_diff(tmpdir):
    tmpdir.join('config.txt').write("""\
dtparam=i2c=on
dtparam=spi=on
hdmi_group=1
hdmi_mode=4
""")
    parser = BootParser()
    default = Settings()
    settings = default.copy()
    settings.extract(parser.parse(str(tmpdir)))
    assert default.diff(settings) == {
        (default[name], settings[name])
        for name in (
            'i2c.enabled',
            'spi.enabled',
            'video.hdmi0.group',
            'video.hdmi0.mode',
        )
    }


def test_settings_validate(tmpdir):
    tmpdir.join('config.txt').write("""\
hdmi_group=1
hdmi_mode=4
""")
    parser = BootParser()
    settings = Settings()
    settings.extract(parser.parse(str(tmpdir)))
    settings.validate()
    settings.update({'video.hdmi0.mode': 90})
    with pytest.raises(ValueError):
        settings.validate()


def test_settings_output(tmpdir):
    tmpdir.join('config.txt').write("""\
dtparam=i2c,spi
hdmi_group=1
hdmi_mode=4
""")
    parser = BootParser()
    settings = Settings()
    settings.extract(parser.parse(str(tmpdir)))
    assert settings.output() == """\
# This file is intended to contain system-made configuration changes. User
# configuration changes should be placed in "usercfg.txt". Please refer to the
# README file for a description of the various configuration files on the boot
# partition.

hdmi_group=1
hdmi_mode=4
dtparam=i2c_arm=on
dtparam=spi=on"""
