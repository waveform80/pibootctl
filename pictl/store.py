import gettext
import tempfile
from weakref import ref
from pathlib import Path
from copy import deepcopy
from textwrap import dedent
from fnmatch import fnmatch
from datetime import datetime
from collections import OrderedDict
from collections.abc import Mapping
from zipfile import ZipFile, BadZipFile, ZIP_DEFLATED

from .parser import BootParser
from .files import AtomicReplaceFile
from .setting import CommandIncludedFile
from .settings import SETTINGS

_ = gettext.gettext


Current = object()
Default = object()


class Store(Mapping):
    """
    A mapping representing all boot configurations (current, default, and
    stored).

    Acts as a mapping keyed by the name of the stored configuration, or the
    special values :data:`Current` for the current boot configuration, or
    :data:`Default` for the default (empty) configuration. The values of the
    mapping are objects which provide the parsed :class:`Settings`, an
    identifying :attr:`~StoredSettings.hash`, and a dictionary mapping
    filenames to contents.

    The mapping is mutable and this can be used to manipulate stored boot
    configurations. For instance, to store the current boot configuration under
    the name "foo"::

        >>> store = Store(config)
        >>> store["foo"] = store[Current]

    Setting the item with the key :data:`Current` overwrites the current boot
    configuration::

        >>> store[Current] = store["serial"]

    Note that items retrieved from the store are ephemeral and modifying them
    does *not* modify the content of the store. To modify the content of the
    store, an item must be explicitly set::

        >>> foo = store["foo"]
        >>> foo.settings.update({"serial.enabled": True})
        >>> store["serial"] = foo

    The same applies to the current boot configuration item::

        >>> current = store[Current]
        >>> current.settings.update({"camera.enabled": True, "gpu.mem": 128})
        >>> store[Current] = current

    Items can be deleted to remove them from the store, with the obvious
    exception of the items with the keys :data:`Current` and :data:`Default`
    which cannot be removed. Furthermore, the item with the key :data:`Default`
    cannot be modified either.
    """
    def __init__(self, config):
        self._store_path = Path(config.store_path)
        self._boot_path = Path(config.boot_path)
        self._config_read = config.config_read
        self._config_write = config.config_write

    def _path_of(self, name):
        return (self._store_path / name).with_suffix('.zip')

    def _enumerate(self):
        for p in self._store_path.glob('*.zip'):
            with ZipFile(str(p), 'r') as arc:
                if arc.comment.startswith(b'pictl:0:'):
                    yield p.stem

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
                    if arc.comment.startswith(b'pictl:0:'):
                        return True
            except (FileNotFoundError, BadZipFile):
                return False

    def __getitem__(self, key):
        if key is Default:
            return DefaultConfiguration()
        elif key is Current:
            return BootConfiguration(self._boot_path, self._config_read)
        elif key in self:
            return StoredConfiguration(self._path_of(key), self._config_read)
        else:
            raise KeyError(_(
                "No stored configuration named {key}").format(key=key))

    def __setitem__(self, key, item):
        if key is Default:
            raise KeyError(_(
                "Cannot change the default configuration"))
        elif key is Current:
            # TODO Sort content so config.txt is written last; this will allow
            # effectively atomic switches of configuration for systems using
            # os_prefix
            for filename, data in item.content.items():
                with AtomicReplaceFile(self._boot_path / filename) as temp:
                    if isinstance(data, bytes):
                        temp.write(data)
                    else:
                        temp.write(b''.join(
                            line.encode('ascii') for line in data))
        else:
            self._store_path.mkdir(parents=True, exist_ok=True)
            # TODO use mode 'x'? Add a --force to overwrite with mode 'w'?
            with ZipFile(str(self._path_of(key)), 'w',
                         compression=ZIP_DEFLATED) as arc:
                arc.comment = 'pictl:0:{hash}\n\n{warning}'.format(
                    hash=item.hash, warning=_(
                        'Do not edit the content of this archive; the line '
                        'above is a hash of the content which will not match '
                        'after manual editing. Please use the pictl tool to '
                        'manipulate stored boot configurations'),
                ).encode('ascii')
                for path, data in item.content.items():
                    if isinstance(data, bytes):
                        arc.writestr(str(path), data)
                    else:
                        arc.writestr(str(path), b''.join(
                            line.encode('ascii') for line in data))

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


