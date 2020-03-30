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

===
get
===

.. program:: pibootctl-get


Synopsis
========

.. code-block:: text

    pibootctl get [-h] [--json | --yaml | --shell] setting [setting ...]


Description
===========

Query the status of one or more boot configuration settings. If a single
setting is requested then just that value is output. If multiple values are
requested then both setting names and values are output. This applies whether
output is in the default, JSON, YAML, or shell-friendly styles.


Options
=======

.. option:: setting

    The name(s) of the setting(s) to query; if a single setting is given its
    value alone is output, if multiple settings are queried the names and
    values of the settings are output.

.. option:: -h, --help

    Show a brief help page for the command.

.. option:: --json

    Use JSON as the output format.

.. option:: --yaml

    Use YAML as the output format.

.. option:: --shell

    Use a var=value output format suitable for the shell.


Usage
=====

The :command:`get` command is primarily of use to those wishing to build
something on top of :command:`pibootctl`; for end users wishing to query the
current boot configuration the :doc:`status` command is of more use. When given
a single setting to query the value of that setting is output on its own, in
whatever output style is selected:

.. code-block:: console

    $ pibootctl get video.overscan.enabled
    on
    $ pibootctl get --json video.overscan.enabled
    true

When given multiple settings, names and values of those settings are both
output:

.. code-block:: console

    $ pibootctl get serial.enabled serial.baud serial.uart
    +----------------+-------------------------+
    | Name           | Value                   |
    |----------------+-------------------------|
    | serial.baud    | 115200                  |
    | serial.enabled | on                      |
    | serial.uart    | 0 (/dev/ttyAMA0; PL011) |
    +----------------+-------------------------+
    $ pibootctl get --json serial.enabled serial.baud serial.uart
    {"serial.enabled": true, "serial.baud": 115200, "serial.uart": 0}

Note that wildcards are not permitted with this command, unlike with the
:doc:`status` command.
