=========
pibootctl
=========

pibootctl is a utility for querying and manipulating the boot configuration of
a `Raspberry Pi`_. It is a relatively low level utility, and not intended to be
as friendly (or as widely applicable) as ``raspi-config``. It provides a
command line interface only, but does attempt to be useful as a basis for more
advanced interfaces (by providing input and output in human-readable,
shell-interpretable, JSON, or YAML formats) as well as being useful in its own
right.

The design philosophy of the utility is as follows:

#. Be safe: the utility manipulates the boot configuration and it's entirely
   possible to create a non-booting system as a result. To that end, if no
   backup of the current boot configuration exists, always take one before
   manipulating it.

#. Be accessible: the Pi's boot configuration lives on a FAT partition and is a
   simple ASCII text file. This means it can be read and manipulated by almost
   any platform (Windows, Mac OS, etc). Any backups of the configuration should
   be as accessible. To that end we use simple PKZIP files to store backups of
   boot configurations (in their original format), and place them on the same
   FAT partition as the configuration.

#. Be extensible: Almost all commands should default to human readable input
   and output, but options should be provided for I/O in JSON, YAML, and a
   shell-parseable format.

Links
=====

* The code is licensed under the `GPL v3`_ or above
* The `source code`_ can be obtained from GitHub, which also hosts the
  `bug tracker`_
* The `documentation`_ (which includes installation and quick start examples)
  can be read on ReadTheDocs
* Packages can be `downloaded`_ from PyPI, although reading the installation
  instructions will probably be more useful

.. _Raspberry Pi: https://raspberrypi.org/
.. _GPL v3: https://www.gnu.org/licenses/gpl-3.0.html
.. _source code: https://github.com/waveform80/pibootctl
.. _bug tracker: https://github.com/waveform80/pibootctl/issues
.. _documentation: https://pibootctl.readthedocs.io/
.. _downloaded: https://pypi.org/project/pibootctl
