============
Installation
============

If your distribution provides pictl then you should either find the utility
is installed by default, or it should be installable via your package manager.
For example:

.. code-block:: console

    $ sudo apt install pictl

It is strongly recommended to use a provided package rather than installing
from PyPI as this will include configuration specific to your distribution. The
utility can be removed via the usual mechanism for your package manager. For
instance:

.. code-block:: console

    $ sudo apt purge pictl


Configuration
=============

pictl looks for its configuration in three locations:

#. :file:`/lib/pictl/pictl.conf`

#. :file:`/etc/pictl.conf`

#. :file:`~/.config/pictl.conf`

The last location is only intended for use by people developing pictl; for the
vast majority of users the configuration should be provided by their
distribution in one of the first two locations.

The configuration file is a straight-forward INI-style containing a single
section titled "defaults". A typical configuration file might look like this::

    [defaults]
    boot_path=/boot
    store_path=pictl
    config_read=config.txt
    config_write=config.txt
    reboot_required=/var/run/reboot-required
    reboot_required_pkgs=/var/run/reboot-required.pkgs
    package_name=pictl
    backup=on

The configuration specifies several settings, but the most important are:

``boot_path``
    The mount-point of the boot partition (defaults to :file:`/boot`).

``store_path``
    The path under which to store saved boot configurations, relative to
    ``boot_path`` (defaults to :file:`pictl`).

``config_read``
    The "root" configuration file which is read first, relative to
    ``boot_path`` (defaults to :file:`config.txt`).

``config_write``
    The configuration file which pictl is permitted to re-write (also defaults
    to :file:`config.txt`). This is used in cases where the default
    configuration includes several files. In this case, pictl needs to know
    which file it is allowed to re-write, and assume all other files are
    distribution maintained. This is also relative to ``boot_path``.

``reboot_required``
    The file which should be created in the event that the active boot
    configuration is changed.

``backup``
    If this is on (the default), any attempt to change the active boot
    configuration will automatically create a backup of that configuration if
    one does not already exist.

Line comments can be included in the configuration file with a ``#`` prefix.
