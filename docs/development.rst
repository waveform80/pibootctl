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

.. _dev_install:

===========
Development
===========

If you wish to install a copy of pibootctl for development purposes, clone the
git repository and set up a configuration to use the cloned directory as the
source of the boot configuration:

.. code-block:: console

    $ sudo apt install python3-dev git virtualenvwrapper
    $ cd
    $ git clone https://github.com/waveform80/pibootctl.git
    $ mkvirtualenv -p /usr/bin/python3 pibootctl
    $ cd pibootctl
    $ workon pibootctl
    (pibootctl) $ make develop
    (pibootctl) $ cat > ~/.config/pibootctl.conf << EOF
    [defaults]
    boot_path=.
    store_path=store
    reboot_required=
    reboot_required_pkgs=
    EOF

At this point you should be able to call the :doc:`pibootctl <manual>` utility,
and have it store the (empty) boot configuration as a `PKZIP`_ file under the
working directory:

.. code-block:: console

    $ pibootctl save foo
    $ pibootctl ls
    +------+--------+---------------------+
    | Name | Active | Timestamp           |
    |------+--------+---------------------|
    | foo  | x      | 2020-03-08 22:40:28 |
    +------+--------+---------------------+

To work on the clone in future simply enter the directory and use the
:command:`workon` command:

.. code-block:: console

    $ cd ~/pibootctl
    $ workon pibootctl

To pull the latest changes from git into your clone and update your
installation:

.. code-block:: console

    $ cd ~/pibootctl
    $ workon pibootctl
    (pibootctl) $ git pull
    (pibootctl) $ make develop

To remove your installation, destroy the sandbox and the clone:

.. code-block:: console

    (pibootctl) $ cd
    (pibootctl) $ deactivate
    $ rmvirtualenv pibootctl
    $ rm -fr ~/pibootctl


Building the docs
=================

If you wish to build the docs, you'll need a few more dependencies. Inkscape is
used for conversion of SVGs to other formats, Graphviz and Gnuplot are used for
rendering certain charts, and TeX Live is required for building PDF output. The
following command should install all required dependencies:

.. code-block:: console

    $ sudo apt install texlive-latex-recommended texlive-latex-extra \
        texlive-fonts-recommended graphviz gnuplot inkscape

Once these are installed, you can use the "doc" target to build the
documentation:

.. code-block:: console

    $ cd ~/pibootctl
    $ workon pibootctl
    (pibootctl) $ make doc

The HTML output is written to :file:`build/html` while the PDF output goes to
:file:`build/latex`.


Test suite
==========

If you wish to run the test suite, follow the instructions in
:ref:`dev_install` above and then make the "test" target within the sandbox:

.. code-block:: console

    $ cd ~/pibootctl
    $ workon pibootctl
    (pibootctl) $ make test

A `tox`_ configuration is also provided that will test the utility against all
supported Python versions:

.. code-block:: console

    $ cd ~/pibootctl
    $ workon pibootctl
    (pibootctl) $ pip install tox
    ...
    (pibootctl) $ tox -p auto

.. note::

    If developing under Ubuntu, the `Dead Snakes PPA`_ is particularly useful
    for obtaining additional Python installations for testing.

.. _PKZIP: https://en.wikipedia.org/wiki/Zip_(file_format)
.. _tox: https://tox.readthedocs.io/en/latest/
.. _Dead Snakes PPA: https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa
