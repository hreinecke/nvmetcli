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
import netifaces
from pathlib import Path

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
        if not params or 'trtype' not in params:
            raise NameError("Parameter 'trtype' missing")
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
        if not params or 'nqn' not in params:
            nqn = None
        else:
            nqn = params['nqn']
        try:
            subsys = nvme.Subsystem(nqn, mode='create')
        except:
            raise RuntimeError("Failed to create subsystem %s" % nqn)
        if not params:
            return subsys.nqn
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
        return subsys.nqn

    def _delete_subsystem(self, params):
        if not params and 'nqn' not in params:
            raise NameError("Parameter 'nqn' missing")
        nqn = params['nqn']
        try:
            subsys = nvme.Subsystem(nqn, mode='lookup');
        except nvme.CFSError:
            raise NameError("Subsystem %s not found" % nqn)
        try:
            subsys.delete()
        except:
            raise RuntimeError("Failed to delete subsystem %s" % nqn)

    def _add_ns(self, params):
        if not params or 'nqn' not in params:
            raise NameError("Parameter 'nqn' missing")
        nqn = params['nqn']
        if 'namespace' not in params:
            raise NameError("Parameter 'namespace' missing")
        ns_params = params['namespace']
        if 'bdev_name' not in ns_params:
            raise NameError("Parameter 'namespace:bdev_name' missing")
        bdev_name = ns_params['bdev_name']
        try:
            bdev = nvme.BackingFile(self.pools, bdev_name)
        except:
            raise NameError("bdev %s not found" % bdev_name)
        try:
            subsys = nvme.Subsystem(nqn, mode='lookup')
        except nvme.CFSError:
            raise NameError("Subsystem %s not found" % nqn)

        if 'nsid' in ns_params:
            nsid = ns_params['nsid']
        else:
            nsid = None

        try:
            ns = nvme.Namespace(subsys, nsid, mode='create')
        except:
            raise NameError("Namespace %s already exists" % nsid)
        nsid = ns.nsid
        if 'uuid' in ns_params:
            try:
                ns.set_attr("device", "uuid", ns_params['uuid'])
            except:
                ns.delete()
                raise RuntimeError("Failed to set uuid %s on ns %s" % (ns_params['uuid'], nsid))
        if 'nguid' in ns_params:
            try:
                ns.set_attr("device", "nguid", ns_params['nguid'])
            except:
                ns.delete()
                raise RuntimeError("Failed to set nguid %s on ns %s" % (ns_params['nguid'], nsid))
        try:
            ns.set_attr("device", "path", bdev.file_path)
        except:
            ns.delete()
            raise RuntimeError("Failed to set path on ns %s" % nsid)
        try:
            ns.set_enable(1)
        except:
            raise RuntimeError("Failed to enable ns %s" % nsid)
        return nsid

    def _remove_ns(self, params):
        if not params and 'nqn' not in params:
            raise NameError("Parameter 'nqn' missing")
        nqn = params['nqn']
        if 'nsid' not in params:
            raise NameError("Parameter 'nsid' missing")
        nsid = params['nsid']
        try:
            subsys = nvme.Subsystem(nqn, mode='lookup')
        except nvme.CFSError:
            raise NameError("Subsystem %s not found" % nqn)
        try:
            ns = nvme.Namespace(subsys, nsid, mode='lookup')
        except nvme.CFSError:
            raise NameError("Namespace %d not found" % nsid)
        ns.delete()

    def _add_port(self, params):
        if not params or 'nqn' not in params:
            raise NameError("Parameter 'nqn' missing")
        if 'listen_address' in params:
            port_params = params['listen_address']
        elif 'port' in params:
            port_params = params['port']
        else:
            raise NameError("Parameter 'listen_address' missing")
        if 'portid' not in port_params:
            ids = [port.portid for port in self.cfg.ports]
            if len(ids):
                portid = max(ids)
            else:
                portid = 0
            portid = portid + 1
        else:
            portid = int(port_params['portid'])
        try:
            port = nvme.Port(portid, mode='create')
        except:
            raise RuntimeError("Port %d already exists" % portid)
        for p in ('trtype', 'adrfam', 'traddr', 'trsvcid'):
            if p not in port_params:
                if p != 'trsvcid':
                    port.delete()
                    raise NameError("Invalid listen_address parameter %s" % p)
                else:
                    v = 4420
            else:
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
        return port.portid

    def _remove_port(self, params):
        if not params or 'nqn' not in params:
            raise NameError("Parameter 'nqn' missing")
        if 'listen_address' in params:
            port_params = params['listen_address']
        elif 'port' in params:
            port_params = params['port']
        else:
            raise NameError("Parameter 'listen_address' missing")
        nqn = params['nqn']
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
        if not params or 'nqn' not in params:
            raise NameError("Parameter 'nqn' missing")
        if 'host' not in params:
            raise NameError("Parameter 'host' missing")
        nqn = params['nqn']
        try:
            subsys = nvme.Subsystem(nqn, mode='lookup')
        except nvme.CFSError:
            raise NameError("Subsystem %s not found" % nqn)
        host = nvme.Host(params['host'])
        try:
            subsys.add_allowed_host(host.nqn)
        except nvme.CFSError:
            raise RuntimeError("Could not add host %s to subsys %s" % (host, nqn))

    def _remove_host(self, params):
        if not params or 'nqn' not in params:
            raise NameError("Parameter 'nqn' missing")
        if 'host' not in params:
            raise NameError("Parameter 'host' missing")
        nqn = params['nqn']
        try:
            subsys = nvme.Subsystem(nqn, mode='lookup')
        except nvme.CFSError:
            raise NameError("Subsystem %s not found" % nqn)
        try:
            host = nvme.Host(params['host'], mode='lookup')
        except nvme.CFSError:
            raise NameError("Host %s not found" % params['host'])
        try:
            subsys.remove_allowed_host(host.nqn)
        except nvme.CFSError:
            raise RuntimeError("Failed to remove host %s from subsys %s" %
                               (nqn,  host.nqn))
        found = 0
        for subsys in self.cfg.subsystems:
            for h in subsys.allowed_hosts:
                if h.nqn == host.nqn:
                    found = found + 1
        if found == 0:
            host.delete()

    def _add_ana(self, params):
        if not params or 'portid' not in params:
            raise NameError("Parameter 'portid' missing")
        portid = params['portid']
        if 'grpid' in params:
            grpid = params['grpid']
        else:
            grpid = None
        try:
            port = nvme.Port(portid, mode='lookup')
        except:
            raise RuntimeError("Port %s not present" % portid)
        try:
            a = nvme.ANAGroup(port, grpid)
        except nvme.CFSError:
            raise RuntimeError("Port %s ANA Group %s already present" %
                               (portid, grpid))
        if 'ana_state' in params:
            try:
                a.set_attr("ana", "state", params['ana_state'])
            except nvme.CFSError:
                raise RuntimeError("Failed to set ANA state on group %s to %s"
                                   % (grpid, params['ana_state']))
        return a.get_attr("ana", "state")

    def _set_ana(self, params):
        if not params or 'portid' not in params:
            raise NameError("Parameter 'portid' missing")
        portid = params['portid']
        if 'grpid' not in params:
            raise NameError("Parameter 'grpid' missing")
        grpid = params['grpid']
        if 'ana_state' not in params:
            raise NameError("Parameter 'ana_state' missing")
        try:
            port = nvme.Port(portid, mode='lookup')
        except:
            raise RuntimeError("Port %s not found" % portid)
        for ana in port.ana_groups:
            if ana.grpid == int(grpid):
                try:
                    ana.set_attr("ana", "state", params['ana_state'])
                    return
                except nvme.CFSError:
                    raise RuntimeError("Failed to set ANA state to %s" % params['ana_state'])
        raise RuntimeError("ANA group %s not found" % grpid)

    def _remove_ana(self, params):
        if not params or 'portid' not in params:
            raise NameError("Parameter 'portid' missing")
        if 'grpid' not in params:
            raise NameError("Parameter 'grpid' missing")
        grpid = params['grpid']
        try:
            port = nvme.Port(params['portid'], mode='lookup')
        except:
            raise RuntimeError("Port %s not found" % params['portid'])
        grpids = [n.grpid for n in port.ana_groups]
        if int(grpid) not in grpids:
            raise RuntimeError("ANA group %s not found" % grpid)
        for ana in port.ana_groups:
            if ana.grpid == grpid:
                ana.delete()

    def _get_config(self, params):
        return self.cfg.dump()

    def _set_config(self, params):
        if not params:
            raise RuntimeError("Invalid configuration")
        try:
            self.cfg.restore(params, merge=True)
        except nvme.CFSError:
            raise RuntimeError("Failed to apply configuration")

    def _get_interfaces(self, params):
        ifnames = {}
        for i in netifaces.interfaces():
            if i == 'lo':
                continue;
            iflist = {}
            ifaddrs = netifaces.ifaddresses(i)
            try:
                a = ifaddrs[netifaces.AF_INET]
            except:
                pass
            else:
                addrlist = []
                for n in a:
                    addrlist.append(n['addr'])
                iflist['ipv4'] = addrlist
            try:
                a = ifaddrs[netifaces.AF_INET6]
            except:
                pass
            else:
                addrlist = []
                for n in a:
                    addrlist.append(n['addr'])
                iflist['ipv6'] = addrlist
            ifnames[i] = iflist
        return ifnames

    def _create_file(self, params):
        if not params or 'file_name' not in params:
            raise NameError("parameter 'file_name' missing")
        file_name = params['file_name']
        if 'size' not in params:
            raise NameError("parameter 'size' missing")
        file_size = params['size']
        if 'pool' in params:
            file_pool = params['pool']
        else:
            file_pool = None
        bfile = nvme.BackingFile(self.pools, file_name, file_pool,
                                mode='create')
        bfile.set_size(int(file_size))
        return bfile.name

    def _delete_file(self, params):
        if not params or 'file_name' not in params:
            raise NameError("parameter 'file_name' missing")
        file_name = params['file_name']
        bfile = nvme.BackingFile(self.pools, file_name)
        bfile.delete()

    def _snapshot_file(self, params):
        if not params or 'file_name' not in params:
            raise NameError("parameter 'file_name' missing")
        file_name = params['file_name']
        snap = params['snapshot_name']
        bfile = nvme.BackingFile(self.pools, file_name)
        return bfile.snapshot(snap)

    def _clone_file(self, params):
        if not params or 'snapshot_name' not in params:
            raise NameError("parameter 'snapshot_name' missing")
        snap = params['snapshot_name']
        clone = params['clone_name']
        bfile = nvme.BackingFile(self.pools, snap)
        return bfile.snapshot(clone)

    def _get_pools(self, params):
        r = []
        for p in self.pools:
            path = Path(self.pools[p])
            filelist = []
            for f in path.iterdir():
                if f.is_file():
                    filelist.append(f.name)
            st = os.statvfs(self.pools[p])
            a = dict(name=p, cluster_size=st.f_frsize,
                     free_clusters=st.f_bavail,
                     total_data_clusters=st.f_blocks,
                     files=filelist)
            r.append(a)
        return r

    _rpc_methods = dict(bdev_file_list_pools=_get_pools,
                        bdev_file_create=_create_file,
                        bdev_file_delete=_delete_file,
                        bdev_file_snapshot=_snapshot_file,
                        bdev_file_clone=_clone_file,
                        nvmf_get_interfaces=_get_interfaces,
                        nvmf_create_transport=_create_transport,
                        nvmf_get_transports=_get_transports,
                        nvmf_create_subsystem=_create_subsystem,
                        nvmf_delete_subsystem=_delete_subsystem,
                        nvmf_subsystem_add_ns=_add_ns,
                        nvmf_subsystem_remove_ns=_remove_ns,
                        nvmf_subsystem_add_port=_add_port,
                        nvmf_subsystem_remove_port=_remove_port,
                        nvmf_subsystem_add_host=_add_host,
                        nvmf_subsystem_remove_host=_remove_host,
                        nvmf_get_subsystems=_get_subsystems,
                        nvmf_port_add_ana=_add_ana,
                        nvmf_port_set_ana=_set_ana,
                        nvmf_port_remove_ana=_remove_ana,
                        nvmf_get_config=_get_config,
                        nvmf_set_config=_set_config)

    def __init__(self, pools = None):
        self.cfg = nvme.Root()
        self.pools = pools

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

