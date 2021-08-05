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

=========
pibootctl
=========

.. program:: pibootctl


Synopsis
========

.. code-block:: text

    pibootctl [-h] [--version] command ...


Description
===========

The :command:`pibootctl` utility exists to query and manipulate the boot
configuration of the Raspberry Pi. It also permits easy storage and retrieval
of boot configurations. Each of the commands provided by the utility are listed
in the following section.


Commands
========

.. include:: commands.rst

Usage
=====

Typically, the :doc:`status` command is the first used, to determine the
current boot configuration:

.. code-block:: console

    $ pibootctl status
    +------------------------+-------+
    | Name                   | Value |
    |------------------------+-------|
    | i2c.enabled            | on    |
    | spi.enabled            | on    |
    | video.overscan.enabled | off   |
    +------------------------+-------+

After which the :doc:`save` command might be used to take a backup of the
configuration before editing it with the :doc:`set` command:

.. code-block:: console

    $ sudo pibootctl save default
    $ sudo pibootctl set camera.enabled=on gpu.mem=128
    $ sudo pibootctl save cam

.. note::

    Note that commands which modify the content of the boot partition (e.g.
    :doc:`save` and :doc:`set`) are executed with :command:`sudo` as root
    privileges are typically required.

The configuration of :program:`pibootctl` itself dictates where the stored
configurations are placed on disk. By default this is under a "pibootctl"
directory on the boot partition, but this can be changed in the
:program:`pibootctl` configuration. The application attempts to read its
configuration from the following locations on startup:

* :file:`/lib/pibootctl/pibootctl.conf`
* :file:`/etc/pibootctl.conf`
* :file:`$XDG_CONFIG_HOME/pibootctl.conf`

The final location is only intended for developers working on
:program:`pibootctl` itself. The others should be used by packages providing
pibootctl on your chosen OS.

Stored boot configurations are simply `PKZIP`_ files containing the files that
make up the boot configuration (sometimes this is just the :file:`config.txt`
file, and sometimes other files may be included).

.. note::

    In the event that your system is unable to boot (e.g. because of
    mis-configuration), you can restore a stored boot configuration simply by
    unzipping the stored configuration back into the root of the boot
    partition.

    In other words, you can simply place your Pi's SD card in a Windows or MAC
    OS X computer which should automatically mount the boot partition (which is
    the only partition that these OS' will understand on the card), find the
    "pibootctl" folder and under there you should see all your stored
    configurations as .zip files. Unzip one of these into the folder above
    "pibootctl", overwriting files as necessary and you have restored your boot
    configuration.

The :doc:`diff` command can be used to discover the differences between
boot configurations:

.. code-block:: console

    $ pibootctl diff default
    +------------------------+---------------+-------------+
    | Name                   | <Current>     | default     |
    |------------------------+---------------+-------------|
    | boot.firmware.filename | 'start_x.elf' | 'start.elf' |
    | boot.firmware.fixup    | 'fixup_x.dat' | 'fixup.dat' |
    | camera.enabled         | on            | off         |
    | gpu.mem                | 128 (Mb)      | 64 (Mb)     |
    +------------------------+---------------+-------------+

.. note::

    Some settings indirectly affect others. Even though we did not explicitly
    set ``boot.firmware.filename``, setting ``camera.enabled`` affected its
    default value.

The :doc:`help` command can be used to display the help screen for each
sub-command:

.. code-block:: console

    $ pibootctl help save
    usage: pibootctl save [-h] [-f] name

    Store the current boot configuration under a given name.

    positional arguments:
      name         The name to save the current boot configuration under; can
                   include any characters legal in a filename

    optional arguments:
      -h, --help   show this help message and exit
      -f, --force  Overwrite an existing configuration, if one exists

Additionally, :doc:`help` will accept setting names to display information
about the defaults and underlying commands each setting represents:

.. code-block:: console

    $ pibootctl help camera.enabled
          Name: camera.enabled
       Default: off
    Command(s): start_x, start_debug, start_file, fixup_file

    Enables loading the Pi camera module firmware. This implies that
    start_x.elf (or start4x.elf) will be loaded as the GPU firmware rather than
    the default start.elf (and the corresponding fixup file).

    Note: with the camera firmware loaded, gpu.mem must be 64Mb or larger
    (128Mb is recommended for most purposes; 256Mb may be required for complex
    processing pipelines).

The :doc:`list` command can be used to display the content of the configuration
store, and :doc:`load` to restore previously saved configurations:

.. code-block:: console

    $ pibootctl list
    +---------+--------+---------------------+
    | Name    | Active | Timestamp           |
    |---------+--------+---------------------|
    | cam     | x      | 2020-03-11 21:29:56 |
    | default |        | 2020-03-11 21:29:13 |
    +---------+--------+---------------------+
    $ sudo pibootctl load default


.. _PKZIP: https://en.wikipedia.org/wiki/Zip_(file_format)
