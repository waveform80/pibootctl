.. _dev_install:

===========
Development
===========

If you wish to install a copy of pictl for development purposes, clone the git
repository and set up a configuration to use the cloned directory as the source
of the boot configuration:

.. code-block:: console

    $ sudo apt install python3-dev git virtualenvwrapper
    $ cd
    $ git clone https://github.com/waveform80/pictl.git
    $ mkvirtualenv -p /usr/bin/python3 pictl
    $ cd pictl
    $ workon pictl
    (pictl) $ make develop
    (pictl) $ cat > ~/.config/pictl.conf << EOF
    [defaults]
    boot_path=.
    store_path=store
    reboot_required=
    reboot_required_pkgs=
    EOF

At this point you should be able to call the :doc:`pictl <manual>` utility, and
have it store the (empty) boot configuration as a `PKZIP`_ file under the
working directory:

.. code-block:: console

    $ pictl save foo
    $ pictl ls
    +------+--------+---------------------+
    | Name | Active | Timestamp           |
    |------+--------+---------------------|
    | foo  | x      | 2020-03-08 22:40:28 |
    +------+--------+---------------------+

To work on the clone in future simply enter the directory and use the
:command:`workon` command:

.. code-block:: console

    $ cd ~/pictl
    $ workon pictl

To pull the latest changes from git into your clone and update your
installation:

.. code-block:: console

    $ cd ~/pictl
    $ workon pictl
    (pictl) $ git pull
    (pictl) $ make develop

To remove your installation, destroy the sandbox and the clone:

.. code-block:: console

    (pictl) $ cd
    (pictl) $ deactivate
    $ rmvirtualenv pictl
    $ rm -fr ~/pictl


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

    $ cd ~/pictl
    $ workon pictl
    (pictl) $ make doc

The HTML output is written to :file:`build/html` while the PDF output goes to
:file:`build/latex`.


Test suite
==========

If you wish to run the test suite, follow the instructions in
:ref:`dev_install` above and then make the "test" target within the sandbox:

.. code-block:: console

    $ cd ~/pictl
    $ workon pictl
    (pictl) $ make test

A `tox`_ configuration is also provided that will test the utility against all
supported Python versions:

.. code-block:: console

    $ cd ~/pictl
    $ workon pictl
    (pictl) $ pip install tox
    ...
    (pictl) $ tox -p auto

.. note::

    If developing under Ubuntu, the `Dead Snakes PPA`_ is particularly useful
    for obtaining additional Python installations for testing.

.. _PKZIP: https://en.wikipedia.org/wiki/Zip_(file_format)
.. _tox: https://tox.readthedocs.io/en/latest/
.. _Dead Snakes PPA: https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa
