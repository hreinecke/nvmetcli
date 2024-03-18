'''
Filesystem abstraction for NVMe target hierarchy

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

import stat
import os
from glob import iglob as glob

from .error import CFSError, CFSNotFound

class Filesystem(object):

    configfs_dir = '/sys/kernel/config'

    def create(self, path):
        os.mkdir(f'{self.configfs_dir}/{path}')

    def fetch(self, path):
        cfs_path = f'{self.configfs_dir}{path}'
        try:
            with open(cfs_path, 'r') as fd:
                return fd.read().strip()
        except FileNotFoundError:
            raise CFSNotFound(f'Cannot find {cfs_path}')
        except Exception as e:
            raise CFSError(f'Failed to read {cfs_path}: {e}')

    def fetch_list(self, path, value):
        return [os.path.basename(name)
                for name in os.listdir(f'{self.configfs_dir}{path}/{value}/')]

    def modify(self, path, value):
        cfs_path = f'{self.configfs_dir}{path}'

        if not os.path.isfile(cfs_path):
            raise CFSNotFound(f'Cannot find attribute: {cfs_path}')
        try:
            with open(f'{self.configfs_dir}{path}', 'w') as fd:
                fd.write(str(value))
        except Exception as e:
            raise CFSError(f'Cannot set attribute {path}: {e}')

    def remove(self, path):
        cfs_path = f'{self.configfs_dir}{path}'

        if not os.path.isdir(cfs_path):
            return
        try:
            os.rmdir(cfs_path)
        except Exception as e:
            raise CFSError(f'Failed to remove {path}: {e}')

    def link(self, src, dst):
        os.symlink(f'{self.configfs_dir}{src}', f'{self.configfs_dir}{dst}')

    def unlink(self, path):
        os.unlink(f'{self.configfs_dir}{path}')

    def test(self, path):
        return os.path.isdir(f'{self.configfs_dir}{path}')

    def test_attr(self, path):
        return os.path.isfile(f'{self.configfs_dir}{path}')

    def test_writable(self, path):
        s = os.stat(f'{self.configfs_dir}{path}')
        return s[stat.ST_MODE] & stat.S_IWUSR

    def attr_names(self, path, group):
        return [os.path.basename(name).split('_', 1)[1]
                for name in glob("%s%s/%s_*" % (self.configfs_dir, path, group))
                    if os.path.isfile(name)]

    def namelist(self, path, name):
        return os.listdir(f'{self.configfs_dir}{path}/{name}/')
