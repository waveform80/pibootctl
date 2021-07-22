# Copyright (c) 2021 Canonical Ltd.
# Copyright (c) 2021 Dave Jones <dave@waveform.org.uk>
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
The :mod:`pibootctl.corrections` module contains a rudimentary implementation
of an `edit distance`_ algorithm for the purposes of correcting the spelling of
interactively entered command line parameters. For example, the user attempts
to query::

    $ pibootctl help audio.enbaled

We would like to return something helpful like:

    Setting 'audio.enbaled' not found, did you mean:

    - audio.enabled

This module provides the function, :func:`corrections` which enables this
facility:

.. autofunction:: corrections

All other contents in this module are simply support structures and functions
for :func:`corrections`, but are documented here for completeness:

.. autoclass:: Graph

.. data:: Any

.. data:: Empty

.. autofunction:: build

.. autofunction:: traverse

.. note::

    It would potentially be more efficient to turn this into a `DFA`_ with a
    `powerset construction`_, but for the intended edit distances (1-5) and
    tiny corpus sizes (<1000) this is simpler to comprehend and sufficiently
    fast, even on a Pi.

.. _edit distance: https://en.wikipedia.org/wiki/Edit_distance
.. _DFA: https://en.wikipedia.org/wiki/Deterministic_finite_automaton
.. _powerset construction: https://en.wikipedia.org/wiki/Powerset_construction
"""

from operator import itemgetter


class Graph:
    """
    A trivial graph class capable of representing a non-deterministic finite
    automaton (`NFA`_).

    The class must be constructed with a *start* state. New edges are added by
    calling the :meth:`add_edge` method, and final states are marked by calling
    :meth:`make_final`.

    The :attr:`dot` property can be used to output the graph in the graphviz
    `dot language`_ for easier debugging. Finally, edges can be "marked" with
    the :meth:`mark_edge` method, which is also a debugging aid (marked edges
    will be output in red in the dot output).

    .. _NFA: https://en.wikipedia.org/wiki/Nondeterministic_finite_automaton
    .. _dot language: https://graphviz.org/doc/info/lang.html
    """
    def __init__(self, start):
        self._final = set()
        self._marked = set()
        self._start = start
        self._states = {start: {}}

    def add_edge(self, from_state, input, to_state):
        """
        Adds an edge connecting *from_state* to *to_state*, labelled by the
        the specified *input* which must be a valid element of any potential
        input sequence. The connected states can be any hashable value, and
        can be new to the graph.
        """
        state = self._states.setdefault(from_state, {})
        state.setdefault(input, set()).add(to_state)
        # Just to ensure all states exist as keys in self._states which makes
        # debugging a little easier
        self._states.setdefault(to_state, {})

    def make_final(self, state):
        """
        Marks the specified *state* as a final accepting state.
        """
        self._states.setdefault(state, {})
        self._final.add(state)

    def mark_edge(self, state, input):
        """
        Marks the edge from *state*, for the given *input*. This is purely for
        debugging purposes, as the only effect is to render edges red in the
        output from :attr:`dot`.
        """
        self._marked.add((state, input))

    def next_states(self, state, input):
        """
        Return the set of states found by following all edges for the given
        *input* element from the original *state*.
        """
        return self._states[state].get(input, set())

    def is_final(self, state):
        """
        Returns :data:`True` if *state* has been marked as a final state by
        calling :meth:`make_final`.
        """
        return state in self._final

    @property
    def dot(self):
        """
        Returns a string containing a Graphviz `dot script`_ rendering the
        nodes and edges of the graph. This is purely `for debugging purposes`_.

        .. _dot script: https://graphviz.org/doc/info/lang.html
        .. _for debugging purposes: https://twitter.com/thingskatedid/status/1386077306381242371
        """
        nodes = {
            state: "node{i}".format(i=i)
            for i, state in enumerate(self._states)
        }
        return """\
digraph G {{
graph [rankdir=LR];
node [shape=circle, style=filled, fontname=Sans, fontsize=10];
edge [fontname=Sans, fontsize=10];

{nodes}
{edges}
}}""".format(
            nodes='\n'.join(
                '{node} [label="{label}", fillcolor="{color}"];'.format(
                    node=nodes[state], label=repr(state),
                    color='hotpink' if state in self._final else 'white')
                for state in self._states
            ),
            edges='\n'.join(
                '{from_node}->{to_node} '
                '[label="{label}", color="{color}"];'.format(
                    from_node=nodes[from_state], to_node=nodes[to_state],
                    label=str(input),
                    color='red' if (from_state, input) in self._marked else 'black')
                for from_state, edges in self._states.items()
                for input, to_states in edges.items()
                for to_state in to_states
            ),
        )


class Any:
    "Singleton representing any possible input character"
    def __repr__(self):
        return 'Any'
    def __str__(self):
        return '*'
Any = Any()


class Empty:
    "Singleton representing no input character"
    def __repr__(self):
        return 'Empty'
    def __str__(self):
        return "''"
Empty = Empty()


def build(s, max_edits=2):
    """
    Build a `Levenshtein automaton`_ in an `NFA`_ for the input string *s* for
    a given *max_edits*, returning a :class:`Graph` instance.

    Each node is keyed by the tuple ``(index, edits)`` where *index* is the
    character matched in the key-string *s*, and *edits* is the number of edits
    (inserts, deletions, or substitutions) performed thus far.

    .. note::

        The :attr:`Graph.dot` property of the result is useful for visualizing
        the resulting automaton. For example::

            dot -Tpng graph.dot | display png:-

    .. _NFA: https://en.wikipedia.org/wiki/Nondeterministic_finite_automaton
    .. _Levenshtein automaton: https://en.wikipedia.org/wiki/Levenshtein_automaton
    """
    g = Graph((0, 0))
    for index, char in enumerate(s):
        for edits in range(max_edits + 1):
            state = (index, edits)
            g.add_edge(state, char, (index + 1, edits))
            if edits < max_edits:
                g.add_edge(state, Any, (index, edits + 1))
                g.add_edge(state, Empty, (index + 1, edits + 1))
                g.add_edge(state, Any, (index + 1, edits + 1))
    for edits in range(max_edits + 1):
        state = (len(s), edits)
        if edits < max_edits:
            g.add_edge(state, Any, (len(s), edits + 1))
        g.make_final(state)
    return g


def traverse(graph, s):
    """
    A generator function that traverses the NFA *graph* for a given test string
    *s*, yielding all final states that are reached.
    """
    def _inner(state=(0, 0), index=0):
        if index < len(s):
            for new_state in graph.next_states(state, Empty):
                yield from _inner(new_state, index)
            for new_state in graph.next_states(state, Any):
                yield from _inner(new_state, index + 1)
            for new_state in graph.next_states(state, s[index]):
                yield from _inner(new_state, index + 1)
        else:
            if graph.is_final(state):
                yield state
            for new_state in graph.next_states(state, Empty):
                yield from _inner(new_state, index)
    yield from _inner()


def corrections(query, corpus, max_edits=2):
    """
    Given a (presumably incorrect) *query* string, and a *corpus* of correct
    strings, this function returns a sorted list of entries from *corpus* that
    are at most *max_edits* (inserts, deletions, or substitutions) "away" from
    the *query* string.
    """
    g = build(query, max_edits)
    results = {
        (s, min(
            {edits for index, edits in traverse(g, s)},
            default=max_edits + 1))
        for s in corpus
    }
    results = {
        (s, edits)
        for s, edits in results
        if edits <= max_edits
    }
    results = sorted(results, key=itemgetter(1))
    return [s for s, edits in results]
