#!/usr/bin/python

'''
BackingFile JSON-RPC handling functions

Copyright (c) 2021 by Hannes Reinecke, SUSE Linux LLC

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

from __future__ import print_function

import os

class BackingFile:
    def __init__(self, pools, name, pool = None, mode = 'lookup'):
        self.name = name
        if mode != 'lookup' and not pool:
            for pool in pools:
                break
        if pool and pool not in pools:
            raise NameError("Invalid pool '%s'" % pool)
        if mode == 'lookup':
            if not pool:
                for pool in pools:
                    self.prefix = pools[pool]
                    path = self.prefix + '/' + name
                    if os.path.exists(path):
                        self.file_path = path
                        break
                if not self.file_path:
                    raise NameError("backing file '%s' not found" % name)
            else:
                self.prefix = pools[pool]
                path = self.prefix + '/' + name
                if not os.path.exists(path):
                    raise NameError("%s: backing file '%s' not found" % (pool, name))
                self.file_path = path
        elif mode == 'create':
            self.prefix = pools[pool]
            path = self.prefix + '/' + name
            if os.path.exists(path):
                raise NameError("%s: backing file '%s' already exists" % (pool, path))
            try:
                fd = open(path, 'x')
            except:
                raise NameError("%s: Cannot create backing file '%s'" % (pool, name))
            fd.close()
            self.file_path = path

    def delete(self):
        try:
            os.remove(self.file_path)
        except FileNotFoundError:
            return RuntimeError("%s: cannot delete backing file '%s'" % (pool, name))

    def set_size(self, file_size):
        self.file_size = file_size
        try:
            os.truncate(self.file_path, self.file_size)
        except:
            raise RuntimeError("Failed to truncate %s" % self.file_path)
