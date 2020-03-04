from unittest import mock
from collections import OrderedDict

import pytest

from pictl.formatter import *


@pytest.fixture()
def table_data(request):
    return [
        ['Key', 'Value'],
        ['foo', 'bar'],
        ['baz', 'A much longer value which can wrap over several lines'],
        ['quux', 'Just for completeness'],
    ]


@pytest.fixture()
def dict_data(request):
    return OrderedDict([
        ['foo', 'bar'],
        ['baz', 'A much longer value which can wrap over several lines'],
        ['quux', 'Just for completeness'],
    ])


def test_table_wrap_basic(table_data):
    expected = [
        "Key  Value                                                ",
        "---- -----------------------------------------------------",
        "foo  bar                                                  ",
        "baz  A much longer value which can wrap over several lines",
        "quux Just for completeness                                ",
    ]
    wrap = TableWrapper()
    assert wrap.wrap(table_data) == expected
    assert wrap.fill(table_data) == '\n'.join(expected)


def test_table_wrap_no_header(table_data):
    expected = [
        "Key  Value                                                ",
        "foo  bar                                                  ",
        "baz  A much longer value which can wrap over several lines",
        "quux Just for completeness                                ",
    ]
    wrap = TableWrapper(header_rows=0)
    assert wrap.wrap(table_data) == expected
    assert wrap.fill(table_data) == '\n'.join(expected)


def test_table_wrap_thin(table_data):
    wrap = TableWrapper(width=40)
    expected = [
        "Key  Value                              ",
        "---- -----------------------------------",
        "foo  bar                                ",
        "baz  A much longer value which can wrap ",
        "     over several lines                 ",
        "quux Just for completeness              ",
    ]
    assert wrap.wrap(table_data) == expected
    assert wrap.fill(table_data) == '\n'.join(expected)


def test_table_wrap_pretty_thin(table_data):
    wrap = TableWrapper(width=40, **pretty_table)
    expected = [
        "+------+-------------------------------+",
        "| Key  | Value                         |",
        "|------+-------------------------------|",
        "| foo  | bar                           |",
        "| baz  | A much longer value which can |",
        "|      | wrap over several lines       |",
        "| quux | Just for completeness         |",
        "+------+-------------------------------+",
    ]
    assert wrap.wrap(table_data) == expected
    assert wrap.fill(table_data) == '\n'.join(expected)


def test_table_wrap_footer(table_data):
    wrap = TableWrapper(width=40, footer_rows=1, **pretty_table)
    expected = [
        "+------+-------------------------------+",
        "| Key  | Value                         |",
        "|------+-------------------------------|",
        "| foo  | bar                           |",
        "| baz  | A much longer value which can |",
        "|      | wrap over several lines       |",
        "|------+-------------------------------|",
        "| quux | Just for completeness         |",
        "+------+-------------------------------+",
    ]
    assert wrap.wrap(table_data) == expected
    assert wrap.fill(table_data) == '\n'.join(expected)


def test_table_wrap_complex():
    table_data = [
        ['Model', 'RAM', 'Ethernet', 'Wifi', 'Bluetooth', 'Notes'],
        ['Raspberry Pi 0', '512Mb', 'No', 'No', 'No',
         'Lowest power draw, smallest form factor'],
        ['Raspberry Pi 0W', '512Mb', 'No', 'Yes', 'Yes',
         'Popular in drones'],
        ['Raspberry Pi 3B+', '1Gb', 'Yes', 'Yes (+5GHz)', 'Yes',
         'The most common Pi currently'],
        ['Raspberry Pi 3A+', '512Mb', 'No', 'Yes (+5GHz)', 'Yes',
         'Small form factor, low power variant of the 3B+'],
    ]
    expected = [
        "+---------------+-------+----------+-------------+-----------+----------------+",
        "| Model         | RAM   | Ethernet | Wifi        | Bluetooth | Notes          |",
        "|---------------+-------+----------+-------------+-----------+----------------|",
        "| Raspberry Pi  | 512Mb | No       | No          | No        | Lowest power   |",
        "| 0             |       |          |             |           | draw, smallest |",
        "|               |       |          |             |           | form factor    |",
        "| Raspberry Pi  | 512Mb | No       | Yes         | Yes       | Popular in     |",
        "| 0W            |       |          |             |           | drones         |",
        "| Raspberry Pi  | 1Gb   | Yes      | Yes (+5GHz) | Yes       | The most       |",
        "| 3B+           |       |          |             |           | common Pi      |",
        "|               |       |          |             |           | currently      |",
        "| Raspberry Pi  | 512Mb | No       | Yes (+5GHz) | Yes       | Small form     |",
        "| 3A+           |       |          |             |           | factor, low    |",
        "|               |       |          |             |           | power variant  |",
        "|               |       |          |             |           | of the 3B+     |",
        "+---------------+-------+----------+-------------+-----------+----------------+",
    ]
    wrap = TableWrapper(width=79, **pretty_table)
    assert wrap.wrap(table_data) == expected
    assert wrap.fill(table_data) == '\n'.join(expected)
    expected = [
        "+-----------+-------+----------+-----------+-----------+------------+",
        "| Model     | RAM   | Ethernet | Wifi      | Bluetooth | Notes      |",
        "|-----------+-------+----------+-----------+-----------+------------|",
        "| Raspberry | 512Mb | No       | No        | No        | Lowest     |",
        "| Pi 0      |       |          |           |           | power      |",
        "|           |       |          |           |           | draw,      |",
        "|           |       |          |           |           | smallest   |",
        "|           |       |          |           |           | form       |",
        "|           |       |          |           |           | factor     |",
        "| Raspberry | 512Mb | No       | Yes       | Yes       | Popular in |",
        "| Pi 0W     |       |          |           |           | drones     |",
        "| Raspberry | 1Gb   | Yes      | Yes       | Yes       | The most   |",
        "| Pi 3B+    |       |          | (+5GHz)   |           | common Pi  |",
        "|           |       |          |           |           | currently  |",
        "| Raspberry | 512Mb | No       | Yes       | Yes       | Small form |",
        "| Pi 3A+    |       |          | (+5GHz)   |           | factor,    |",
        "|           |       |          |           |           | low power  |",
        "|           |       |          |           |           | variant of |",
        "|           |       |          |           |           | the 3B+    |",
        "+-----------+-------+----------+-----------+-----------+------------+",
    ]
    wrap = TableWrapper(width=69, **pretty_table)
    assert wrap.wrap(table_data) == expected
    assert wrap.fill(table_data) == '\n'.join(expected)


