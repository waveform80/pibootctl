.. Copyright (c) 2020 Canonical Ltd.
.. Copyright (c) 2020 Dave Jones <dave@waveform.org.uk>
..
.. This file is part of pibootctl.
..
.. pibootctl is free software: you can redistribute it and/or modify
.. it under the terms of the GNU General Public License as published by
.. the Free Software Foundation, either version 3 of the License, or
.. (at your option) any later version.
..
.. pibootctl is distributed in the hope that it will be useful,
.. but WITHOUT ANY WARRANTY; without even the implied warranty of
.. MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
.. GNU General Public License for more details.
..
.. You should have received a copy of the GNU General Public License
.. along with pibootctl.  If not, see <https://www.gnu.org/licenses/>.

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
    :caption: pibootctl.conf

    [defaults]
    boot_path = /boot
    store_path = pibootctl
    package_name = pibootctl
    comment_lines = on
    backup = on

The configuration specifies several settings, but the most important are:

``boot_path``
    The mount-point of the boot partition (defaults to :file:`/boot`).

``store_path``
    The path under which to store saved boot configurations, relative to
    ``boot_path`` (defaults to :file:`pibootctl`).

``config_root``
    The "root" configuration file which is read first, relative to
    ``boot_path`` (defaults to :file:`config.txt`). This is also the primary
    file that gets re-written when settings are changed.

``mutable_files``
    The set of files within a configuration that may be modified by the
    utility (defaults to :file:`config.txt`). List multiple files on separate
    lines. Currently, this *must* include :file:`config.txt`.

``comment_lines``
    If this is on, when lines in configuration files are no longer required,
    they will be commented out with a "#" prefix instead of being deleted.
    Defaults to off.

    Note that, regardless of this setting, the utility will always search for
    commented lines to uncomment before writing new ones.

``reboot_required``
    The file which should be created in the event that the active boot
    configuration is changed.

``reboot_required_pkgs``
    The file to which the value of ``package_name`` should be appended in the
    event that the active boot configuration is changed.

``package_name``
    The name of the package which contains the utility. Used by
    ``reboot_required_pkgs``.

``backup``
    If this is on (the default), any attempt to change the active boot
    configuration will automatically create a backup of that configuration if
    one does not already exist.

Line comments can be included in the configuration file with a ``#`` prefix.
Another example configuration, typical for Ubuntu on the Raspberry Pi, is shown
below:

.. code-block:: ini
    :caption: pibootctl.conf

    [defaults]
    boot_path = /boot
    store_path = pibootctl
    mutable_files =
      config.txt
      syscfg.txt

    reboot_required = /var/run/reboot-required
    reboot_required_pkgs = /var/run/reboot-required.pkgs
    package_name = pibootctl
    backup = on
