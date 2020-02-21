import gettext
import tempfile
from weakref import ref
from pathlib import Path
from copy import deepcopy
from fnmatch import fnmatch
from collections import OrderedDict
from collections.abc import Mapping
from zipfile import ZipFile, BadZipFile, ZIP_DEFLATED

from .files import AtomicReplaceFile
from .parser import BootParser
from .setting import CommandIncludedFile

_ = gettext.gettext


class Store(Mapping):
    """
    A mapping representing all stored boot configurations and the current
    boot configuration.

    Acts as a mapping keyed by the name of the stored configuration, or
    :data:`None` for the current boot configuration. The values of the mapping
    are objects which provide the parsed :class:`Settings`, an identifying
    :attr:`~StoredSettings.hash`, and a dictionary mapping filenames to
    contents.

    The mapping is mutable and this can be used to manipulate stored boot
    configurations. For instance, to store the current boot configuration under
    the name "default"::

        >>> store = Store(config)
        >>> store["default"] = store[None]

    Setting the item with the key :data:`None` overwrites the current boot
    configuration::

        >>> store[None] = store["serial"]

    Note that items retrieved from the store are ephemeral and modifying them
    does *not* modify the content of the store. To modify the content of the
    store, an item must be explicitly set::

        >>> default = store["default"]
        >>> default.settings.update({"serial.enabled": True})
        >>> store["serial"] = default

    The same applies to the current boot configuration item::

        >>> current = store[None]
        >>> current.settings.update({"camera.enabled": True, "gpu.mem": 128})
        >>> store[None] = current

    Items can be deleted to remove them from the store, with the obvious
    exception of the item with the key :data:`None` which cannot be removed.
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
        return sum(1 for i in self._enumerate()) + 1  # for the current config

    def __iter__(self):
        yield None  # the current boot configuration has no name
        yield from self._enumerate()

    def __contains__(self, key):
        if key is None:
            # The current boot configuration is always present (even if
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
        if key is None:
            return BootConfiguration(self._boot_path, self._config_read)
        elif key in self:
            return BootConfiguration(self._path_of(key), self._config_read)
        else:
            raise KeyError(_(
                "No stored configuration named {key}").format(key=key))

    def __setitem__(self, key, item):
        if key is None:
            # TODO Sort contents so config.txt is written last; this will allow
            # effectively atomic switches of configuration for systems using
            # os_prefix
            for filename, content in item.contents.items():
                with AtomicReplaceFile(self._boot_path / filename) as temp:
                    temp.write(content)
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
        if key is None:
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
        configuration is currently active, returns :data:`None` (the key of the
        current boot configuration).
        """
        current = self[None]
        for key in self:
            if key is not None:
                stored = self[key]
                if stored.hash == current.hash:
                    return key


class BootConfiguration:
    def __init__(self, path, filename='config.txt'):
        self._path = path
        self._filename = filename
        self._settings = None
        self._content = None
        # TODO Extract hash and timestamp from zip metadata for stored configs
        self._hash = None
        self._timestamp = None

    def _parse(self):
        assert self._settings is None
        parser = BootParser()
        parser.parse(self._path, self._filename)
        self._settings = Settings()
        for setting in self._settings.values():
            for item, value in setting.extract(parser.config):
                setting._value = value
                # TODO track the config items affecting the setting
        for setting in self._settings.values():
            if isinstance(setting, CommandIncludedFile):
                parser.add(self._path, setting.filename)
        self._content = parser.content
        self._hash = parser.hash.hexdigest().lower()
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


class Settings(Mapping):
    """
    Represents a complete configuration; acts like an ordered mapping of
    names to :class:`Setting` objects.
    """
    def __init__(self):
        # This is deliberately imported upon construction instead of at the
        # module level because the settings module is "expensive" to import and
        # materially affects start-up time on slower Pis; this matters where it
        # is not required (e.g. just running --help)
        from .settings import SETTINGS

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
        # This ignores the _visible filter; the complete configuration is
        # always validated
        for item in self._items.values():
            item.validate()

    def output(self):
        """
        Generate a new boot configuration file which represents the settings
        stored in this mapping.
        """
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
