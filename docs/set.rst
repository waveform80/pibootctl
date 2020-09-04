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
set
===

.. program:: pibootctl-set


Synopsis
========

.. code-block:: text

    pibootctl set [-h] [--no-backup] [--all | --this-model | --this-serial]
                  [--json] [--yaml] [--shell]
                  [name=[value] [name=[value] ...]]


Description
===========

Change the value of one or more boot configuration settings. To reset the value
of a setting to its default, simply omit the new value.


Options
=======

.. option:: name=[value]

    Specify one or more settings to change on the command line; to reset a
    setting to its default omit the value.

.. option:: -h, --help

    Show a brief help page for the command.

.. option:: --no-backup

    Don't take an automatic backup of the current boot configuration if one
    doesn't exist.

.. option:: --all

    Set the specified settings on all Pis this SD card is used with. This is
    the default context.

.. option:: --this-model

    Set the specified settings for this model of Pi only.

.. option:: --this-serial

    Set the specified settings for this Pi's serial number only.

.. option:: --json

    Use JSON as the input format.

.. option:: --yaml

    Use YAML as the input format.

.. option:: --shell

    Use a var=value input format suitable for the shell.


Usage
=====

The :command:`set` command can be used at the command line to update the boot
configuration:

.. code-block:: console

    $ sudo pibootctl set video.overscan.enabled=off
    Backed up current configuration in backup-20200309-230959

Note that, if no backup of the current boot configuration exists, a backup is
automatically taken (unless :option:`--no-backup` is specified). Multiple
settings can be changed at once, and settings can be reset to their default
value by omitting the new value after the "=" sign:

.. code-block:: console

    $ sudo pibootctl set --no-backup serial.enabled=on serial.uart=

By default, settings are written into an "[all]" section in :file:`config.txt`
meaning that they will apply everywhere the SD card is moved. However, you can
opt to make settings specific to the current model of Pi, or even the current
Pi's serial number:

.. code-block:: console

    $ sudo pibootctl set --this-serial camera.enabled=on gpu.mem=128

In this case an appropriate section like "[0x123456789]" will be added and the
settings written under there.

For those wishing to build an interface on top of pibootctl, JSON, YAML, and
shell-friendly formats can also be used to feed new values to the
:command:`set` command:

.. code-block:: console

    $ cat << EOF | sudo pibootctl set --json --no-backup
    {"serial.enabled": true, "serial.uart": null}
    EOF
