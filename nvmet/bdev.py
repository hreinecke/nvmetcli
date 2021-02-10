#!/usr/bin/python

'''
BlockDevice JSON-RPC handling functions

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
import sys
import json
import base64
import uuid as UUID
import nvmet as nvme

class BlockDevice:
    _path_prefix = dict( malloc='/dev/shm/', lvol='/srv/longhorn/')

    def __init__(self, name, uuid = None, type = 'any', mode = 'lookup'):
        self.name = name
        if type == 'any':
            if mode == 'create':
                raise NameError("Need to specify a mode for 'lookup'")
        elif type not in BlockDevice._path_prefix:
            raise NameError("Invalid bdev type %s" % type)

        if mode == 'lookup':
            if type == 'any':
                for p in BlockDevice._path_prefix:
                    self.prefix = BlockDevice._path_prefix[p]
                    if os.path.exists(self.prefix + name):
                        self.link_path = self.prefix + name
                        break
                if not self.link_path:
                    raise NameError("bdev %s not found" % name)
            else:
                self.prefix = BlockDevice._path_prefix[type]
                self.link_path = self.prefix + name
                if not os.path.exists(self.link_path):
                    raise NameError("%s bdev %s not found" % (type, name))
            try:
                self.uuid_path = os.readlink(self.link_path)
            except FileNotFoundError:
                raise RuntimeError("UUID symlink for bdev %s not found" % name)
            self.uuid = self.uuid_path[len(self.prefix):]
        else:
            self.prefix = BlockDevice._path_prefix[type]
            self.link_path = self.prefix + name
            if os.path.exists(self.prefix + name):
                raise NameError("%s bdev %s already exists" % (type, name))
            if uuid is None:
                self.uuid = str(UUID.uuid4())
            else:
                self.uuid = uuid
            self.uuid_path = self.prefix + self.uuid
            if os.path.exists(self.uuid_path):
                raise NameError("bdev %s already exists" % self.uuid_path)
            try:
                fd = open(self.uuid_path, 'x')
            except:
                raise NameError("Cannot create %s" % self.uuid_path)
            fd.close()
            try:
                os.symlink(self.uuid_path, self.link_path)
            except:
                raise RuntimeError("Failed to link %s to %s" % (self.link_path, self.uuid_path))

    def delete(self):
        try:
            os.remove(self.link_path)
        except FileNotFoundError:
            raise RuntimeError("link %s does not exist" % self.link_path)
        try:
            os.remove(self.uuid_path)
        except FileNotFoundError:
            raise RuntimeError("bdev %s does not exist" % self.uuid_path)

    def snapshot(self, clone, uuid=None):
        if not uuid:
            uuid = str(UUID.uuid4())
        clone_uuid_path = self.prefix + uuid
        if os.path.exists(clone_uuid_path):
            raise NameError("snapshot uuid %s already exists" % uuid)
        clone_link_path = self.prefix + clone
        if os.path.exists(clone_link_path):
            raise NameError("snapshot %s already exists" % clone)
        try:
            os.system("cp --reflink %s %s" % (self.uuid_path, clone_uuid_path) )
        except:
            raise RuntimeError("failed to clone bdev %s to %s" % (self.uuid_path, clone_uuid_path))
        try:
            os.symlink(clone_uuid_path, clone_link_path)
        except:
            raise RuntimeError("failed to link %s to %s" % (clone_link_path, clone_uuid_path))
        return clone

    def set_size(self, bdev_size):
        self.bdev_size = bdev_size
        try:
            os.truncate(self.uuid_path, self.bdev_size)
        except:
            raise RuntimeError("Failed to truncate %s" % self.uuid_path)

