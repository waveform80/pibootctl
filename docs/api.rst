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

===
API
===

:doc:`pibootctl <manual>` can be used both as a standalone application, and as
an API within Python. The primary class of interest when using :doc:`pibootctl
<manual>` as an API is :class:`pibootctl.store.Store`, but
:class:`pibootctl.main.Application` is useful for constructing an instance of
the :class:`~pibootctl.store.Store` using the stored configuration.

The API is split into several modules, documented in the following sections:

.. toctree::
    :maxdepth: 1

    api_exc
    api_files
    api_formatter
    api_info
    api_main
    api_parser
    api_setting
    api_settings
    api_store
    api_term
    api_userstr
