=============
How-To Guides
=============


The following sections are intended as a walk-through of various typical
operations with :program:`pibootctl`.


Getting Help
============

The :program:`pibootctl` command has several sub-commands. If you ever forget
which sub-commands are available you can simply run pibootctl on its own to
view a summary:

.. code-block:: console

    $ pibootctl
    usage: pibootctl [-h] [--version]
                     {help,?,status,dump,get,set,save,load,diff,show,cat,
                     list,ls,remove,rm,rename,mv} ...

    pibootctl is a tool for querying and modifying the boot configuration of
    the Raspberry Pi.

    optional arguments:
      -h, --help            show this help message and exit
      --version             show program's version number and exit

    commands:
      {help,?,status,dump,get,set,save,load,diff,show,cat,list,ls,remove,rm,rename,mv}
        help (?)            Displays help about the specified command or setting
        status (dump)       Output the current boot time configuration
        get                 Query the state of one or more boot settings
        set                 Change the state of one or more boot settings
        save                Store the current boot configuration for later use
        load                Replace the boot configuration with a saved one
        diff                Show the differences between boot configurations
        show (cat)          Show the specified stored configuration
        list (ls)           List the stored boot configurations
        remove (rm)         Remove a stored boot configuration
        rename (mv)         Rename a stored boot configuration

At the top of the list of commands is :doc:`help`, which will produce the same
output if run with :program:`pibootctl`:

.. code-block:: console

    $ pibootctl help
    usage: pibootctl [-h] [--version]
                     {help,?,status,dump,get,set,save,load,diff,show,cat,list,
                     ls,remove,rm,rename,mv} ...

    pibootctl is a tool for querying and modifying the boot configuration of
    the Raspberry Pi.

    ...

The :doc:`help` command can also be used with other commands to obtain
information on their syntax, including the :doc:`help` command itself:

.. code-block:: console

    $ pibootctl help help
    usage: pibootctl help [-h] [command-or-setting]

    With no arguments, displays the list of pibootctl commands. If a command
    name is given, displays the description and options for the named command.
    If a setting name is given, displays the description and default value for
    that setting.

    positional arguments:
      command-or-setting  The name of the command or setting to output help for

    optional arguments:
      -h, --help          show this help message and exit

Or for the :doc:`list` command, or its alias "ls":

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

You can also obtain help information about individual settings:

.. code-block:: console

    $ pibootctl help boot.splash.enabled
          Name: boot.splash.enabled
       Default: on
    Command(s): disable_splash

    If this is switched off, the rainbow splash screen will not be shown on
    boot.

Finally, if you've installed pibootctl through your system's package manager
(e.g. :manpage:`apt(8)`) then you likely have the man pages available for
each command:

.. code-block:: console

    $ man pibootctl-status


Querying the Boot Settings
==========================

The :doc:`status` command (or its alias "dump") can be used to show the
current set of settings specified by the boot configuration:

.. code-block:: console

    $ pibootctl status
    ┌─────────────────────────┬───────────────────┐
    │ Name                    │ Value             │
    ├─────────────────────────┼───────────────────┤
    │ audio.enabled           │ on                │
    │ boot.initramfs.address  │ -1 (auto)         │
    │ boot.initramfs.filename │ ['initrd.img']    │
    │ boot.kernel.64bit       │ on                │
    │ boot.kernel.cmdline     │ 'cmdline.txt'     │
    │ boot.kernel.filename    │ 'vmlinuz'         │
    │ camera.enabled          │ on                │
    │ gpu.mem                 │ 128 (Mb)          │
    │ i2c.enabled             │ on                │
    │ spi.enabled             │ on                │
    │ video.firmware.mode     │ 'fkms' (Fake KMS) │
    │ video.framebuffer.max   │ 2                 │
    │ video.overscan.enabled  │ off               │
    └─────────────────────────┴───────────────────┘

The structure of the output is quite simple: the name of each setting is in the
left column, and the value of the setting in the right. An optional hint (in
parentheses) may appear after a value to provide some hint as to what the value
means (a scale like MHz or MB, or an explanation of what a particular integer
value actually means).

.. note::

    Do note that this is not necessarily the *effective* configuration. It may
    have been altered since the last boot. This simply reflects what is
    *currently* written in the :file:`config.txt` file on the boot partition.

By default, only those settings which have been modified from their defaults
are shown (if the configuration is entirely default, no settings will be
shown). You can show all settings by adding the :option:`--all
<pibootctl-status --all>` option:

.. code-block:: console

    $ pibootctl dump --all
    ┌──────────────────────────────┬──────────┬────────────────────────────────┐
    │ Name                         │ Modified │ Value                          │
    ├──────────────────────────────┼──────────┼────────────────────────────────┤
    │ audio.depth                  │          │ 11                             │
    │ audio.dither                 │          │ auto                           │
    │ audio.enabled                │ ✓        │ on                             │
    │ bluetooth.enabled            │          │ on                             │
    │ boot.debug.enabled           │          │ off                            │
    │ boot.debug.serial            │          │ off                            │
    │ boot.delay.1                 │          │ 0                              │
    │ boot.delay.2                 │          │ 0                              │
    │ boot.devicetree.address      │          │ 0 (auto)                       │
    │ boot.devicetree.filename     │          │ ''                             │
    │ boot.devicetree.limit        │          │ 0                              │
    │ boot.firmware.filename       │          │ 'start4x.elf'                  │
    │ boot.firmware.fixup          │          │ 'fixup4x.dat'                  │
    │ boot.initramfs.address       │ ✓        │ -1 (auto)                      │
    │ boot.initramfs.filename      │ ✓        │ ['initrd.img']                 │
    │ boot.kernel.64bit            │ ✓        │ on                             │
    │ boot.kernel.address          │          │ 524288 (0x80000)               │
    │ boot.kernel.atags            │          │ on                             │
    │ boot.kernel.cmdline          │ ✓        │ 'cmdline.txt'                  │
    │ boot.kernel.filename         │ ✓        │ 'vmlinuz'                      │
    │ boot.mem                     │          │ 8192 (Mb)                      │
    │ boot.prefix                  │          │ ''                             │
    │ boot.splash.enabled          │          │ on                             │
    │ boot.test.enabled            │          │ off                            │
    │ camera.enabled               │ ✓        │ on                             │
    │ camera.led.enabled           │          │ on                             │
    │ cpu.frequency.max            │          │ 1500 (MHz)                     │
    │ cpu.frequency.min            │          │ 600 (MHz)                      │
    │ cpu.gic.enabled              │          │ on                             │
    │ cpu.l2.enabled               │          │ off                            │
    │ cpu.mem.ctrl.voltage         │          │ 0 (1.2V)                       │
    ...

This output is usually sufficiently long that a pager will be run automatically
to allow you to browse up and down through the results. Also note that this
output includes a column indicating whether a given setting has been modified
from its default.


Saving and Restoring Boot Settings
==================================

You can find the set of boot configurations that are currently stored with the
:doc:`list` command (or its "ls" alias):

.. code-block:: console

    $ pibootctl list
    No stored boot configurations found

In this case we haven't got any stored configurations, so this outputs a simple
message telling us so. We can save the current configuration with the
:doc:`save` command:

.. code-block:: console

    $ sudo pibootctl save default

.. note::

    Note that we use the :program:`sudo` prefix here. The boot configurations
    are typically stored in a location only writeable by root (for reasons
    explained in the next section), hence we need root privileges to write a
    new configuration there.

If we now re-run the :doc:`list` command we can see we have one stored
configuration, which matches the current boot configuration:

.. code-block:: console

    $ pibootctl list
    ┌─────────┬────────┬─────────────────────┐
    │ Name    │ Active │ Timestamp           │
    ├─────────┼────────┼─────────────────────┤
    │ default │ ✓      │ 2021-07-22 16:56:50 │
    └─────────┴────────┴─────────────────────┘

Next we'll make a small modification to the current boot configuration and save
again so we can switch back to the original configuration:

.. code-block:: console

    $ sudo pibootctl set boot.splash.enabled=off
    $ sudo pibootctl save nosplash

If we check the output of :doc:`list` again we can see that "nosplash" is now
the "active" configuration:

.. code-block:: console

    $ pibootctl ls
    ┌──────────┬────────┬─────────────────────┐
    │ Name     │ Active │ Timestamp           │
    ├──────────┼────────┼─────────────────────┤
    │ default  │        │ 2021-07-22 16:56:50 │
    │ nosplash │ ✓      │ 2021-07-23 16:19:54 │
    └──────────┴────────┴─────────────────────┘

Note that "active" doesn't mean this is the configuration you booted with, just
that this is the configuration currently written to the boot partition.

We can now switch back to our "default" configuration with the :doc:`load`
command:

.. code-block:: console

    $ sudo pibootctl load default
    $ pibootctl ls
    ┌──────────┬────────┬─────────────────────┐
    │ Name     │ Active │ Timestamp           │
    ├──────────┼────────┼─────────────────────┤
    │ default  │ ✓      │ 2021-07-22 16:56:50 │
    │ nosplash │        │ 2021-07-23 16:19:54 │
    └──────────┴────────┴─────────────────────┘

.. note::

    Depending upon pibootctl's configuration (specifically the
    :option:`pibootctl reboot-required` option), your system may warn you that
    a reboot is required after loading a new boot configuration.


Restoring an Unbootable System
==============================
