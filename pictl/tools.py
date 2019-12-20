import gettext
from itertools import tee

_ = gettext.gettext


def to_bool(s):
    """
    Converts the :class:`str` *s* to a :class:`bool`. Various "typical" string
    representations of true and false are accepted including "true", "yes",
    and "on", along with their counter-parts "false", "no", and "off".
    """
    try:
        return {
            'true':  True,
            'yes':   True,
            'on':    True,
            '1':     True,
            'y':     True,
            'false': False,
            'no':    False,
            'off':   False,
            '0':     False,
            'n':     False,
        }[s.strip().lower()]
    except KeyError:
        raise ValueError(_('{value} is not a valid bool').format(value=s))


def to_tri_bool(s):
    """
    Converts the :class:`str` *s* to a :class:`bool` (like :func:`to_bool`) or
    to :data:`None` if *s* is the blank string, or "auto".
    """
    try:
        return {
            '':     None,
            'auto': None,
        }[s.strip().lower()]
    except KeyError:
        return to_bool(s)


def pairwise(it):
    a, b = tee(it)
    next(b, None)
    return zip(a, b)


def int_ranges(values):
    """
    Given a set of integer *values*, returns a compressed string representation
    of all values in the set. For example:

        >>> int_ranges({1, 2})
        '1,2'
        >>> int_ranges({1, 2, 3})
        '1-3'
        >>> int_ranges({1, 2, 3, 4, 8})
        '1-4, 8'
        >>> int_ranges({1, 2, 3, 4, 8, 9})
        '1-4, 8-9'
    """
    if len(values) == 0:
        return ''
    elif len(values) == 1:
        return '{0}'.format(*values)
    elif len(values) == 2:
        return '{0}, {1}'.format(*values)
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
        return ', '.join(
            ('{start}-{finish}' if finish > start else '{start}').format(
                start=start, finish=finish)
            for start, finish in ranges
        )


class TransTemplate(str):
    """
    Used by :class:`TransFormat` to transparently pass unknown format
    templates through for later substitution. When this value is used in a
    :meth:`str.format` substitution, it renders itself with the format
    specification as {self!conv:spec}, passing the template through verbatim.

    .. note::

        One exception is that the ``!a`` conversion is not handled correctly.
        This is erroneously converted to ``!r``. Unfortunately there's no
        solution to this; it's a side-effect of the means by which the ``!a``
        conversion is performed.
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
    in a given template, passing the reset through for later processing. For
    example:

        >>> '{foo}{bar}'.format_map(TransMap(foo=1))
        '1{bar}'
        >>> '{foo:02d}{bar:02d}{baz:02d}'.format_map(TransMap(foo=1, baz=3))
        '01{bar:02d}03'
    """
    def __init__(self, **kw):
        self._kw = kw

    def __contains__(self, key):
        return True

    def __getitem__(self, key):
        return self._kw.get(key, TransTemplate(key))
