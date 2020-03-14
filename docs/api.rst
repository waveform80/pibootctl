===
API
===

:doc:`pibootctl <manual>` can be used both as a standalone application, and as
an API within Python. The primary class of interest when using :doc:`pibootctl
<manual>` as an API is :class:`pibootctl.store.Store`, but
:class:`pibootctl.main.Application` is useful in obtaining the configuration
necessary to construct an instance of the :class:`~pibootctl.store.Store`.

The API is split into several modules, documented in the following sections:

.. toctree::
    :maxdepth: 1

    api_main
    api_parser
    api_setting
    api_store
    api_userstr
