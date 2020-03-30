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
diff
====

.. program:: pibootctl-diff


Synopsis
========

.. code-block:: text

    pibootctl diff [-h] [--json | --yaml | --shell] [left] right


Description
===========

Display the settings that differ between two stored boot configurations, or
between one stored boot configuration and the current configuration.


Options
=======

.. option:: left

    The boot configuration to compare from, or the current configuration if
    omitted.

.. option:: right

    The boot configuration to compare against.

.. option:: -h, --help

    Show a brief help page for the command.

.. option:: --json

    Use JSON as the output format.

.. option:: --yaml

    Use YAML as the output format.

.. option:: --shell

    Use a tab-delimited output format suitable for the shell.


Usage
=====

The :command:`diff` command is used to display the differences between two boot
configurations; either two stored configurations (if two names are supplied on
the command line), or between the current boot configuration and a stored one
(if one name is supplied on the command line):

.. code-block:: console

    $ sudo pibootctl save default
    $ sudo pibootctl set video.hdmi0.group=1 video.hdmi0.mode=4
    $ pibootctl diff default
    +-------------------+----------------+--------------------+
    | Name              | <Current>      | default            |
    |-------------------+----------------+--------------------|
    | video.hdmi0.group | 1 (CEA)        | 0 (auto from EDID) |
    | video.hdmi0.mode  | 4 (720p @60Hz) | 0 (auto from EDID) |
    +-------------------+----------------+--------------------+
    $ sudo pibootctl save 720p
    $ pibootctl diff default 720p
    +-------------------+--------------------+----------------+
    | Name              | default            | 720p           |
    |-------------------+--------------------+----------------|
    | video.hdmi0.group | 0 (auto from EDID) | 1 (CEA)        |
    | video.hdmi0.mode  | 0 (auto from EDID) | 4 (720p @60Hz) |
    +-------------------+--------------------+----------------+

For developers wishing to build on top of pibootctl, options are provided to
produce the output in JSON (:option:`--json`), YAML (:option:`--yaml`), and
shell-friendly (:option:`--shell`):

.. code-block:: console

    $ pibootctl diff --json default 720p
    {"video.hdmi0.mode": {"right": 4, "left": 0}, "video.hdmi0.group":
    {"right": 1, "left": 0}}