class DefaultConfiguration:
    """
    Represents the default boot configuration with an entirely empty content
    and a fresh :class:`Settings` instance.
    """
    @property
    def content(self):
        return {}

    @property
    def hash(self):
        return 'da39a3ee5e6b4b0d3255bfef95601890afd80709'  # empty sha1

    @property
    def timestamp(self):
        return datetime.fromtimestamp(0)  # UNIX epoch

    @property
    def settings(self):
        return Settings()


class BootConfiguration:
    """
    Represents the current boot configuration, as parsed from *filename*
    (default "config.txt") on the boot partition (presumably mounted at
    *path*).
    """
    def __init__(self, path, filename='config.txt'):
        self._path = path
        self._filename = filename
        self._settings = None
        self._content = None
        self._hash = None
        self._timestamp = None

    def _parse(self):
        assert self._settings is None
        parser = BootParser(self._path)
        parser.parse(self._filename)
        self._settings = Settings()
        for setting in self._settings.values():
            for item, value in setting.extract(parser.config):
                setting._value = value
                # TODO track the config items affecting the setting
        for setting in self._settings.values():
            if isinstance(setting, CommandIncludedFile):
                parser.add(setting.filename)
        self._content = parser.content
        self._hash = parser.hash
        self._timestamp = parser.timestamp

    @property
    def path(self):
        return self._path

    @property
    def filename(self):
        return self._filename

    @property
    def timestamp(self):
        if self._timestamp is None:
            self._parse()
        return self._timestamp

    @property
    def hash(self):
        if self._hash is None:
            self._parse()
        return self._hash

    @property
    def settings(self):
        if self._settings is None:
            self._parse()
        return self._settings

    @property
    def content(self):
        if self._content is None:
            self._parse()
        return self._content


class StoredConfiguration(BootConfiguration):
    """
    Represents a boot configuration stored in a zip file specified by *path*.
    The starting file of the configuration is given by *filename*.
    """
    def __init__(self, path, filename='config.txt'):
        super().__init__(ZipFile(str(path), 'r'), filename)
        # We can grab the hash and timestamp from the arc's meta-data without
        # any decompression work (it's all in the uncompressed footer)
        comment = self.path.comment
        if comment.startswith(b'pictl:0:'):
            h = comment[8:48].decode('ascii')
            if len(h) != 40:
                raise ValueError(_(
                    'Invalid stored configuration: invalid length'))
            if not set(h) <= set('0123456789abcdef'):
                raise ValueError(_(
                    'Invalid stored configuration: non-hex hash'))
            self._hash = h
            # A stored archive can be empty, hence default= is required
            self._timestamp = max(
                (datetime(*info.date_time) for info in self.path.infolist()),
                default=datetime.fromtimestamp(0))
        else:
            # TODO Should we allow "self-made" archives without a pictl
            # header comment? We can't currently reach here because the
            # enumerate and contains tests check for pictl:0: but that
            # could be relaxed...
            assert False, 'Invalid stored configuration: missing hash'


class Settings(Mapping):
    """
    Represents all settings in a boot configuration; acts like an ordered
    mapping of names to :class:`Setting` objects.
    """
    def __init__(self):
        self._items = deepcopy(SETTINGS)
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
            (setting, other[setting.name]
                      if setting.name in other else
                      None)
            for setting in self.values()
            if setting.name not in other or
            other[setting.name].value != setting.value
        } | {
            (None, setting)
            for name in other
            if name not in self
        }

    def update(self, values):
        """
        Given a mapping of setting names to new values, updates the values
        of the corresponding settings in this collection. If a value is
        :data:`None`, the setting is reset to its default value.
        """
        # TODO move this to BootConfiguration and have it wipe content and hash
        # upon call (for later recalculation)
        for name, value in values.items():
            if name not in self._visible:
                raise KeyError(name)
            item = self._items[name]
            item._value = item.update(value)

    def validate(self):
        """
        Checks for errors in the configuration. This ensures that each setting
        makes sense in the wider context of all other settings.
        """
        # TODO move to BootConfiguration?
        # This ignores the _visible filter; the complete configuration is
        # always validated
        for item in self._items.values():
            item.validate()

    def output(self):
        """
        Generate a new boot configuration file which represents the settings
        stored in this mapping.
        """
        # TODO move to BootConfiguration; have it update content and hash too
        output = """\
# This file is intended to contain system-made configuration changes. User
# configuration changes should be placed in "usercfg.txt". Please refer to the
# README file for a description of the various configuration files on the boot
# partition.

""".splitlines()
        for name, setting in self._items.items():
            if name in self._visible:
                for line in setting.output():
                    output.append(line)
        return '\n'.join(output)
