======
status
======

.. program:: pictl-status


Synopsis
========

.. code-block:: text

    pictl status [-h] [-a] [--json | --yaml | --shell] [pattern]


Description
===========

Output the current value of modified boot time settings that match the
specified pattern (or all if no pattern is provided). The :option:`--all`
option may be specified to output all boot settings regardless of modification
state.


Options
=======

.. option:: pattern

    If specified, only displays settings with names that match the specified
    *pattern* which may include shell globbing characters (e.g. \*, ?, and
    simple [classes]).

.. option:: -h, --help

    Show a brief help page for the command.

.. option:: -a, --all

    Include all settings, regardless of modification, in the output. By
    default, only settings which have been modified are included.

.. option:: --json

    Use JSON as the output format.

.. option:: --yaml

    Use YAML as the output format.

.. option:: --shell

    Use a var=value format suitable for the shell.


Usage
=====

By default, the ``status`` command only outputs boot time settings which have
been modified:

.. code-block:: console

    $ pictl status
    +-------------+-------+
    | Name        | Value |
    |-------------+-------|
    | i2c.enabled | on    |
    | spi.enabled | on    |
    +-------------+-------+

The full set of settings (which is usually several pages long, and thus will
implicitly invoke the system's pager) can be displayed with the
:option:`--all` option:

.. code-block:: console

    $ pictl status --all
    +------------------------------+----------+--------------------------+
    | Name                         | Modified | Value                    |
    |------------------------------+----------+--------------------------|
    ...
    | i2c.baud                     |          | 100000                   |
    | i2c.enabled                  | x        | on                       |
    | i2s.enabled                  |          | off                      |
    | serial.baud                  |          | 115200                   |
    | serial.clock                 |          | 48000000                 |
    | serial.enabled               |          | on                       |
    | serial.uart                  |          | 0 (/dev/ttyAMA0; PL011)  |
    | spi.enabled                  | x        | on                       |
    | video.cec.enabled            |          | on                       |
    ...

Note that when :option:`--all` is specified, a "Modified" column is included in
the output to indicate which settings are no longer default.

The list of settings can be further filtered by specified a *pattern* with the
command. The *pattern* can include any of the common shell wildcard characters:

* ``*`` for any number of any character
* ``?`` for any single character
* ``[seq]`` for any character in *seq*
* ``[!seq]`` for any character not in *seq*

For example:

.. code-block:: console

    $ pictl status --all i2c.*
    +-------------+----------+--------+
    | Name        | Modified | Value  |
    |-------------+----------+--------|
    | i2c.baud    |          | 100000 |
    | i2c.enabled | x        | on     |
    +-------------+----------+--------+

For developers wishing to build on top of pictl, options are provided to
produce the output in JSON (:option:`--json`), YAML (:option:`--yaml`), and
shell-friendly (:option:`--shell`). These combine with all aforementioned
options as expected:

.. code-block:: console

    $ pictl status --json --all i2c.*
    {"i2c.baud": 100000, "i2c.enabled": true}
