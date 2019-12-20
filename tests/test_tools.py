import pytest

from pictl.tools import *


def test_to_bool():
    assert to_bool('1') is True
    assert to_bool('YES') is True
    assert to_bool(' true ') is True
    assert to_bool(' 0') is False
    assert to_bool('n') is False
    assert to_bool('false ') is False
    with pytest.raises(ValueError):
        to_bool('foo')


def test_to_tri_bool():
    assert to_tri_bool('1') is True
    assert to_tri_bool('YES') is True
    assert to_tri_bool(' true ') is True
    assert to_tri_bool(' 0') is False
    assert to_tri_bool('n') is False
    assert to_tri_bool('false ') is False
    assert to_tri_bool(' ') is None
    assert to_tri_bool('auto') is None
    with pytest.raises(ValueError):
        to_tri_bool('foo')


def test_int_ranges():
    assert int_ranges(set()) == ''
    assert int_ranges({1}) == '1'
    assert int_ranges({1, 2}) == '1, 2'
    assert int_ranges({1, 2, 3}) == '1-3'
    assert int_ranges({1, 2, 3, 4, 8}) == '1-4, 8'
    assert int_ranges({1, 2, 3, 4, 8, 9}) == '1-4, 8-9'


def test_transmap():
    assert ''.format_map(TransMap(foo=1)) == ''
    assert '{foo}{bar}'.format_map(TransMap(foo=1)) == '1{bar}'
    assert '{foo:02d}{bar:02d}{baz:02d}'.format_map(TransMap(foo=1, baz=3)) == '01{bar:02d}03'
    assert '{foo!r}{bar!s}{baz!a}'.format_map(TransMap(foo=1)) == '1{bar!s}{baz!r}'
    assert 'foo' in TransMap(foo=1)
