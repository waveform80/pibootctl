====
load
====

.. program:: pibootctl-load


Synopsis
========

.. code-block:: text

    pibootctl load [-h] [--no-backup] name


Description
===========

Overwrite the current boot configuration with a stored one.


Options
=======

.. option:: name

    The name of the boot configuration to restore

.. option:: -h, --help

    Show a brief help page for the command.

.. option:: --no-backup

    Don't take an automatic backup of the current boot configuration if one
    doesn't exist


Usage
=====

The :command:`load` command is used to replace the current boot configuration
with one previously stored. Effectively this simply unpacks the `PKZIP`_ of the
stored boot configuration into the boot partition, overwriting existing files.

If the current boot configuration has not been stored (with the :doc:`save`
command), an automatically named backup will be saved first:

.. code-block:: console

    $ sudo pibootctl save default
    $ sudo pibootctl set video.hdmi0.group=1 video.hdmi0.mode=4
    $ sudo pibootctl load default
    Backed up current configuration in backup-20200310-095646

This can be avoided with the :option:`--no-backup` option.

.. warning::

    The command is written to guarantee that no files will ever be left
    half-written (files are unpacked to a temporary filename then atomically
    moved into their final location overwriting any existing file).

    However, the utility cannot guarantee that in the event of an error, the
    configuration as a whole is not half-written (i.e. that one or more files
    failed to unpack). In other words, in the event of failure you cannot
    assume that the boot configuration is consistent.

.. _PKZIP: https://en.wikipedia.org/wiki/Zip_(file_format)
