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


from pibootctl.corrections import *


def test_singletons():
    assert repr(Any) == 'Any'
    assert repr(Empty) == 'Empty'
    assert str(Any) == '*'
    assert str(Empty) == "''"


def test_graph_init():
    g = Graph(0)
    g.add_edge(0, 'f', 1)
    g.add_edge(1, 'o', 2)
    g.add_edge(2, 'o', 3)
    g.make_final(3)
    assert g._start == 0
    assert g._states == {0: {'f': {1}}, 1: {'o': {2}}, 2: {'o': {3}}, 3: {}}
    assert g._final == {3}


def test_graph_next():
    g = Graph(0)
    g.add_edge(0, 'f', 1)
    g.add_edge(1, 'o', 2)
    g.add_edge(1, 'o', 3)
    g.add_edge(2, 'o', 3)
    g.add_edge(2, Any, 3)
    g.make_final(3)
    assert g.next_states(0, 'f') == {1}
    assert g.next_states(1, 'o') == {2, 3}
    assert g.next_states(1, 'b') == set()


def test_graph_final():
    g = Graph(0)
    g.add_edge(0, 'f', 1)
    g.add_edge(1, 'o', 2)
    g.add_edge(1, 'o', 3)
    g.add_edge(2, 'o', 3)
    g.add_edge(2, Any, 3)
    g.make_final(3)
    assert g.is_final(3)
    assert not g.is_final(0)


def test_graph_debug():
    g = Graph(0)
    g.add_edge(0, 'f', 1)
    g.add_edge(1, 'o', 2)
    g.add_edge(2, 'o', 3)
    g.make_final(3)
    g.mark_edge(0, 'f')
    g.mark_edge(1, 'o')
    assert g.dot == """\
digraph G {
graph [rankdir=LR];
node [shape=circle, style=filled, fontname=Sans, fontsize=10];
edge [fontname=Sans, fontsize=10];

node0 [label="0", fillcolor="white"];
node1 [label="1", fillcolor="white"];
node2 [label="2", fillcolor="white"];
node3 [label="3", fillcolor="hotpink"];
node0->node1 [label="f", color="red"];
node1->node2 [label="o", color="red"];
node2->node3 [label="o", color="black"];
}"""


def test_build_nfa():
    g = build('pi', max_edits=2)
    assert g._states == {
        (0, 0): {'p': {(1, 0)}, Any: {(0, 1), (1, 1)}, Empty: {(1, 1)}},
        (1, 0): {'i': {(2, 0)}, Any: {(1, 1), (2, 1)}, Empty: {(2, 1)}},
        (2, 0): {Any: {(2, 1)}},
        (0, 1): {'p': {(1, 1)}, Any: {(0, 2), (1, 2)}, Empty: {(1, 2)}},
        (1, 1): {'i': {(2, 1)}, Any: {(1, 2), (2, 2)}, Empty: {(2, 2)}},
        (2, 1): {Any: {(2, 2)}},
        (0, 2): {'p': {(1, 2)}},
        (1, 2): {'i': {(2, 2)}},
        (2, 2): {},
    }
    assert g._final == {(2, 0), (2, 1), (2, 2)}


def test_traverse_nfa():
    g = build('pi', max_edits=2)
    assert set(traverse(g, 'pi')) == {(2, 0), (2, 1), (2, 2)}
    assert set(traverse(g, 'pig')) == {(2, 1), (2, 2)}
    assert set(traverse(g, 'foo')) == set()


def test_corrections():
    corpus = {'pi', 'pig', 'foo', 'bar'}
    assert corrections('pi', corpus, max_edits=2) == ['pi', 'pig']
    assert corrections('pig', corpus, max_edits=2) == ['pig', 'pi']
    assert corrections('doom', corpus, max_edits=2) == ['foo']
    assert corrections('quux', corpus, max_edits=2) == []
