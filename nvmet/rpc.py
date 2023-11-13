'''
REST API abstraction for NVMe target hierarchy

Copyright (c) 2023 SUSE LLC

Licensed under the Apache License, Version 2.0 (the "License"); you may
not use this file except in compliance with the License. You may obtain
a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
License for the specific language governing permissions and limitations
under the License.
'''

import requests
import json
from glob import iglob as glob

from .error import CFSError, CFSNotFound

class RESTapi(object):

    nvmet_url = 'http://127.0.0.1:5000'

    def __init__(self, uri):
        if uri:
            self.nvmet_url = uri

    def _get_path(self, path):
        return f'{self.nvmet_url}/{path}'

    def _error(self, r):
        print(f'error: {r.text}')
        m = r.reason
        if r.status_code < 400:
            t = r.json()
            if t and 'message' in t:
                m = t['message']
        if len(m):
            return f'{r.status_code}, {m}'
        else:
            return f'{r.status_code}'

    def create(self, path):
        r = requests.put(self._get_path(path))
        if r.ok:
            return
        msg = self._error(r)
        raise CFSError(f'Failed to create {path}: {msg}')

    def fetch(self, path):
        r = requests.get(self._get_path(path))
        if r.status_code == requests.codes.not_found:
            raise CFSNotFound(f'Cannot find attribute {path}')
        elif not r.ok:
            msg = self._error(r)
            raise CFSError(f'Failed to get {path}: {msg}')
        return r.json()

    def fetch_list(self, path, value):
        return self.fetch(f'{path}/{value}')

    def modify(self, path, value):
        r = requests.put(self._get_path(path), str(value))
        if r.status_code == requests.codes.not_found:
            raise CFSNotFound(f'Cannot find attribute: {path}')
        elif not r.ok:
            msg = self._error(r)
            raise CFSError(f'Cannot set {path} to {value}: {msg}')

    def remove(self, path):
        r = requests.delete(self._get_path(path))
        if r.status_code == requests.codes.not_found:
            return
        elif r.status_code == requests.codes.no_content:
            return
        elif not r.ok:
            msg = self._error(r)
            raise CFSError(f'Cannot delete {path}: {msg}')

    def link(self, src, dst):
        self.create(dst)

    def unlink(self, path):
        self.remove(path)

    def test(self, path):
        r = requests.head(self._get_path(path))
        if not r.ok:
            return False
        else:
            return True

    def test_attr(self, path):
        return self.test(path)

    def test_writable(self, path):
        # No mapping for REST API
        return True

    def attr_names(self, path, group):
        names = self.fetch(f'{path}')
        if group in names:
            return list(names[group])
        return {}

    def namelist(self, path, name):
        return self.fetch(f'{path}/{name}')
