====
save
====

.. program:: pibootctl-save


Synopsis
========

.. code-block:: text

    pibootctl save [-h] [-f] name


Description
===========

Store the current boot configuration under a given name.


Options
=======

.. option:: name

    The name to save the current boot configuration under; can include any
    characters legal in a filename

.. option:: -h, --help

    Show a brief help page for the command.

.. option:: -f, --force

    Overwrite an existing configuration, if one exists


Usage
=====

The :command:`save` command is used to take a backup of the current boot
configuration. In practice this creates a `PKZIP`_ of the files that make up
the boot configuration (:file:`config.txt` et al.), and places it under the
configured directory on the boot partition (usually :file:`pibootctl`):

.. code-block:: console

    $ ls /boot/pibootctl
    $ sudo pibootctl save foo
    $ ls /boot/pibootctl
    foo.zip

Note that by default, you cannot overwrite saved configurations, but this can
be overridden with the :option:`--force` option:

.. code-block:: console

    $ sudo pibootctl save foo
    [Errno 17] File exists: 'foo.zip'
    $ sudo pibootctl save -f foo

In the event that your system is rendered un-bootable, a boot configuration can
be easily restored by extracting the PKZIP of a saved configuration into the
boot partition (over-writing files as necessary). Alternatively you can use the
:doc:`load` command (if the system can boot). The :doc:`list` command can be
used to display all currently stored configurations.

.. _PKZIP: https://en.wikipedia.org/wiki/Zip_(file_format)
