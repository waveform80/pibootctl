====
help
====

.. program:: pibootctl-help


Synopsis
========

.. code-block:: text

    pibootctl help [-h] [command | setting]


Description
===========

With no arguments, displays the list of :command:`pibootctl` commands. If a
command name is given, displays the description and options for the named
command. If a setting name is given, displays the description and default value
for that setting.


Options
=======

.. option:: -h, --help

    Show a brief help page for the command.

.. option:: command

    The name of the command to output help for. The full command name must be
    given; abbreviations are not accepted.

.. option:: setting

    The name of the setting to output help for.

    If the setting is not recognized, and contains an underscore ('_')
    character, the utility will assume it is a config.txt configuration command
    and attempt to output help for the setting that corresponds to it. If
    multiple settings correspond, their names will be printed instead.


Usage
=====

The :command:`help` command is the default command, and thus will be invoked if
:command:`pibootctl` is called with no other arguments. However it can also be
used to retrieve help for specific commands:

.. code-block:: console

    $ pibootctl help ls
    usage: pibootctl list [-h] [--json | --yaml | --shell]

    List all stored boot configurations.

    optional arguments:
      -h, --help  show this help message and exit
      --json      Use JSON as the format
      --yaml      Use YAML as the format
      --shell     Use a var=value or tab-delimited format suitable for the
                  shell

Alternatively, it can be used to describe settings:

.. code-block:: console

    $ pibootctl help boot.debug.enabled
          Name: boot.debug.enabled
       Default: off
    Command(s): start_debug, start_file, fixup_file

    Enables loading the debugging firmware. This implies that start_db.elf (or
    start4db.elf) will be loaded as the GPU firmware rather than the default
    start.elf (or start4.elf). Note that the debugging firmware incorporates
    the camera firmware so this will implicitly switch camera.enabled on if it
    is not already.

    The debugging firmware performs considerably more logging than the default
    firmware but at a performance cost, ergo it should only be used when
    required.

Finally, if you are more familiar with the "classic" boot configuration
commands, it can be used to discover which :command:`pibootctl` settings
correspond to those commands:

.. code-block:: console

    $ pibootctl help start_file
    start_file is affected by the following settings:

    camera.enabled
    boot.debug.enabled
    boot.firmware.filename
