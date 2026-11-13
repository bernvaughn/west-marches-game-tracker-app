"""Static storage that adds a content-hash version to every URL.

Works with runserver and tests: no collectstatic step is needed.
"""
import hashlib
import os

from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import StaticFilesStorage


class VersionedStaticFilesStorage(StaticFilesStorage):
    _hash_cache: dict = {}

    def _source_path(self, name):
        found = finders.find(name)
        if isinstance(found, (list, tuple)):
            found = found[0] if found else None
        if found:
            return found
        path = self.path(name)
        return path if os.path.isfile(path) else None

    def _version(self, name):
        path = self._source_path(name)
        if not path:
            return None
        try:
            st = os.stat(path)
            key = (path, st.st_mtime_ns, st.st_size)
            if key not in self._hash_cache:
                with open(path, "rb") as fh:
                    self._hash_cache[key] = hashlib.sha256(fh.read()).hexdigest()[:12]
            return self._hash_cache[key]
        except OSError:
            return None

    def url(self, name):
        url = super().url(name)
        version = self._version(name) if name else None
        if version and "?" not in url:
            url += f"?v={version}"
        return url
