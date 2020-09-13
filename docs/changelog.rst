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

=========
Changelog
=========

.. currentmodule:: pibootctl


Release 0.5.2 (2020-09-14)
==========================

* Fix handling of initramfs (ramfsaddr=0 doesn't work)

Release 0.5.1 (2020-09-09)
==========================

* Handle future model numbers elegantly
* Rewrote the configuration setting code to always target :file:`config.txt`
  as several settings don't work in included files (e.g. ``start_x``).
* Added ``comment_lines`` configuration option to permit commenting out lines
  instead of deleting them
* Enhanced the configuration setting code to search for and uncomment existing
  lines in preference to writing new ones
* Added ``--this-model`` and ``--this-serial`` options to permit adding
  settings in new conditional sections

Release 0.4 (2020-03-31)
========================

* Handle unrecognized commands correctly in the "help" command
* Implemented loading settings with the ``--shell`` style
* Improved help output for reference lists
* Fixed all legal stuff (added copyright headers where required, re-licensed to
  GPL 3+)

Release 0.3 (2020-03-27)
========================

* Added full bash completion support

Release 0.2 (2020-03-26)
========================

* The application now reports which lines overrode a setting when the
  "ineffective setting" error occurs
* Added the max_framebuffers setting, and detection for the vc4-\*-v3d overlays
* Fixed restoring the default configuration in which config.txt doesn't exist
  (i.e. when config.txt should be deleted or blanked; the prior version simply
  left the old config.txt in place incorrectly)
* Various documentation fixes

Release 0.1.1 (2020-03-13)
==========================

* Fixed broken build on Bionic

Release 0.1 (2020-03-13)
========================

* Initial release.

* Please note that as this is a pre-v1 release, API stability is not yet
  guaranteed.
