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
