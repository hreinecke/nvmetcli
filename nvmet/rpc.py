'''
Implements JSON-RPC handlers for the NVMe target configfs hierarchy

Copyright (c) 2021 Hannes Reinecke, SUSE LLC

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

import os
import stat
import json
import nvmet as nvme

class JsonRPC:
    def _get_subsystems(self, params = None):
        return [s.dump() for s in self.cfg.subsystems]

    def _get_transports(self, params = None):
        km = kmod.Kmod()
        ml = []
        for m in km.loaded():
            if m.name.startswith("nvmet_"):
                ml.append(m.name[len("nvmet_"):])
            elif m.name == "nvme_loop":
                ml.append(m.name[len("nvme_"):])
        return ml

    def _create_transport(self, params):
        trtype = params['trtype']
        if trtype.lower() == 'loop':
            prefix = "nvme_"
        else:
            prefix = "nvmet_"
        try:
            self.cfg._modprobe(prefix + trtype.lower())
        except:
            raise NameError("Module %s%s not found" % (prefix, trtype.lower()))

    def _create_subsystem(self, params):
        nqn = params['nqn']
        try:
            subsys = nvme.Subsystem(nqn, mode='create')
        except:
            raise RuntimeError("Failed to create subsystem %s" % nqn)
        if 'model_number' in params:
            model = params['model_number']
            if (len(model) > 40):
                subsys.delete()
                raise NameError("Model number longer than 40 characters")
            try:
                subsys.set_attr("attr", "model", model)
            except:
                subsys.delete()
                raise RuntimeError("Failed to set model %s" % model)
        if 'serial_number' in params:
            serial = params['serial_number']
            if len(serial) > 20:
                subsys.delete()
                raise NameError("Serial number longer than 20 characters")
            try:
                subsys.set_attr("attr", "serial", serial)
            except:
                subsys.delete()
                raise RuntimeError("Failed to set serial %s" % serial)
        if 'allow_any_host' in params:
            subsys.set_attr("attr", "allow_any_host", "1")

    def _delete_subsystem(self, params):
        nqn = params['nqn']
        try:
            subsys = nvme.Subsystem(nqn, mode='lookup');
        except CFSError:
            raise NameError("Subsystem %s not found" % nqn)
        try:
            subsys.delete()
        except:
            raise RuntimeError("Failed to delete subsystem %s" % nqn)

    def _add_ns(self, params):
        nqn = params['nqn']
        ns_params = params['namespace']
        bdev_name = ns_params['bdev_name']
        try:
            bdev = BlockDevice(bdev_name)
        except:
            raise NameError("bdev %s not found" % bdev_name)
        try:
            subsys = nvme.Subsystem(nqn, mode='lookup')
        except CFSError:
            raise NameError("Subsystem %s not found" % nqn)

        if 'nsid' in ns_params:
            nsid = ns_params['nsid']

        try:
            ns = nvme.Namespace(subsys, nsid, mode='create')
        except:
            raise NameError("Namespace %s already exists" % nsid)
        try:
            ns.set_attr("device", "uuid", bdev.uuid)
        except:
            ns.delete()
            raise RuntimeError("Failed to set uuid %s on ns %s" % (bdev.uuid, nsid))
        try:
            ns.set_attr("device", "path", bdev.uuid_path)
        except:
            ns.delete()
            raise RuntimeError("Failed to set path on ns %s" % nsid)
        try:
            ns.set_enable(1)
        except:
            raise RuntimeError("Failed to enable ns %s" % nsid)

    def _remove_ns(self, params):
        nqn = params['nqn']
        nsid = params['nsid']
        try:
            subsys = nvme.Subsystem(nqn, mode='lookup')
        except CFSError:
            raise NameError("Subsystem %s not found" % nqn)
        try:
            ns = nvme.Namespace(subsys, nsid, mode='lookup')
        except CFSError:
            raise NameError("Namespace %d not found" % nsid)
        ns.delete()

    def _add_port(self, params):
        try:
            port = nvme.Port(mode='create')
        except:
            raise RuntimeError("Cannot create port")
        port_params = params['listen_address']
        for p in ('trtype', 'adrfam', 'traddr', 'trsvcid'):
            if p not in port_params:
                port.delete()
                raise NameError("Invalid listen_address parameter %s" % p)
            v = port_params[p]
            if p == 'adrfam':
                v = port_params[p].lower()
            try:
                port.set_attr("addr", p, v)
            except:
                port.delete()
                raise RuntimeError("Failed to set %s to %s" % (p, v))
        nqn = params['nqn']
        try:
            port.add_subsystem(nqn)
        except:
            port.delete()
            raise NameError("subsystem %s not found" % nqn)

    def _remove_port(self, params):
        nqn = params['nqn']
        port_params = params['listen_address']
        for port in self.cfg.ports:
            for p in ('trtype', 'adrfam', 'traddr', 'trsvcid'):
                if p not in port_params:
                    continue
                if port.get_attr("addr", p) != port_params[p]:
                    continue
            for s in port.subsystems:
                if s != nqn:
                    continue
                port.remove_subsystem(nqn)
                if not len(port.subsystems):
                    port.delete()

    def _add_host(self, params):
        nqn = params['nqn']
        try:
            subsys = nvme.Subsystem(nqn, mode='lookup')
        except CFSError:
            raise NameError("Subsystem %s not found" % nqn)
        host = params['host']
        try:
            subsys.add_allowed_host(host)
        except CFSError:
            return False
        return True

    def _remove_host(self, params):
        nqn = params['nqn']
        try:
            subsys = nvme.Subsystem(nqn, mode='lookup')
        except CFSError:
            raise NameError("Subsystem %s not found" % nqn)
        host = params['host']
        try:
            subsys.remove_allowed_host(host)
        except CFSError:
            return False
        return True

    def _get_config(self, params):
        return self.cfg.dump()

    def _set_config(self, params):
        try:
            self.cfg.restore(params)
        except CFSError:
            raise RuntimeError("Failed to apply configuration")

    def _create_malloc(self, params):
        bdev_name = params['name']
        bdev_blocksize = params['block_size']
        bdev_blocks = params['num_blocks']
        if 'uuid' in params:
            bdev_uuid = params['uuid']
        else:
            bdev_uuid = None

        bdev = BlockDevice(bdev_name, bdev_uuid, type='malloc', mode='create')
        bdev.set_size(int(bdev_blocks) * int(bdev_blocksize))
        return bdev.name

    def _delete_malloc(self, params):
        bdev_name = params['name']
        bdev = BlockDevice(bdev_name, type='malloc')
        bdev.delete()

    def _create_lvol(self, params):
        bdev_name = params['lvol_name']
        bdev_size = params['size']
        if 'uuid' in params:
            bdev_uuid = params['uuid']
        else:
            bdev_uuid = None

        bdev = BlockDevice(bdev_name, bdev_uuid, type='lvol', mode='create')
        bdev.set_size(int(bdev_size))
        return bdev.name

    def _delete_lvol(self, params):
        bdev_name = params['name']
        bdev = BlockDevice(bdev_name, type='lvol')
        bdev.delete()

    def _snapshot_lvol(self, params):
        lvol = params['lvol_name']
        snap = params['snapshot_name']
        bdev = BlockDevice(lvol, type='lvol')
        return bdev.snapshot(snap)

    def _clone_lvol(self, params):
        snap = params['snapshot_name']
        clone = params['clone_name']
        bdev = BlockDevice(snap, type='lvol')
        return bdev.snapshot(clone)

    def _get_lvolstores(self, params):
        if params:
            if 'uuid' in params:
                lvs_uuid = params['uuid']
            if 'lvs_name' in params:
                lvs_name = params['lvs_name']
        st = os.statvfs(BlockDevice._path_prefix['lvol'])
        return dict(name='longhorn',
                    cluster_size=st.f_frsize,
                    free_clusters=st.f_bavail,
                    total_data_clusters=st.f_blocks)

    _rpc_methods = dict(bdev_malloc_create=_create_malloc,
                        bdev_malloc_delete=_delete_malloc,
                        bdev_lvol_create=_create_lvol,
                        bdev_lvol_delete=_delete_lvol,
                        bdev_lvol_snapshot=_snapshot_lvol,
                        bdev_lvol_clone=_clone_lvol,
                        bdev_lvol_get_lvstores=_get_lvolstores,
                        nvmf_create_transport=_create_transport,
                        nvmf_get_transports=_get_transports,
                        nvmf_create_subsystem=_create_subsystem,
                        nvmf_delete_subsystem=_delete_subsystem,
                        nvmf_subsystem_add_ns=_add_ns,
                        nvmf_subsystem_remove_ns=_remove_ns,
                        nvmf_subsystem_add_listener=_add_port,
                        nvmf_subsystem_remove_listener=_remove_port,
                        nvmf_subsystem_add_host=_add_host,
                        nvmf_subsystem_remove_host=_remove_host,
                        nvmf_get_subsystems=_get_subsystems,
                        nvmf_get_config=_get_config,
                        nvmf_set_config=_set_config)

    def __init__(self):
        self.cfg = nvme.Root()

    def rpc_call(self, req):
        print ("%s" % req)
        if 'method' in req:
            method = req['method']
        else:
            method = None
        if 'params' in req:
            params = req['params']
        else:
            params = None
        resp = dict(jsonrpc='2.0')
        if 'id' in req:
            resp['id'] = req['id']
        if method not in self._rpc_methods:
            error = dict(code=-32601,message='Method not found')
            resp['error'] = error;
        else:
            try:
                result = self._rpc_methods[method](self, params)
                resp['result'] = result
            except NameError as n:
                error = dict(code=-32602, message='Invalid params', data=n.args)
                resp['error'] = error
            except RuntimeError as err:
                error = dict(code=-32000, message=err.args)
                resp['error'] = error
            print ("%s" % json.dumps(resp))
        return json.dumps(resp)

