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
The :mod:`pibootctl.formatter` module contains some generic text formatting
routines, including the :class:`TableWrapper` class (akin to
:class:`~textwrap.TextWrapper` but specific to table output), :class:`TransMap`
for partially formatting templates, and the :func:`render` function: a crude
markup renderer.

.. autoclass:: TableWrapper

.. data:: pretty_table

    Uses simple ASCII characters to produce a typical "box-like" table
    appearance::

        >>> from pibootctl.formatter import *
        >>> wrapper = TableWrapper(width=80, **pretty_table)
        >>> data = [
        ... ('Name', 'Length', 'Position'),
        ... ('foo', 3, 1),
        ... ('bar', 3, 2),
        ... ('baz', 3, 3),
        ... ('quux', 4, 4)]
        >>> print(wrapper.fill(data))
        +------+--------+----------+
        | Name | Length | Position |
        |------+--------+----------|
        | foo  | 3      | 1        |
        | bar  | 3      | 2        |
        | baz  | 3      | 3        |
        | quux | 4      | 4        |
        +------+--------+----------+

.. data:: curvy_table

    Uses simple ASCII characters to produce a "round-edged" table appearance::

        >>> from pibootctl.formatter import *
        >>> wrapper = TableWrapper(width=80, **curvy_table)
        >>> data = [
        ... ('Name', 'Length', 'Position'),
        ... ('foo', 3, 1),
        ... ('bar', 3, 2),
        ... ('baz', 3, 3),
        ... ('quux', 4, 4)]
        >>> print(wrapper.fill(data))
        ,------+--------+----------.
        | Name | Length | Position |
        |------+--------+----------|
        | foo  | 3      | 1        |
        | bar  | 3      | 2        |
        | baz  | 3      | 3        |
        | quux | 4      | 4        |
        `------+--------+----------'

.. data:: unicode_table

    Uses unicode box-drawing characters to produce a typical "box-like" table
    appearance::

        >>> from pibootctl.formatter import *
        >>> wrapper = TableWrapper(width=80, **unicode_table)
        >>> data = [
        ... ('Name', 'Length', 'Position'),
        ... ('foo', 3, 1),
        ... ('bar', 3, 2),
        ... ('baz', 3, 3),
        ... ('quux', 4, 4)]
        >>> print(wrapper.fill(data))
        ┌──────┬────────┬──────────┐
        │ Name │ Length │ Position │
        ├──────┼────────┼──────────┤
        │ foo  │ 3      │ 1        │
        │ bar  │ 3      │ 2        │
        │ baz  │ 3      │ 3        │
        │ quux │ 4      │ 4        │
        └──────┴────────┴──────────┘

.. data:: curvy_unicode_table

    Uses unicode box-drawing characters to produce a "round-edged" table
    appearance::

        >>> from pibootctl.formatter import *
        >>> wrapper = TableWrapper(width=80, **curvy_unicode_table)
        >>> data = [
        ... ('Name', 'Length', 'Position'),
        ... ('foo', 3, 1),
        ... ('bar', 3, 2),
        ... ('baz', 3, 3),
        ... ('quux', 4, 4)]
        >>> print(wrapper.fill(data))
        ╭──────┬────────┬──────────╮
        │ Name │ Length │ Position │
        ├──────┼────────┼──────────┤
        │ foo  │ 3      │ 1        │
        │ bar  │ 3      │ 2        │
        │ baz  │ 3      │ 3        │
        │ quux │ 4      │ 4        │
        ╰──────┴────────┴──────────╯

.. autoclass:: TransMap

.. autoclass:: FormatDict

.. autofunction:: int_ranges

.. autofunction:: render
"""

import re
from bisect import bisect
from textwrap import dedent, TextWrapper
from itertools import islice, zip_longest, chain, tee


class TableWrapper:
    """
    Similar to :class:`~textwrap.TextWrapper`, this class provides facilities
    for wrapping text to a particular width, but with a focus on table-based
    output.

    The constructor takes numerous arguments, but typically you don't need to
    specify them all (or at all). A series of dictionaries are provided with
    "common" configurations: :data:`pretty_table`, :data:`curvy_table`,
    :data:`unicode_table`, and :data:`curvy_unicode_table`. For example::

        >>> from pibootctl.formatter import *
        >>> wrapper = TableWrapper(width=80, **curvy_table)
        >>> data = [
        ... ('Name', 'Length', 'Position'),
        ... ('foo', 3, 1),
        ... ('bar', 3, 2),
        ... ('baz', 3, 3),
        ... ('quux', 4, 4)]
        >>> print(wrapper.fill(data))
        ,------+--------+----------.
        | Name | Length | Position |
        |------+--------+----------|
        | foo  | 3      | 1        |
        | bar  | 3      | 2        |
        | baz  | 3      | 3        |
        | quux | 4      | 4        |
        `------+--------+----------'

    The :class:`TableWrapper` instance attributes (and keyword arguments to
    the constructor) are as follows:

    .. attribute:: width

        (default 70) The maximum number of characters that the table can take
        up horizontally. :class:`TableWrapper` guarantees that no output line
        will be longer than :attr:`width` characters.

    .. attribute:: header_rows

        (default 1) The number of rows at the top of the table that will be
        separated from the following rows by a horizontal border
        (:attr:`internal_line`).

    .. attribute:: footer_rows

        (default 0) The number of rows at the bottom of the table that will be
        separated from the preceding rows by a horizontal border
        (:attr:`internal_line`).

    .. attribute:: cell_separator

        (default ``' '``) The string used to separate columns of cells.

    .. attribute:: internal_line

        (default ``'-'``) The string used to draw horizontal lines inside the
        table for :attr:`header_rows` and :attr:`footer_rows`.

    .. attribute:: internal_separator

        (default ``' '``) The string used within runs of :attr:`internal_line`
        to separate columns.

    .. attribute:: borders

        (default ``('', '', '', '')``) A 4-tuple of strings which specify the
        characters used to create the left, top, right, and bottom borders of
        the table respectively.

    .. attribute:: corners

        (default ``('', '', '', '')``) A 4-tuple of strings which specify the
        characters used for the top-left, top-right, bottom-right, and
        bottom-left corners of the table respectively.

    .. attribute:: internal_borders

        (default ``('', '', '', '')``) A 4-tuple of strings which specify the
        characters used to interrupt runs of the :attr:`borders` characters
        to draw row and column separators. Like :attr:`borders` these are the
        left, top, right, and bottom characters respectively.

    .. attribute:: align

        A callable accepting three parameters: 0-based row index, 0-based
        column index, and the cell data. The callable must return a character
        indicating the intended alignment of data within the cell. "<" for
        left justification, "^" for centered alignment, and ">" for right
        justification (as in :meth:`str.format`). The default is to left align
        everything.

    .. attribute:: format

        A callable accepting three parameters: 0-based row index, 0-based
        column index, and the cell data. The callable must return the desired
        string representation of the cell data. The default simply calls
        :class:`str` on everything.

    :class:`TableWrapper` also provides similar public methods to
    :class:`~textwrap.TextWrapper`:

    .. automethod:: wrap

    .. automethod:: fill
    """

    def __init__(self, width=70, header_rows=1, footer_rows=0,
                 cell_separator=' ', internal_line='-', internal_separator=' ',
                 borders=('', '', '', ''), corners=('', '', '', ''),
                 internal_borders=('', '', '', ''), align=None, format=None):
        if len(borders) != 4:
            raise ValueError('borders must be a 4-tuple of strings')
        if len(corners) != 4:
            raise ValueError('corners must be a 4-tuple of strings')
        if len(internal_borders) != 4:
            raise ValueError('internal_borders must be a 4-tuple of strings')
        self.width = width
        self.header_rows = header_rows
        self.footer_rows = footer_rows
        self.internal_line = internal_line
        self.cell_separator = cell_separator
        self.internal_separator = internal_separator
        self.internal_borders = internal_borders
        self.borders = tuple(borders)
        self.corners = tuple(corners)
        self.internal_borders = tuple(internal_borders)
        if align is None:
            align = lambda row, col, data: '<'
        self.align = align
        if format is None:
            format = lambda row, col, data: str(data)
        self.format = format

    def fit_widths(self, widths):
        """
        Internal method which, given the sequence of *widths* (the calculated
        maximum width of each column), reduces those widths until they fit in
        the specified :attr:`width` limit, taking into account the implied
        width of column separators, borders, etc.
        """
        min_width = sum((
            len(self.borders[0]),
            len(self.borders[2]),
            len(self.cell_separator) * (len(widths) - 1)
        ))
        # Minimum width of each column is 1
        if min_width + len(widths) > self.width:
            raise ValueError('width is too thin to accommodate the table')
        total_width = sum(widths) + min_width
        # Reduce column widths until they fit in the available space. First, we
        # sort by the current column widths then by index so the widest columns
        # form a left-to-right ordered suffix of the list
        widths = sorted((w, i) for i, w in enumerate(widths))
        while total_width > self.width:
            # Find the insertion point before the suffix
            suffix = bisect(widths, (widths[-1][0] - 1, -1))
            suffix_len = len(widths) - suffix
            # Calculate the amount of width we still need to shed
            reduce_by = total_width - self.width
            if suffix > 0:
                # Limit this by the amount that can be removed evenly from the
                # suffix columns before the suffix needs to expand to encompass
                # more columns (requiring another loop)
                reduce_by = min(
                    reduce_by,
                    (widths[suffix][0] - widths[suffix - 1][0]) * suffix_len
                )
            # Distribute the reduction evenly across the columns of the suffix
            widths[suffix:] = [
                (w - reduce_by // suffix_len, i)
                for w, i in widths[suffix:]
            ]
            # Subtract the remainder from the left-most columns of the suffix
            for i in range(suffix, suffix + reduce_by % suffix_len):
                widths[i] = (widths[i][0] - 1, widths[i][1])
            total_width -= reduce_by
        return [w for i, w in sorted((i, w) for w, i in widths)]

    def wrap_lines(self, data, widths):
        """
        Internal method responsible for wrapping the contents of each cell in
        each row in *data* to the specified column *widths*.
        """
        # Construct wrappers for each column width
        wrappers = [TextWrapper(width=width) for width in widths]
        for y, row in enumerate(data):
            aligns = [self.align(y, x, cell) for x, cell in enumerate(row)]
            # Construct a list of wrapped lines for each cell in the row; these
            # are not necessarily of equal length (hence zip_longest below)
            cols = [
                wrapper.wrap(self.format(y, x, cell))
                for x, (cell, wrapper) in enumerate(zip(row, wrappers))
            ]
            for line in zip_longest(*cols, fillvalue=''):
                yield (
                    self.borders[0] +
                    self.cell_separator.join(
                        '{cell:{align}{width}}'.format(
                            cell=cell, align=align, width=width)
                        for align, width, cell in zip(aligns, widths, line)) +
                    self.borders[2]
                )

    def generate_lines(self, data):
        """
        Internal method which, given a sequence of rows of tuples in *data*,
        uses :meth:`fit_widths` to calculate the maximum possible column
        widths, and :meth:`wrap_lines` to wrap the text in *data* to the
        calculated widths, yielding rows of strings to the caller.
        """
        widths = [
            max(1, max(len(
                self.format(y, x, item)) for x, item in enumerate(row)))
            for y, row in enumerate(zip(*data))  # transpose
        ]
        widths = self.fit_widths(widths)
        lines = iter(data)
        if self.borders[1]:
            yield (
                self.corners[0] +
                self.internal_borders[1].join(
                    self.borders[1] * width for width in widths) +
                self.corners[1]
            )
        if self.header_rows > 0:
            yield from self.wrap_lines(islice(lines, self.header_rows), widths)
            yield (
                self.internal_borders[0] +
                self.internal_separator.join(
                    self.internal_line * w for w in widths) +
                self.internal_borders[2]
            )
        yield from self.wrap_lines(
            islice(lines, len(data) - self.header_rows - self.footer_rows),
            widths)
        if self.footer_rows > 0:
            yield (
                self.internal_borders[0] +
                self.internal_separator.join(
                    self.internal_line * w for w in widths) +
                self.internal_borders[2]
            )
        yield from self.wrap_lines(lines, widths)
        if self.borders[3]:
            yield (
                self.corners[3] +
                self.internal_borders[3].join(
                    self.borders[3] * width for width in widths) +
                self.corners[2]
            )

    def wrap(self, data):
        """
        Wraps the table *data* returning a list of output lines without final
        newlines. *data* must be a sequence of row tuples, each of which is
        assumed to be the same length.

        If the current :attr:`width` does not permit at least a single
        character per column (after taking account of the width of borders,
        internal separators, etc.) then :exc:`ValueError` will be raised.
        """
        return list(self.generate_lines(data))

    def fill(self, data):
        """
        Wraps the table *data* returning a string containing the wrapped
        output.
        """
        return '\n'.join(self.wrap(data))


# Some prettier defaults for TableWrapper
pretty_table = {
    'cell_separator': ' | ',
    'internal_line': '-',
    'internal_separator': '-+-',
    'borders': ('| ', '-', ' |', '-'),
    'corners': ('+-', '-+', '-+', '+-'),
    'internal_borders': ('|-', '-+-', '-|', '-+-'),
}

curvy_table = pretty_table.copy()
curvy_table['corners'] = (',-', '-.', "-'", '`-')

unicode_table = {
    'cell_separator': ' │ ',
    'internal_line': '─',
    'internal_separator': '─┼─',
    'borders': ('│ ', '─', ' │', '─'),
    'corners': ('┌─', '─┐', '─┘', '└─'),
    'internal_borders': ('├─', '─┬─', '─┤', '─┴─'),
}

curvy_unicode_table = unicode_table.copy()
curvy_unicode_table['corners'] = ('╭─', '─╮', '─╯', '╰─')


def pairwise(iterable):
    """
    Taken from the recipe in the documentation for :mod:`itertools`.
    """
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


def int_ranges(values, range_sep='-', list_sep=', '):
    """
    Given a set of integer *values*, returns a compressed string representation
    of all values in the set. For example:

        >>> int_ranges({1, 2})
        '1, 2'
        >>> int_ranges({1, 2, 3})
        '1-3'
        >>> int_ranges({1, 2, 3, 4, 8})
        '1-4, 8'
        >>> int_ranges({1, 2, 3, 4, 8, 9})
        '1-4, 8-9'

    *range_sep* and *list_sep* can be optionally specified to customize the
    strings used to separate ranges and lists of ranges respectively.
    """
    if len(values) == 0:
        return ''
    elif len(values) == 1:
        return '{0}'.format(*values)
    elif len(values) == 2:
        return '{0}{sep}{1}'.format(*values, sep=list_sep)
    else:
        ranges = []
        start = None
        for i, j in pairwise(sorted(values)):
            if start is None:
                start = i
            if j > i + 1:
                ranges.append((start, i))
                start = j
        if j == i + 1:
            ranges.append((start, j))
        else:
            ranges.append((j, j))
        return list_sep.join(
            ('{start}{sep}{finish}' if finish > start else '{start}').format(
                start=start, finish=finish, sep=range_sep)
            for start, finish in ranges
        )


class TransTemplate(str):
    """
    Used by :class:`TransMap` to transparently pass unknown format templates
    through for later substitution. When this value is used in a
    :meth:`str.format` substitution, it renders itself with the format
    specification as {self!conv:spec}, passing the template through verbatim.
    """
    # NOTE: No calling str.format in this class! ;)

    def __repr__(self):
        return TransTemplate(self + '!r')

    def __str__(self):
        return TransTemplate(self + '!s')

    def __format__(self, spec):
        if spec:
            parts = ('{', self, ':', spec, '}')
        else:
            parts = ('{', self, '}')
        return ''.join(parts)


class TransMap:
    """
    Used with :meth:`str.format_map` to substitute only a subset of values
    in a given template, passing the rest through for later processing. For
    example:

        >>> '{foo}{bar}'.format_map(TransMap(foo=1))
        '1{bar}'
        >>> '{foo:02d}{bar:02d}{baz:02d}'.format_map(TransMap(foo=1, baz=3))
        '01{bar:02d}03'

    .. note::

        One exception is that the ``!a`` conversion is not handled correctly.
        This is erroneously converted to ``!r``. Unfortunately there's no
        solution to this; it's a side-effect of the means by which the ``!a``
        conversion is performed.
    """
    def __init__(self, **kw):
        self._kw = kw

    def __contains__(self, key):
        return True

    def __getitem__(self, key):
        return self._kw.get(key, TransTemplate(key))


class FormatDict:
    """
    Used to format *data*, a :class:`dict`, in a format acceptable as input to
    the :func:`render` function. The *key_title* and *value_title* strings
    provide the cells for the single header row.

    This class is intended to be used within a string for :meth:`str.format`.
    For example::

        >>> from pibootctl.formatter import FormatDict
        >>> d = {'foo': 100, 'bar': 200}
        >>> print('An example table:\\n\\n{s}'.format(s=FormatDict(d)))
        An example table:

        | Key | Value |
        | foo | 100 |
        | bar | 200 |

    The format specification in the format string can be used to request
    different kinds of output, for instance::

        >>> f = FormatDict({'foo': 100, 'bar': 200})
        >>> print('An example list:\\n\\n{f:list}'.format(f=f))
        An example list:

        * foo = 100
        * bar = 200
        >>> print('An example reference list:\\n\\n{f:refs}'.format(f=f))
        An example reference list:

        [foo]: 100
        [bar]: 200

    The default format specification is "table", naturally.

    If the values are tuples that should be expanded into multiple columns,
    set *value_title* to a tuple with the corresponding column titles::

        >>> from pibootctl.formatter import FormatDict
        >>> d = {'foo': (1, 100), 'bar': (2, 200)}
        >>> print('An example table:\\n\\n{s}'.format(s=FormatDict(d,
        ... value_title=('col1', 'col2'))))
        An example table:

        | Key | col1 | col2 |
        | foo | 1 | 100 |
        | bar | 2 | 200 |

    Tuple values are only supported for table output.

    .. note::

        In Python versions before 3.7, you may need to use
        :class:`collections.OrderedDict` to ensure output of the elements of
        *data* in a particular order. Alternatively, you may specify a
        *sort_key* value which will be applied to the key values of the dict to
        sort them prior to output.
    """
    def __init__(self, data, key_title='Key', value_title='Value',
                 sort_key=None):
        self.data = data
        self.key_title = key_title
        self.value_title = value_title
        self.sort_key = sort_key

    def __format__(self, spec):
        if self.sort_key is None:
            items = self.data.items()
        else:
            items = (
                (key, self.data[key])
                for key in sorted(self.data.keys(), key=self.sort_key)
            )
        if not spec or spec == 'table':
            if isinstance(self.value_title, tuple):
                return '\n'.join(
                    '| {key} | {values} |'.format(
                        key=key, values=' | '.join(values))
                    for key, values in chain(
                        [(self.key_title, self.value_title)],
                        items
                    )
                )
            else:
                return '\n'.join(
                    '| {key} | {value} |'.format(key=key, value=value)
                    for key, value in chain(
                        [(self.key_title, self.value_title)],
                        items
                    )
                )
        elif spec == 'list':
            return '\n'.join(
                '* {key} = {value}'.format(key=key, value=value)
                for key, value in items
            )
        elif spec == 'refs':
            return '\n'.join(
                '[{key}]: {value}'.format(key=key, value=value)
                for key, value in items
            )
        else:
            raise ValueError('Unknown format spec. {!r}'.format(spec))


def lex(text):
    """
    Internal function which acts as the lexer for :func:`render`.
    """
    row_re = re.compile(r'^\|.*\|$')
    item_re = re.compile(r'^\*')
    ref_re = re.compile(r'^\[[0-9A-Z]+\]:')

    for line in text.splitlines() + ['']:
        line = line.rstrip()
        if row_re.match(line):
            yield 'row', [col.strip() for col in line[1:-1].split('|')]
        elif item_re.match(line):
            yield 'item', line[1:].strip()
        elif ref_re.match(line):
            ref, link = line.split(':', 1)
            yield 'ref', (ref, link.strip())
        elif line:
            yield 'line', line.strip()
        else:
            yield 'blank', None
    # Always yield a final "blank" just to make the outer parser easier
    yield 'blank', None


def parse(text):
    """
    Internal function which acts as the parser for :func:`render`.
    """
    state = 'break'
    rows = []
    items = []
    item = []
    para = []

    def start_table():
        nonlocal rows
        rows = [s]
        return 'table/row'

    def start_list():
        nonlocal item, items
        item = [s]
        items = []
        return 'list/item'

    def start_refs():
        nonlocal items
        items = [s]
        return 'refs'

    def start_para():
        nonlocal para
        para = [s]
        return 'para'

    def start_break():
        return 'break'

    switch = {
        'row':   start_table,
        'item':  start_list,
        'ref':   start_refs,
        'line':  start_para,
        'blank': start_break,
    }

    try:
        for token, s in lex(text):
            if state == 'break':
                state = switch[token]()
            elif state == 'table/row':
                if token == 'row':
                    rows.append(s)
                else:
                    yield 'table', rows
                    state = switch[token]()
            elif state == 'list/item':
                if token == 'line':
                    item.append(s)
                else:
                    items.append(' '.join(item))
                    if token == 'item':
                        item = [s]
                    elif token == 'blank':
                        state = 'list'
                    else:
                        yield 'list', items
                        state = switch[token]()
            elif state == 'list':
                if token == 'item':
                    state = 'list/item'
                    item = [s]
                else:
                    yield 'list', items
                    state = switch[token]()
            elif state == 'refs':
                if token == 'ref':
                    items.append(s)
                else:
                    yield 'refs', items
                    state = switch[token]()
            elif state == 'para':
                if token == 'line':
                    para.append(s)
                else:
                    yield 'para', ' '.join(para)
                    state = switch[token]()
            else:
                assert False, 'invalid state'
    except KeyError:
        assert False, 'invalid token'

    assert state == 'break'


def render(text, width=70, list_space=False, table_style=None):
    """
    A crude renderer for a crude markup language intended for formatting
    documentation for the console.

    The markup recognized by this routine is as follows:

    .. code-block:: text

        * Paragraphs must be separated by at least one blank line. They will be
          wrapped to *width*.

        * Items in bulleted lists must start with an asterisk. No list nesting
          is permitted, but items may span several lines (without blank lines
          between them). Items will be wrapped to *width* and indented
          appropriately.

        * Lines beginning and ending with a pipe character are assumed to be
          table rows. Pipe characters also delimit columns within the row. The
          first row is assumed to be a header row and will be separated from
          the rest.

        An example table is shown below:

        | Command | Description |
        | cd | changes the current directory |
        | ls | lists the content of a directory |
        | cp | copies files |
        | mv | renames files |
        | rm | removes files |
    """
    if table_style is None:
        table_style = {}
    para_wrapper = TextWrapper(width=width)
    list_wrapper = TextWrapper(width=width, initial_indent='* ',
                               subsequent_indent='  ')
    table_wrapper = TableWrapper(width=width, **table_style)
    chunks = []
    for token, data in parse(dedent(text)):
        if token == 'para':
            chunks.append(para_wrapper.fill(data))
        elif token == 'list':
            if list_space:
                for item in data:
                    chunks.append(list_wrapper.fill(item))
            else:
                chunks.append('\n'.join(
                    list_wrapper.fill(item)
                    for item in data
                ))
        elif token == 'refs':
            ref_len = max(len(ref) for ref, link in data)
            chunks.append('\n'.join(
                para_wrapper.fill('{ref}:{space} {link}'.format(
                    ref=ref, link=link, space=' ' * (ref_len - len(ref))))
                for ref, link in data
            ))
        elif token == 'table':
            chunks.append(table_wrapper.fill(data))
        else:
            assert False, 'invalid render state'
    return '\n\n'.join(chunks)
