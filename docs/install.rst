============
Installation
============

If your distribution provides pibootctl then you should either find the utility
is installed by default, or it should be installable via your package manager.
For example:

.. code-block:: console

    $ sudo apt install pibootctl

It is strongly recommended to use a provided package rather than installing
from PyPI as this will include configuration specific to your distribution. The
utility can be removed via the usual mechanism for your package manager. For
instance:

.. code-block:: console

    $ sudo apt purge pibootctl


Configuration
=============

pibootctl looks for its configuration in three locations:

#. :file:`/lib/pibootctl/pibootctl.conf`

#. :file:`/etc/pibootctl.conf`

#. :file:`~/.config/pibootctl.conf`

The last location is only intended for use by people developing pibootctl; for
the vast majority of users the configuration should be provided by their
distribution in one of the first two locations.

The configuration file is a straight-forward INI-style containing a single
section titled "defaults". A typical configuration file might look like this:

.. code-block:: ini

    [defaults]
    boot_path=/boot
    store_path=pibootctl

    config_read=config.txt
    config_write=config.txt
    config_template=
        # This file is changed by pibootctl; manual edits may be lost!
        {config}

    reboot_required=/var/run/reboot-required
    reboot_required_pkgs=/var/run/reboot-required.pkgs
    package_name=pibootctl
    backup=on

The configuration specifies several settings, but the most important are:

``boot_path``
    The mount-point of the boot partition (defaults to :file:`/boot`).

``store_path``
    The path under which to store saved boot configurations, relative to
    ``boot_path`` (defaults to :file:`pibootctl`).

``config_read``
    The "root" configuration file which is read first, relative to
    ``boot_path`` (defaults to :file:`config.txt`).

``config_write``
    The configuration file which pibootctl is permitted to re-write (also
    defaults to :file:`config.txt`). This is used in cases where the default
    configuration includes several files. In this case, pibootctl needs to know
    which file it is allowed to re-write, and assume all other files are
    distribution maintained. This is also relative to ``boot_path``.

``config_template``
    The template to be used when writing the file specified by
    ``config_write``. By default this is simply "{config}" (the bare
    substitution marker for the generated configuration lines). However, this
    setting can be used to add headers, footers, or for that matter additional
    fixed includes or even other configuration settings.

``reboot_required``
    The file which should be created in the event that the active boot
    configuration is changed.

``backup``
    If this is on (the default), any attempt to change the active boot
    configuration will automatically create a backup of that configuration if
    one does not already exist.

Line comments can be included in the configuration file with a ``#`` prefix.
