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
The :mod:`pibootctl.store` module defines classes which control a store of
Raspberry Pi boot configurations, or the active boot configuration.

The main class of interest is :class:`Store`. From an instance of this, one can
access derivatives of :class:`BootConfiguration` for the purposes of
manipulating the store of configurations, or the active boot configuration
itself. Each :class:`BootConfiguration` contains an instance of
:class:`Settings` which maps setting names to
:class:`~pibootctl.setting.Setting` instances.

See :class:`pibootctl.main` for information on obtaining an instance of
:class:`Store`.

.. data:: Current

    The key of the active boot configuration in instances of :class:`Store`.

.. data:: Default

    The key of the default (empty) boot configuration in instances of
    :class:`Store`.

.. autoclass:: Store
    :members:

.. autoclass:: BootConfiguration
    :members:

.. autoclass:: StoredConfiguration
    :members:

.. autoclass:: MutableConfiguration
    :members:

.. autoclass:: Settings
    :members:
"""

import os
import gettext
from weakref import ref
from pathlib import Path
from copy import deepcopy
from fnmatch import fnmatch
from datetime import datetime
from operator import itemgetter
from collections.abc import Mapping
from zipfile import ZipFile, BadZipFile, ZIP_DEFLATED

from .files import AtomicReplaceFile
from .parser import BootParser, BootFile, BootComment, BootConditions
from .setting import CommandIncludedFile
from .settings import SETTINGS
from .exc import InvalidConfiguration, IneffectiveConfiguration, DelegatedOutput

_ = gettext.gettext


class Current:
    "Singleton representing the active boot configuration in :class:`Store`."
    def __repr__(self):
        return 'Current'
Current = Current()


class Default:
    "Singleton representing the default boot configuration in :class:`Store`."
    def __repr__(self):
        return 'Default'
Default = Default()


class Store(Mapping):
    """
    A mapping representing all boot configurations (current, default, and
    stored).

    Acts as a mapping keyed by the name of the stored configuration, or the
    special values :data:`Current` for the current boot configuration, or
    :data:`Default` for the default (empty) configuration. The values of the
    mapping are derivatives of :class:`BootConfiguration` which provide the
    parsed :class:`Settings`, along with some other attributes.

    The mapping is mutable and this can be used to manipulate stored boot
    configurations. For instance, to store the current boot configuration under
    the name "foo"::

        >>> store = Store('/boot', 'pibootctl')
        >>> store["foo"] = store[Current]

    Setting the item with the key :data:`Current` overwrites the current boot
    configuration::

        >>> store[Current] = store["serial"]

    Note that items retrieved from the store are effectively immutable;
    modifying them (even internally) does *not* modify the content of the
    store. To modify the content of the store, you must request a
    :meth:`~BootConfiguration.mutable` copy of a configuration, modify it, and
    assign it back::

        >>> foo = store["foo"].mutable()
        >>> foo.update({"serial.enabled": True})
        >>> store["serial"] = foo

    The same applies to the current boot configuration item::

        >>> current = store[Current].mutable()
        >>> current.update({"camera.enabled": True, "gpu.mem": 128})
        >>> store[Current] = current

    Items can be deleted to remove them from the store, with the obvious
    exception of the items with the keys :data:`Current` and :data:`Default`
    which cannot be removed (attempting to do so will raise a :exc:`KeyError`).
    Furthermore, the item with the key :data:`Default` cannot be modified
    either.

    :param str boot_path:
        The path on which the boot partition is mounted.

    :param str store_path:
        The path (relative to *boot_path*) under which stored configurations
        will be saved.

    :param str config_root:
        The filename of the "root" of the configuration, i.e. the first file
        read by the parser, and the file in which certain commands (e.g.
        start_x) *must* be placed. Currently, this should always be
        "config.txt", the default.

    :param set mutable_files:
        The set of filenames which :class:`MutableConfiguration` instances are
        permitted to change. By default this is just "config.txt".

    :param bool comment_lines:
        If :data:`True`, then :class:`MutableConfiguration` will comment out
        lines no longer required with a # prefix. When :data:`False` (the
        default), such lines will be deleted instead. When adding lines,
        regardless of this setting, the utility will search for, and uncomment,
        commented out lines which match the required output.
    """
    def __init__(self, boot_path, store_path, config_root='config.txt',
                 mutable_files=frozenset({'config.txt'}), comment_lines=False):
        self._boot_path = Path(boot_path)
        self._store_path = self._boot_path / store_path
        self._config_root = config_root
        self._mutable_files = frozenset(mutable_files)
        self._comment_lines = comment_lines

    def _path_of(self, name):
        return (self._store_path / name).with_suffix('.zip')

    def _enumerate(self):
        for path in self._store_path.glob('*.zip'):
            with ZipFile(str(path), 'r') as arc:
                if arc.comment.startswith(b'pibootctl:0:'):
                    yield path.stem

    def __len__(self):
        # +2 for the current and default configs
        return sum(1 for i in self._enumerate()) + 2

    def __iter__(self):
        yield Default
        yield Current
        yield from self._enumerate()

    def __contains__(self, key):
        if key in (Current, Default):
            # The current and boot configurations are always present (even if
            # config.txt doesn't exist, there's still technically a boot
            # configuration - just a default one)
            return True
        else:
            try:
                with ZipFile(str(self._path_of(key)), 'r') as arc:
                    return arc.comment.startswith(b'pibootctl:0:')
            except (FileNotFoundError, BadZipFile):
                return False

    def __getitem__(self, key):
        if key is Default:
            return DefaultConfiguration()
        elif key is Current:
            return BootConfiguration(
                self._boot_path, self._config_root, self._mutable_files,
                self._comment_lines)
        elif key in self:
            return StoredConfiguration(
                self._path_of(key), self._config_root, self._mutable_files,
                self._comment_lines)
        else:
            raise KeyError(_(
                "No stored configuration named {key}").format(key=key))

    def __setitem__(self, key, item):
        if key is Default:
            raise KeyError(_(
                "Cannot change the default configuration"))
        elif key is Current:
            def replace_file(path, file):
                with AtomicReplaceFile(self._boot_path / path) as temp:
                    temp.write(file.content)
                os.utime(str(self._boot_path / path), (
                    datetime.now().timestamp(), file.timestamp.timestamp()))

            old_files = set(self[Current].files.keys())
            for path, file in item.files.items():
                if path != self._config_root:
                    replace_file(path, file)
            # config.txt is deliberately dealt with last. This ensures that,
            # in the case of systems using os_prefix to switch boot directories
            # the switch is effectively atomic
            try:
                path = self._config_root
                file = item.files[self._config_root]
            except KeyError:
                pass
            else:
                replace_file(path, file)
            # Remove files that existed in the old configuration but not the
            # new; this is necessary to deal with the case of switching from
            # a config with config.txt (or other includes) to one without
            # (which is a valid, default configuration). Again, for systems
            # using os_prefix to switch boot dirs, this must occur last
            for path in old_files:
                if not path in item.files:
                    os.unlink(str(self._boot_path / path))
        elif isinstance(key, str) and key:
            self._store_path.mkdir(parents=True, exist_ok=True)
            with ZipFile(str(self._path_of(key)), 'x',
                         compression=ZIP_DEFLATED) as arc:
                arc.comment = 'pibootctl:0:{hash}\n\n{warning}'.format(
                    hash=item.hash, warning=_(
                        'Do not edit the content of this archive; the line '
                        'above is a hash of the content which will not match '
                        'after manual editing. Please use the pibootctl tool '
                        'to manipulate stored boot configurations'),
                ).encode('ascii')
                for file in item.files.values():
                    file.add_to_zip(arc)
        else:
            raise KeyError(_(
                '{key!r} is an invalid stored configuration').format(key=key))

    def __delitem__(self, key):
        if key is Default:
            raise KeyError(_("Cannot remove the default configuration"))
        elif key is Current:
            raise KeyError(_("Cannot remove the current boot configuration"))
        else:
            try:
                self._path_of(key).unlink()
            except FileNotFoundError:
                raise KeyError(_(
                    "No stored configuration named {key}").format(key=key))

    @property
    def active(self):
        """
        Returns the key of the active configuration, if any. If no
        configuration is currently active, returns :data:`None`.
        """
        current = self[Current]
        for key in self:
            if key not in (Current, Default):
                stored = self[key]
                if stored.hash == current.hash:
                    return key
        return None


class DefaultConfiguration:
    """
    Represents the default boot configuration with an entirely empty file-set
    and a fresh :class:`Settings` instance.
    """
    @property
    def files(self):
        """
        A mapping of filenames to :class:`~pibootctl.parser.BootFile` instances
        representing all the files that make up the boot configuration.
        """
        return {}

    @property
    def hash(self):
        """
        The `SHA-1`_ hash that identifies the boot configuration. This is
        obtained by hashing the files of the boot configuration in parsing
        order.

        .. _SHA-1: https://en.wikipedia.org/wiki/SHA-1
        """
        return 'da39a3ee5e6b4b0d3255bfef95601890afd80709'  # empty sha1

    @property
    def timestamp(self):
        """
        The last modified timestamp of the boot configuration, as a
        :class:`~datetime.datetime`.
        """
        return datetime(1970, 1, 1)  # UNIX epoch

    @property
    def settings(self):
        """
        A :class:`Settings` instance containing all the settings extracted from
        the boot configuration.
        """
        return Settings()


class BootConfiguration:
    """
    Represents a boot configuration, as parsed from *config_root* (default
    "config.txt") on the boot partition (presumably mounted at *path*, a
    :class:`~pathlib.Path` instance).
    """
    def __init__(self, path, config_root='config.txt',
                 mutable_files=frozenset({'config.txt'}), comment_lines=False):
        self._path = path
        self._config_root = config_root
        self._mutable_files = mutable_files
        self._comment_lines = comment_lines
        self._settings = None
        self._files = None
        self._hash = None
        self._timestamp = None

    def _parse(self):
        parser = BootParser(self._path)
        parser.parse(self._config_root)
        self._settings = Settings()
        for setting in self._settings.values():
            lines = []
            for item, value in setting.extract(parser.config):
                if item.conditions.enabled:
                    setting._value = value
                lines.append(item)
            setting._lines = tuple(lines[::-1])
        for setting in self._settings.values():
            if isinstance(setting, CommandIncludedFile):
                parser.add(setting.filename)
        self._files = parser.files
        self._hash = parser.hash
        self._timestamp = parser.timestamp
        return parser

    @property
    def path(self):
        """
        The path (or archive or entity) containing all the files that make up
        the boot configuration.
        """
        return self._path

    @property
    def config_root(self):
        """
        The root file of the boot configuration. This is currently always
        "config.txt".
        """
        return self._config_root

    @property
    def timestamp(self):
        """
        The last modified timestamp of the boot configuration, as a
        :class:`~datetime.datetime`.
        """
        if self._timestamp is None:
            self._parse()
        return self._timestamp

    @property
    def hash(self):
        """
        The SHA1 hash that identifies the boot configuration. This is obtained
        by hashing the files of the boot configuration in parsing order.
        """
        if self._hash is None:
            self._parse()
        return self._hash

    @property
    def settings(self):
        """
        A :class:`Settings` instance containing all the settings extracted from
        the boot configuration.
        """
        if self._settings is None:
            self._parse()
        return self._settings

    @property
    def files(self):
        """
        A mapping of filenames to :class:`~pibootctl.parser.BootFile` instances
        representing all the files that make up the boot configuration.
        """
        if self._files is None:
            self._parse()
        return self._files

    def mutable(self):
        """
        Return a :class:`MutableConfiguration` based on the parsed content of
        this configuration.

        Note that mutable configurations are not backed by any files on disk,
        so nothing is actually re-written until the updated mutable
        configuration is assigned back to something in the :class:`Store`.
        """
        return MutableConfiguration(self.files.copy(), self._config_root,
                                    self._mutable_files, self._comment_lines)


class StoredConfiguration(BootConfiguration):
    """
    Represents a boot configuration stored in a :class:`~zipfile.ZipFile`
    specified by *path*. The starting file of the configuration is given by
    *config_root*. All other parameters are as in :class:`BootConfiguration`.
    """
    def __init__(self, path, config_root='config.txt',
                 mutable_files=frozenset({'config.txt'}), comment_lines=False):
        super().__init__(
            ZipFile(str(path), 'r'), config_root, mutable_files, comment_lines)
        # We can grab the hash and timestamp from the arc's meta-data without
        # any decompression work (it's all in the uncompressed footer)
        comment = self.path.comment
        if comment.startswith(b'pibootctl:0:'):
            i = len('pibootctl:0:')
            zip_hash = comment[i:40 + i].decode('ascii')
            if len(zip_hash) != 40:
                raise ValueError(_(
                    'Invalid stored configuration: invalid length'))
            if not set(zip_hash) <= set('0123456789abcdef'):
                raise ValueError(_(
                    'Invalid stored configuration: non-hex hash'))
            self._hash = zip_hash
            # A stored archive can be empty, hence default= is required
            self._timestamp = max(
                (datetime(*info.date_time) for info in self.path.infolist()),
                default=datetime(1970, 1, 1))
        else:
            # TODO Should we allow "self-made" archives without a pibootctl
            # header comment? We can't currently reach here because the
            # enumerate and contains tests check for pibootctl:0: but that
            # could be relaxed...
            assert False, 'Invalid stored configuration: missing hash'


class MutableConfiguration(BootConfiguration):
    """
    Represents a changeable boot configuration.

    Do not construct instances of this class directly; they are typically
    constructed from a *base* :class:`BootConfiguration`, by calling
    :meth:`~BootConfiguration.mutable`.

    Mutable configurations can be changed with the :meth:`update` method which
    will also validate the new configuration, and check that the settings were
    not overridden by later files. No link is maintained between the original
    :class:`BootConfiguration` and the mutable copy. This implies that nothing
    is re-written on disk when the mutable configuration is updated. The
    resulting configuration must be assigned back to something in the
    :class:`Store` in order to re-write disk files.
    """
    def update(self, values, context):
        """
        Given a mapping of setting names to new values, updates the values of
        the corresponding settings in this configuration. If a value is
        :data:`None`, the setting is reset to its default value.
        """
        # Generate the "desired" settings. Note that this is a "pure" copy of
        # the settings without any actual configuration files backing it. We'll
        # use this firstly to validate the new settings are coherent, and later
        # to determine whether the configuration we generate matches the
        # desired settings.
        updated = self.settings.copy()
        for name, value in values.items():
            item = updated[name]
            item._value = item.update(value)
            item._lines = ()
        errors = {}
        for item in updated.values():
            try:
                item.validate()
            except ValueError as exc:
                errors[item.name] = exc
        if errors:
            raise InvalidConfiguration(errors)

        # Generate a clean configuration devoid of all the lines that affected
        # "values", then build a final configuration from the desired settings
        # we generated above, and validate it results in the desired settings
        self._update_path(self._clean_config(values, context))
        self._parse()
        self._update_path(self._final_config(updated, context))
        self._parse()
        diff = updated.diff(self.settings)
        if diff:
            raise IneffectiveConfiguration(diff)

    def _parse(self):
        # Save the parsed lines of the boot configuration; the final phase of
        # the update method (_final_config) requires this information
        parser = super()._parse()
        self._config = parser.config

    def _update_path(self, new_path):
        # Update self._path from *new_path*, a dict mapping filenames to
        # lists of lines.
        for filename, lines in new_path.items():
            try:
                old_file = self._path[filename]
            except KeyError:
                old_file = BootFile.empty(
                    filename, encoding='ascii', errors='replace')
            new_content = ''.join(lines).encode(
                old_file.encoding, old_file.errors)
            self._path[filename] = BootFile(
                filename, datetime.now(), new_content,
                old_file.encoding, old_file.errors)

    def _clean_config(self, values, context):
        # Generate a "clean" configuration in which all lines which affected
        # (or would potentially affect, under *context*) the settings mentioned
        # in *values* are disabled or deleted
        files = {
            line.filename
            for name in values
            for line in self.settings[name].lines
        }
        new_path = {
            filename: list(self._path[filename].lines())
            for filename in files
        }
        for name in values:
            for line in self.settings[name].lines:
                if (
                        line.filename in self._mutable_files and
                        line.conditions <= context):
                    new_file = new_path[line.filename]
                    if self._comment_lines:
                        if not new_file[line.linenum - 1].startswith('#'):
                            new_file[line.linenum - 1] = (
                                '#' + new_file[line.linenum - 1])
                    else:
                        new_file[line.linenum - 1] = ''
        return new_path

    def _final_config(self, updated, context):
        # Diff the new settings to figure out which settings actually need
        # writing, and generate content from changed settings. Here we handle
        # the case of settings delegating their output to other settings and
        # track which ones have been done to avoid duplication
        done = set()
        new_lines = {}
        # XXX Can new ever be None? Would that be an error?
        for old, new in self.settings.diff(updated):
            if new.name in done:
                continue
            setting = new
            while True:
                try:
                    done.add(setting.name)
                    new_lines[setting.key] = list(setting.output())
                except DelegatedOutput as exc:
                    setting = updated[exc.master]
                else:
                    break

        # Search for comments that can be "uncommented" instead of writing new
        # lines, and otherwise record which new lines are required
        new_path = {}
        new_config = []
        for key, lines in sorted(new_lines.items(), key=itemgetter(0)):
            for new_line in lines:
                for old_line in self._config:
                    # XXX This isn't *entirely* safe when dealing with
                    # dt-params, because anything we uncomment is potentially
                    # out of key order in the final output
                    if (
                            isinstance(old_line, BootComment) and
                            old_line.conditions == context and
                            old_line.comment == new_line):
                        try:
                            new_file = new_path[old_line.filename]
                        except KeyError:
                            new_file = new_path[old_line.filename] = (
                                list(self._path[old_line.filename].lines()))
                        new_file[old_line.linenum - 1] = old_line.comment + '\n'
                        break
                else:
                    new_config.append(new_line)

        # Find the insertion-point for new_config; ideally, this is the last
        # line of any section in the root configuration file which matches our
        # desired context. Failing that, it'll be the last line of the root
        # configuration file
        insert_at = None
        for line in reversed(self._config):
            if line.filename == self.config_root:
                if insert_at is None:
                    # Set a tentative insertion-point at the last line in the
                    # root configuration file
                    insert_at = line
                if line.conditions == context:
                    # If we find a line which has conditions matching our
                    # required context, we're done
                    insert_at = line
                    break
        if insert_at is None:
            # This can only happen if there's no root configuration file so
            # we need to generate one with the appropriate context
            insert_at = BootComment(self.config_root, 0, BootConditions())

        # Insert the new content, prefixed with any necessary
        # sections to adjust the context of the insertion point (ip)
        if insert_at.conditions != context:
            # Two cases are relevant here: the above case where no root
            # configuration file exists, and the case where no lines in the
            # existing configuration match the desired context
            new_config.insert(0, '')
            new_config[1:1] = list(context.generate(insert_at.conditions))
        try:
            new_file = new_path[self.config_root]
        except KeyError:
            try:
                new_file = new_path[self.config_root] = (
                    list(self._path[self.config_root].lines()))
            except KeyError:
                new_file = new_path[self.config_root] = []
        new_config = [line + '\n' for line in new_config]
        new_file[insert_at.linenum:insert_at.linenum] = new_config

        # TODO Add an (optional?) phase to prune (/comment?) empty sections?
        # TODO Add an (optional?) phase to ensure [all] is always last?
        return new_path


class Settings(Mapping):
    """
    Represents all settings in a boot configuration; acts like an ordered
    mapping of names to :class:`~pibootctl.setting.Setting` objects.
    """
    def __init__(self, items=None):
        if items is None:
            items = SETTINGS
        self._items = deepcopy(items)
        for setting in self._items.values():
            setting._settings = ref(self)
        self._visible = set(self._items.keys())

    def __len__(self):
        return len(self._visible)

    def __iter__(self):
        for key in self._items:
            if key in self._visible:
                yield key

    def __contains__(self, key):
        return key in self._visible

    def __getitem__(self, key):
        if key not in self._visible:
            raise KeyError(key)
        return self._items[key]

    def copy(self):
        """
        Returns a distinct copy of the configuration that can be updated
        without affecting the original.
        """
        new = deepcopy(self)
        for setting in new._items.values():
            setting._settings = ref(new)
        return new

    def modified(self):
        """
        Returns a copy of the configuration which only contains modified
        settings.
        """
        # When filtering we mustn't actually remove any members of _items as
        # Setting instances may need to refer to a "hidden" value to, for
        # example, determine their default value
        new_visible = {
            name for name in self._visible
            if self[name].modified
        }
        copy = self.copy()
        copy._visible = new_visible
        return copy

    def filter(self, pattern):
        """
        Returns a copy of the configuration which only contains settings with
        names matching *pattern*, which may contain regular shell globbing
        patterns.
        """
        new_visible = {
            name for name in self._visible
            if fnmatch(name, pattern)
        }
        copy = self.copy()
        copy._visible = new_visible
        return copy

    def diff(self, other):
        """
        Returns a set of (self, other) setting tuples for all settings that
        differ between *self* and *other* (another :class:`Settings` instance).
        If a particular setting is missing from either side, its entry will be
        given as :data:`None`.
        """
        return {
            (setting, other[setting.name] if setting.name in other else None)
            for setting in self.values()
            if setting.name not in other or
            other[setting.name].value != setting.value
        } | {
            (None, other[name])
            for name in other
            if name not in self
        }
