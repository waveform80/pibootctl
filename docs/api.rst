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
