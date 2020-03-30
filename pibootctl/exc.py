# Copyright (c) 2020 Canonical Ltd.
# Copyright (c) 2020 Dave Jones <dave@waveform.org.uk>
#
# This file is part of pibootctl.
#
# pibootctl is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pibootctl is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pibootctl.  If not, see <https://www.gnu.org/licenses/>.

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
