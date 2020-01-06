from bisect import bisect
from textwrap import dedent, TextWrapper
from itertools import islice, zip_longest, chain


class TableWrapper:
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
            align = lambda data: '<'
        self.align = align
        if format is None:
            format = lambda data: str(data)
        self.format = format

    def fit_widths(self, widths):
        min_width = sum((
            len(self.borders[0]),
            len(self.borders[2]),
            len(self.cell_separator) * (len(widths) - 1)
        ))
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
        # Construct wrappers for each column width
        wrappers = [TextWrapper(width=width) for width in widths]
        for row in data:
            aligns = [self.align(cell) for cell in row]
            # Construct a list of wrapped lines for each cell in the row; these
            # are not necessarily of equal length (hence zip_longest below)
            cols = [
                wrapper.wrap(self.format(cell))
                for cell, wrapper in zip(row, wrappers)
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
        widths = [
            max(1, max(len(str(item)) for item in row))
            for row in zip(*data)  # transpose
        ]
        widths = self.fit_widths(widths)
        int_width = sum(widths) + len(self.cell_separator) * (len(widths) - 1)
        borders = []
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
        return list(self.generate_lines(data))

    def fill(self, data):
        return '\n'.join(self.wrap(data))


# Some prettier defaults for TableWrapper
pretty_table = {
    'cell_separator': ' | ',
    'internal_line': '-',
    'internal_separator': '-+-',
    'borders': ('| ', '-', ' |', '-'),
    'corners': ('+-', '-+', "-+", '+-'),
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


class FormatDict:
    def __init__(self, data, key_title='Key', value_title='Value'):
        self.data = data
        self.key_title = key_title
        self.value_title = value_title

    def __format__(self, spec):
        if not spec or spec == 'table':
            return '\n'.join(
                '| {key} | {value} |'.format(key=key, value=value)
                for key, value in chain(
                    [(self.key_title, self.value_title)],
                    self.data.items()
                )
            )
        elif spec == 'list':
            return '\n'.join(
                '* {key} = {value}'.format(key=key, value=value)
                for key, value in self.data.items()
            )
        else:
            raise ValueError('Unknown format spec. {!r}'.format(spec))


def lex(text):
    state = 'blank'
    rows = []
    for line in text.splitlines() + ['']:
        line = line.rstrip()
        if line.startswith('|') and line.endswith('|'):
            yield 'row', [col.strip() for col in line[1:-1].split('|')]
        elif line.startswith('*'):
            yield 'item', line[1:].strip()
        elif line:
            yield 'line', line.strip()
        else:
            yield 'blank', None
    # Always yield a final "blank" just to make the outer parser easier
    yield 'blank', None


def parse(text):
    state = 'break'
    for token, s in lex(text):
        if state == 'break':
            if token == 'row':
                state = 'table/row'
                rows = [s]
            elif token == 'item':
                state = 'list/item'
                item = [s]
                items = []
            elif token == 'line':
                state = 'para'
                para = [s]
        elif state == 'table/row':
            if token == 'row':
                rows.append(s)
            else:
                yield 'table', rows
                state = 'break'
        elif state == 'list/item':
            if token == 'item':
                items.append(' '.join(item))
                item = [s]
            elif token == 'line':
                item.append(s)
            else:
                items.append(' '.join(item))
                state = 'list'
        elif state == 'list':
            if token == 'item':
                state = 'list/item'
                item = [s]
            elif token == 'row':
                yield 'list', items
                state = 'table/row'
                rows = [s]
            elif token == 'line':
                yield 'list', items
                state = 'para'
                para = [s]
        elif state == 'para':
            if token == 'row':
                yield 'para', ' '.join(para)
                state = 'table/row'
                rows = [s]
            elif token == 'item':
                yield 'para', ' '.join(para)
                state = 'list/item'
                item = [s]
                items = []
            elif token == 'line':
                para.append(s)
            else:
                yield 'para', ' '.join(para)
                state = 'break'

    # Deal with residual state (lists have indeterminate endings)
    if state == 'list':
        yield 'list', items
        state = 'break'

    assert state == 'break'


def render(text, width=70, list_space=False, table_style=None):
    """
    A crude renderer for a crude markup language intended for formatting
    documentation for the console.

    The markup recognized by this routine is as follows:

    * Paragraphs must be separated by at least one blank line. They will be
      wrapped to *width*.

    * Items in bulleted lists must start with an asterisk. No list nesting is
      permitted, but items may span several lines (without blank lines between
      them). Items will be wrapped to *width* and indented appropriately.

    * Lines beginning and ending with a pipe character are assumed to be table
      rows. Pipe characters also delimit columns within the row. The first row
      is assumed to be a header row and will be separated from the rest. No
      wrapping will be used within the table, but column widths will be
      calculated automatically. If the total column width exceeds *width* the
      table will be right-truncated in the output.

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
        elif token == 'table':
            chunks.append(table_wrapper.fill(data))
    return '\n\n'.join(chunks)
