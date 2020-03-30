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

======
remove
======

.. program:: pibootctl-remove


Synopsis
========

.. code-block:: text

    pibootctl remove [-h] [-f] name


Description
===========

Remove a stored boot configuration.


Options
=======

.. option:: name

    The name of the boot configuration to remove.

.. option:: -h, --help

    Show a brief help page for the command.

.. option:: -f, --force

    Ignore errors if the named configuration does not exist.


Usage
=====

The :command:`remove` command is used to delete a stored boot configuration:

.. code-block:: console

    $ pibootctl list
    +---------+--------+---------------------+
    | Name    | Active | Timestamp           |
    |---------+--------+---------------------|
    | 720p    | x      | 2020-03-10 11:33:24 |
    | default |        | 2020-03-10 11:32:12 |
    | dpi     |        | 2020-02-01 15:46:48 |
    | gpi     |        | 2020-02-01 16:13:02 |
    +---------+--------+---------------------+
    $ sudo pibootctl remove gpi
    $ pibootctl list
    +---------+--------+---------------------+
    | Name    | Active | Timestamp           |
    |---------+--------+---------------------|
    | 720p    | x      | 2020-03-10 11:33:24 |
    | default |        | 2020-03-10 11:32:12 |
    | dpi     |        | 2020-02-01 15:46:48 |
    +---------+--------+---------------------+

If, for scripting purposes, you wish to ignore the error in the case the
specified stored configuration does not exist, use the :option:`--force`
option:

.. code-block:: console

    $ pibootctl rm foo
    unknown configuration foo
    $ pibootctl rm -f foo
