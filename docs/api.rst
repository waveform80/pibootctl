===
API
===

:doc:`pictl <manual>` can be used both as a standalone application, and as an
API within Python. The primary class of interest when using :doc:`pictl
<manual>` as an API is :class:`pictl.store.Store`, but
:class:`pictl.main.Application` is useful in obtaining the configuration
necessary to construct an instance of the :class:`~pictl.store.Store`.

The API is split into several modules, documented in the following sections:

.. toctree::
    :maxdepth: 1

    api_main
    api_parser
    api_setting
    api_store
