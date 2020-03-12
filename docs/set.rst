===
set
===

.. program:: pictl-set


Synopsis
========

.. code-block:: text

    pictl set [-h] [--no-backup] [--json] [--yaml] [--shell]
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

    $ sudo pictl set video.overscan.enabled=off
    Backed up current configuration in backup-20200309-230959

Note that, if no backup of the current boot configuration exists, a backup is
automatically taken (unless :option:`--no-backup` is specified). Multiple
settings can be changed at once, and settings can be reset to their default
value by omitting the new value after the "=" sign:

.. code-block:: console

    $ sudo pictl set --no-backup serial.enabled=on serial.uart=

For those wishing to build an interface on top of pictl, JSON, YAML, and
shell-friendly formats can also be used to feed new values to the
:command:`set` command:

.. code-block:: console

    $ cat << EOF | sudo pictl set --json --no-backup
    {"serial.enabled": true, "serial.uart": null}
    EOF
