====
list
====

.. program:: pibootctl-list


Synopsis
========

.. code-block:: text

    pibootctl list [-h] [--json | --yaml | --shell]


Description
===========

List all stored boot configurations.


Options
=======

.. option:: -h, --help

    Show a brief help page for the command.

.. option:: --json

    Use JSON as the output format.

.. option:: --yaml

    Use YAML as the output format.

.. option:: --shell

    Use a tab-delimited output format suitable for the shell.


Usage
=====

The :command:`list` command is used to display the content of the store of boot
configurations:

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

If one (or more) of the stored configurations match the current boot
configuration, this will be indicated in the "Active" column. Note that
equivalence is based on a hash of all files in the configuration, not on the
resulting settings. Hence a simple edit like, for example, reversing the order
of two lines (which might not make any difference to the resulting settings)
would be sufficient to mark the configuration as "different".

The "timestamp" of a stored configuration is the last modification date of that
configuration (calculated as the latest modification date of all files within
the configuration).

For developers wishing to build on top of pibootctl, options are provided to
produce the output in JSON (:option:`--json`), YAML (:option:`--yaml`), and
shell-friendly (:option:`--shell`). These combine with all aforementioned
options as expected:

.. code-block:: console

    $ pibootctl list --json
    [{"timestamp": "2020-02-01T15:46:48", "active": false, "name": "dpi"},
    {"timestamp": "2020-03-10T11:32:12", "active": false, "name": "default"},
    {"timestamp": "2020-02-01T16:13:02", "active": false, "name": "gpi"},
    {"timestamp": "2020-03-10T11:33:24", "active": true, "name": "720p"}]
