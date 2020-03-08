===
get
===

.. program:: pictl-get


Synopsis
========

.. code-block:: text

    pictl get [-h] [--json | --yaml | --shell] setting [setting ...]


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

This command is primarily of use to those wishing to build something on top of
pictl; for end users wishing to query the current boot configuration the
:doc:`status` command is of more use. When given a single setting to query the
value of that setting is output on its own, in whatever output style is
selected:

.. code-block:: console

    $ pictl get video.overscan.enabled
    on
    $ pictl get --json video.overscan.enabled
    true

When given multiple settings, names and values of those settings are both
output:

.. code-block:: console

    $ pictl get serial.enabled serial.baud serial.uart
    +----------------+-------------------------+
    | Name           | Value                   |
    |----------------+-------------------------|
    | serial.baud    | 115200                  |
    | serial.enabled | on                      |
    | serial.uart    | 0 (/dev/ttyAMA0; PL011) |
    +----------------+-------------------------+
    $ pictl get --json serial.enabled serial.baud serial.uart
    {"serial.enabled": true, "serial.baud": 115200, "serial.uart": 0}

Note that wildcards are not permitted with this command, unlike with the
:doc:`status` command.
