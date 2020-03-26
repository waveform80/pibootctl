"""
The :mod:`pibootctl.exc` module defines the various exceptions used in the
application:

.. autoexception:: InvalidConfiguration

.. autoexception:: IneffectiveConfiguration

.. autoexception:: MissingInclude
"""

import gettext

_ = gettext.gettext


class InvalidConfiguration(ValueError):
    """
    Error raised when an updated configuration fails to validate. All
    :exc:`ValueError` exceptions raised during validation are available from
    the :attr:`errors` attribute which maps setting names to the
    :exc:`ValueError` raised.
    """
    def __init__(self, errors):
        self.errors = errors
        super().__init__(str(self))

    def __str__(self):
        return _(
            "Configuration failed to validate with {count} error(s)").format(
                count=len(self.errors))


class IneffectiveConfiguration(ValueError):
    """
    Error raised when an updated configuration has been overridden by something
    in a file we're not allowed to edit. All settings which have been
    overridden are available from the :attr:`diff` attribute.
    """
    def __init__(self, diff):
        self.diff = diff
        super().__init__(str(self))

    def __str__(self):
        return _("Failed to set {count} setting(s)").format(
            count=len(self.diff))


class MissingInclude(ValueError):
    """
    Error raised when the file that's re-written by pibootctl isn't included in
    the configuration.
    """
    def __init__(self, rewrite):
        self.rewrite = rewrite
        super().__init__(str(self))

    def __str__(self):
        return _(
            "{rewrite} was not included in the new configuration").format(
                rewrite=self.rewrite)