def test_table_wrap_too_thin(table_data):
    expected = [
        "Key  Value                                                ",
        "---- -----------------------------------------------------",
        "foo  bar                                                  ",
        "baz  A much longer value which can wrap over several lines",
        "quux Just for completeness                                ",
    ]
    wrap = TableWrapper(width=5, **pretty_table)
    with pytest.raises(ValueError):
        wrap.wrap(table_data)


def test_table_wrap_bad_init():
    with pytest.raises(ValueError):
        TableWrapper(borders='|')
    with pytest.raises(ValueError):
        TableWrapper(corners=',-')
    with pytest.raises(ValueError):
        TableWrapper(internal_borders='foo')


def test_table_wrap_align():
    data = [
        ('Key', 'Value'),
        ('foo', 1),
        ('bar', 2),
    ]
    expected = [
        "Key Value",
        "--- -----",
        "foo     1",
        "bar     2",
    ]
    wrap = TableWrapper(
        width=40,
        align=lambda data: '>' if isinstance(data, int) else '<')
    assert wrap.wrap(data) == expected
    assert wrap.fill(data) == '\n'.join(expected)


def test_table_wrap_format():
    data = [
        ('Key', 'Value'),
        ('foo', 1),
        ('bar', 2),
    ]
    expected = [
        "Key Value",
        "--- -----",
        "foo 001  ",
        "bar 002  ",
    ]
    wrap = TableWrapper(
        width=40,
        format=lambda data: '{:03d}'.format(data)
                            if isinstance(data, int) else str(data))
    assert wrap.wrap(data) == expected
    assert wrap.fill(data) == '\n'.join(expected)


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


def test_format_dict_table(dict_data):
    assert '{:table}'.format(FormatDict(dict_data)) == """\
| Key | Value |
| foo | bar |
| baz | A much longer value which can wrap over several lines |
| quux | Just for completeness |"""


def test_format_dict_list(dict_data):
    assert '{:list}'.format(FormatDict(dict_data)) == """\
* foo = bar
* baz = A much longer value which can wrap over several lines
* quux = Just for completeness"""


def test_format_dict_bad_format(dict_data):
    with pytest.raises(ValueError):
        '{:foo}'.format(FormatDict(dict_data))


def test_render_para():
    assert render("""\
This is a very long line which ought to be wrapped by the renderer.

And this is another very long which also ought to get wrapped.

This is a short line.""", width=40) == """\
This is a very long line which ought to
be wrapped by the renderer.

And this is another very long which also
ought to get wrapped.

This is a short line."""


def test_render_list(dict_data):
    assert render("{:list}".format(FormatDict(dict_data)), width=40) == """\
* foo = bar
* baz = A much longer value which can
  wrap over several lines
* quux = Just for completeness"""
    assert render("""
* A list item
  can be defined across
  several lines

* Or not""") == """\
* A list item can be defined across several lines
* Or not"""
    assert render("""
* A list item
  can be defined across
  several lines

* Or not""", list_space=True) == """\
* A list item can be defined across several lines

* Or not"""


def test_render_table(dict_data):
    assert render("{:table}".format(FormatDict(dict_data)), width=40,
                  table_style=pretty_table) == """\
+------+-------------------------------+
| Key  | Value                         |
|------+-------------------------------|
| foo  | bar                           |
| baz  | A much longer value which can |
|      | wrap over several lines       |
| quux | Just for completeness         |
+------+-------------------------------+"""


def test_render_mixed():
    assert render("""\
A paragraph
* Followed by a two item
* list
| Key | Value |
| foo | 1 |
| bar | 2 |

* Split list

* of three items

* followed by

| Key | Value |
| foo | 1 |
| bar | 2 |

* A final list with a single item

And a final paragraph, split over lines
followed by
| Key | Value |
| foo | 1 |
| bar | 2 |
""", table_style=pretty_table) == """\
A paragraph

* Followed by a two item
* list

+-----+-------+
| Key | Value |
|-----+-------|
| foo | 1     |
| bar | 2     |
+-----+-------+

* Split list
* of three items
* followed by

+-----+-------+
| Key | Value |
|-----+-------|
| foo | 1     |
| bar | 2     |
+-----+-------+

* A final list with a single item

And a final paragraph, split over lines followed by

+-----+-------+
| Key | Value |
|-----+-------|
| foo | 1     |
| bar | 2     |
+-----+-------+"""
