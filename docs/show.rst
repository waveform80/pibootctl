.. Copyright (c) 2020 Canonical Ltd.
.. Copyright (c) 2020 Dave Jones <dave@waveform.org.uk>
..
.. This file is part of pibootctl.
..
.. pibootctl is free software: you can redistribute it and/or modify
.. it under the terms of the GNU General Public License as published by
.. the Free Software Foundation, either version 3 of the License, or
.. (at your option) any later version.
..
.. pibootctl is distributed in the hope that it will be useful,
.. but WITHOUT ANY WARRANTY; without even the implied warranty of
.. MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
.. GNU General Public License for more details.
..
.. You should have received a copy of the GNU General Public License
.. along with pibootctl.  If not, see <https://www.gnu.org/licenses/>.

====
show
====

.. program:: pibootctl-show


Synopsis
========

.. code-block:: text

    pibootctl show [-h] [-a] [--json | --yaml | --shell] name [pattern]


Description
===========

Display the specified stored boot configuration, or the sub-set of its settings
that match the specified pattern.


Options
=======

.. option:: name

    The name of the boot configuration to display.

.. option:: pattern

    If specified, only displays settings with names that match the specified
    pattern which may include shell globbing characters (e.g. \*, ?, and simple
    [classes])

.. option:: -h, --help

    Show a brief help page for the command.

.. option:: -a, --all

    Include all settings, regardless of modification, in the output; by
    default, only settings which have been modified are included.

.. option:: --json

    Use JSON as the output format.

.. option:: --yaml

    Use YAML as the output format.

.. option:: --shell

    Use a var=value output format suitable for the shell.


Usage
=====

The :command:`show` command is the equivalent of the :doc:`status` command for
stored boot configurations. By default it displays only the settings in the
specified configuration that have been modified from their default:

.. code-block:: console

    $ pibootctl show 720p
    +------------------------+----------------+
    | Name                   | Value          |
    |------------------------+----------------|
    | video.hdmi0.group      | 1 (CEA)        |
    | video.hdmi0.mode       | 4 (720p @60Hz) |
    +------------------------+----------------+

The full set of settings can be displayed (which is usually several pages long,
and thus will implicitly invoke the system's pager) can be displayed with the
:option:`--all` option:

.. code-block:: console

    $ pibootctl show 720p --all
    +------------------------------+----------+--------------------------------+
    | Name                         | Modified | Value                          |
    |------------------------------+----------+--------------------------------|
    ...
    | video.hdmi0.enabled          |          | auto                           |
    | video.hdmi0.encoding         |          | 0 (auto; 1 for CEA, 2 for DMT) |
    | video.hdmi0.flip             |          | 0 (none)                       |
    | video.hdmi0.group            | x        | 1 (CEA)                        |
    | video.hdmi0.mode             | x        | 4 (720p @60Hz)                 |
    | video.hdmi0.mode.force       |          | off                            |
    | video.hdmi0.rotate           |          | 0                              |
    | video.hdmi0.timings          |          | []                             |
    | video.hdmi1.audio            |          | auto                           |
    | video.hdmi1.boost            |          | 5                              |
    ...

Note that when :option:`--all` is specified, a "Modified" column is included in
the output to indicate which settings are no longer default.

As with the :doc:`status` command, the list of settings can be further filtered
by specified a *pattern* with the command. The *pattern* can include any of the
common shell wildcard characters:

* ``*`` for any number of any character
* ``?`` for any single character
* ``[seq]`` for any character in *seq*
* ``[!seq]`` for any character not in *seq*

For example:

.. code-block:: console

    $ pibootctl show --all 720p i2c.*
    +-------------+----------+--------+
    | Name        | Modified | Value  |
    |-------------+----------+--------|
    | i2c.baud    |          | 100000 |
    | i2c.enabled |          | off    |
    +-------------+----------+--------+

For developers wishing to build on top of pibootctl, options are provided to
produce the output in JSON (:option:`--json`), YAML (:option:`--yaml`), and
shell-friendly (:option:`--shell`). These combine with all aforementioned
options as expected:

.. code-block:: console

    $ pibootctl show --json --all 720p i2c.*
    {"i2c.baud": 100000, "i2c.enabled": false}
