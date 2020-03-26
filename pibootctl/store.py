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
from collections.abc import Mapping
from zipfile import ZipFile, BadZipFile, ZIP_DEFLATED

from .files import AtomicReplaceFile
from .parser import BootParser, BootFile
from .setting import CommandIncludedFile
from .settings import SETTINGS
from .exc import (
    InvalidConfiguration,
    IneffectiveConfiguration,
    MissingInclude,
)

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

    :param str config_read:
        The filename of the "root" of the configuration, i.e. the first file
        read by the parser. Currently, this should always be "config.txt", the
        default.

    :param str config_write:
        The filename of the configuration file which should be re-written by
        mutable configurations. By default this is "config.txt" but
        distributions may wish to include another file from "config.txt",
        leaving "config.txt" to be managed by the distribution itself.

    :param str config_template:
        The template to use when re-writing *config_write*. By default this
        is just "{config}", but this parameter can be used to add headers or
        footers to the generated configuration (or for that matter, additional
        fixed includes, or even configuration lines).
    """
    def __init__(self, boot_path, store_path, config_read='config.txt',
                 config_write='config.txt', config_template='{config}'):
        self._boot_path = Path(boot_path)
        self._store_path = self._boot_path / store_path
        self._config_read = config_read
        self._config_write = config_write
        self._config_template = config_template

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
                self._boot_path, self._config_read, self._config_write,
                self._config_template)
        elif key in self:
            return StoredConfiguration(
                self._path_of(key), self._config_read, self._config_write,
                self._config_template)
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
                if path != self._config_read:
                    replace_file(path, file)
            # config.txt is deliberately dealt with last. This ensures that,
            # in the case of systems using os_prefix to switch boot directories
            # the switch is effectively atomic
            try:
                path = self._config_read
                file = item.files[self._config_read]
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
        The SHA1 hash that identifies the boot configuration. This is obtained
        by hashing the files of the boot configuration in parsing order.
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
    Represents the current boot configuration, as parsed from *filename*
    (default "config.txt") on the boot partition (presumably mounted at
    *path*, a :class:`~pathlib.Path` instance).

    The file named by *rewrite* (default "config.txt") is the file within the
    configuration that should be considered mutable, i.e. this is the file that
    gets re-written within a :meth:`mutable` configuration.

    Finally, the *template* string specifies the template used to format the
    *rewrite* file. By default this is simple "{config}" indicating that the
    generated configuration alone should be placed in the file, but headers
    and footers (or even additional includes) can be added by means of this
    parameter.
    """
    def __init__(self, path, filename='config.txt', rewrite='config.txt',
                 template='{config}'):
        self._path = path
        self._filename = filename
        self._settings = None
        self._files = None
        self._hash = None
        self._timestamp = None
        self._rewrite = rewrite
        self._template = template

    def _parse(self):
        assert self._settings is None
        parser = BootParser(self._path)
        parser.parse(self._filename)
        self._settings = Settings()
        for setting in self._settings.values():
            lines = []
            for item, value in setting.extract(parser.config):
                setting._value = value
                lines.append(item)
            setting._lines = tuple(lines[::-1])
        for setting in self._settings.values():
            if isinstance(setting, CommandIncludedFile):
                parser.add(setting.filename)
        self._files = parser.files
        self._hash = parser.hash
        self._timestamp = parser.timestamp

    @property
    def path(self):
        """
        The path (or archive or entity) containing all the files that make up
        the boot configuration.
        """
        return self._path

    @property
    def filename(self):
        """
        The root file of the boot configuration. This is currently always
        "config.txt".
        """
        return self._filename

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
        return MutableConfiguration(self.files.copy(), self._filename,
                                    self._rewrite, self._template)


class StoredConfiguration(BootConfiguration):
    """
    Represents a boot configuration stored in a :class:`~zipfile.ZipFile`
    specified by *path*. The starting file of the configuration is given by
    *filename*. All other parameters are as in :class:`BootConfiguration`.
    """
    def __init__(self, path, filename='config.txt', rewrite='config.txt',
                 template='{config}'):
        super().__init__(ZipFile(str(path), 'r'), filename, rewrite, template)
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

    Only one file in the configuration, specified by *rewrite*, is permitted to
    be re-written and its contents are (partially) dictated by the specified
    *template*.

    Mutable configurations can be changed with the :meth:`update` method which
    will also validate the new configuration, and check that the settings were
    not overridden by later files. No link is maintained between the original
    :class:`BootConfiguration` and the mutable copy. This implies that nothing
    is re-written on disk when the mutable configuration is updated. The
    resulting configuration must be assigned back to something in the
    :class:`Store` in order to re-write disk files.
    """
    def update(self, values):
        """
        Given a mapping of setting names to new values, updates the values of
        the corresponding settings in this configuration. If a value is
        :data:`None`, the setting is reset to its default value.
        """
        for name, value in values.items():
            item = self.settings[name]
            item._value = item.update(value)
            item._lines = ()

        # Validate the new configuration; aggregate all exceptions for the
        # user's convenience
        errors = {}
        for item in self.settings.values():
            try:
                item.validate()
            except ValueError as exc:
                errors[item.name] = exc
        if errors:
            raise InvalidConfiguration(errors)

        # Regenerate the dict forming our "path". First, blank out the file we
        # intend to re-write and re-parse the settings to see what they are
        # without that file
        updated = self.settings.copy()
        self._path.pop(self._rewrite, None)
        self._settings = self._files = self._hash = None
        self._parse()

        # Diff the re-parsed settings with the updated copy to figure out
        # which settings actually need writing, and re-construct the _rewrite
        # file from these
        content = []
        # XXX Can new ever be None? Would that be an error?
        for old, new in sorted(self.settings.diff(updated),
                               key=lambda i: i[1].key):
            content.extend(new.output())
        content = self._template.format(config='\n'.join(content))
        self._path[self._rewrite] = BootFile(
            self._rewrite, datetime.now(),
            content.encode('ascii'),
            'ascii', 'replace')
        self._settings = self._files = self._hash = None
        self._parse()

        # Check whether any settings were overridden by files later than the
        # _rewrite file
        if self._rewrite not in self.files:
            raise MissingInclude(self._rewrite)
        diff = updated.diff(self.settings)
        if diff:
            raise IneffectiveConfiguration(diff)


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
        # This curious ordering is necessary to ensure the sorting order of
        # _items is preserved
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
