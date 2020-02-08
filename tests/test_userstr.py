import pytest

from pictl.userstr import *


def test_to_bool():
    assert to_bool(UserStr('1')) is True
    assert to_bool(UserStr('YES')) is True
    assert to_bool(UserStr(' true ')) is True
    assert to_bool(UserStr(' 0')) is False
    assert to_bool(UserStr('n')) is False
    assert to_bool(UserStr('false ')) is False
    assert to_bool(UserStr(' ')) is None
    with pytest.raises(ValueError):
        to_bool(UserStr('foo'))
