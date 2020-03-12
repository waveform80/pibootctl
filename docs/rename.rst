======
rename
======

.. program:: pibootctl-rename


Synopsis
========

.. code-block:: text

    pibootctl rename [-h] [-f] name to


Description
===========

Rename a stored boot configuration.


Options
=======

.. option:: name

    The name of the boot configuration to rename.

.. option:: to

    The new name of the boot configuration.

.. option:: -h, --help

    Show a brief help page for the command.

.. option:: -f, --force

    Overwrite the target configuration, if it exists.


Usage
=====

The :command:`rename` command can be used to change the name of a stored boot
configuration:

.. code-block:: console

    $ pibootctl ls
    +---------+--------+---------------------+
    | Name    | Active | Timestamp           |
    |---------+--------+---------------------|
    | 720p    | x      | 2020-03-10 11:33:24 |
    | default |        | 2020-03-10 11:32:12 |
    | dpi     |        | 2020-02-01 15:46:48 |
    +---------+--------+---------------------+
    $ sudo pibootctl rename default foo
    $ pibootctl ls
    +------+--------+---------------------+
    | Name | Active | Timestamp           |
    |------+--------+---------------------|
    | 720p | x      | 2020-03-10 11:33:24 |
    | dpi  |        | 2020-02-01 15:46:48 |
    | foo  |        | 2020-03-10 11:32:12 |
    +------+--------+---------------------+

As with :doc:`save`, any characters permitted in a filename are permitted in
the new destination name.

If you wish to rename a configuration such that it overwrites an existing
configuration you will need to use the :option:`--force` option:

.. code-block:: console

    $ sudo pibootctl load default
    $ sudo pibootctl save foo
    $ pibootctl ls
    +---------+--------+---------------------+
    | Name    | Active | Timestamp           |
    |---------+--------+---------------------|
    | 720p    |        | 2020-03-10 11:33:24 |
    | default | x      | 2020-03-10 11:32:12 |
    | dpi     |        | 2020-02-01 15:46:48 |
    | foo     | x      | 2020-03-10 11:32:12 |
    +---------+--------+---------------------+
    $ sudo pibootctl mv foo default
    [Errno 17] File exists: 'default.zip'
    $ sudo pibootctl mv -f foo default
