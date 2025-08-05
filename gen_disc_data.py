#!/usr/bin/python3

import os
import struct
from glob import glob

nvmetdir = '/sys/kernel/config/nvmet'
discovery_nqn = 'nqn.2014-08.org.nvmexpress.discovery'

subtype_val = {
    'referral': 1,
    'nvm': 2,
    'current': 3,
    }

treq_val = {
    'not specified': 0,
    'required': 1,
    'not required': 2
    }

trtype_val = {
    'rdma': 1,
    'fc': 2,
    'tcp': 3,
    }

adrfam_val = {
    'ipv4': 1,
    'ipv6': 2,
    'ib': 3,
    'fc': 4,
    }

tsas_tcp_val = {
    'none': 0,
    'tls1.2': 1,
    'tls1.3': 2,
    }

def port_attr(port):
    attr = {
        'trtype': 254,
        'adrfam': 254,
        'treq': 3,
        'trsvcid': '',
        'traddr': '',
        'tsas': 0,
        'cntlid': 0xffff,
        'eflags': 0,
        'asqsz': 32,
        }
    for a in glob(f'{port}/addr_*'):
        addr = os.path.basename(a).split('_')[1]
        with open(a, 'r') as fd:
            val = fd.read().strip()
            if (addr == 'treq'):
                if val in treq_val:
                    attr[addr] = treq_val[val]
            elif (addr == 'trtype'):
                if val in trtype_val:
                    attr[addr] = trtype_val[val]
            elif (addr == 'adrfam'):
                if val in adrfam_val:
                    attr[addr] = adrfam_val[val]
            elif (addr == 'tsas'):
                if val in tsas_tcp_val:
                    attr[addr] = bytes(tsas_tcp_val[val])
            elif (addr == 'trsvcid'):
                attr[addr] = bytes.fromhex(''.join([hex(ord(char))[2:] for char in val]))
            elif (addr == 'traddr'):
                attr[addr] = bytes.fromhex(''.join([hex(ord(char))[2:] for char in val]))
            else:
                print(f'{portid}: addr {addr} val {val}')
    return attr

def format_lpe(subsysnqn):
    portid = 0
    lpe = []
    for port in glob(f'{nvmetdir}/ports/*'):
        if os.path.isdir(port):
            portid = portid + 1
            attr = port_attr(port)
            attr['portid'] = portid
            attr['subtype'] = subtype_val['nvm']

            nqn = discovery_nqn
            subsys = bytes.fromhex(''.join([hex(ord(char))[2:] for char in nqn]))
            attr['subtype'] = subtype_val['current']
            disc_entry = struct.pack("<BBBBHHHH20x32s192x256s256s256s",
                                     attr['trtype'], attr['adrfam'],
                                     attr['subtype'], attr['treq'],
                                     attr['portid'], attr['cntlid'],
                                     attr['asqsz'], attr['eflags'],
                                     attr['trsvcid'], subsys,
                                     attr['traddr'], attr['tsas'])
            lpe.append(disc_entry)

            for s in glob(f'{port}/subsystems/*'):
                nqn = os.path.basename(s)
                if (nqn != subsysnqn):
                    continue
                subsys = bytes.fromhex(''.join([hex(ord(char))[2:] for char in nqn]))
                disc_entry = struct.pack("<BBBBHHHH20x32s192x256s256s256s",
                                         attr['trtype'], attr['adrfam'],
                                         attr['subtype'], attr['treq'],
                                         attr['portid'], attr['cntlid'],
                                         attr['asqsz'], attr['eflags'],
                                         attr['trsvcid'], subsys,
                                         attr['traddr'], attr['tsas'])
                lpe.append(disc_entry)
    return lpe

def format_hdr(lpe):
    genctr = 1
    numrec = len(lpe)
    recfmt = 0
    dlpf = 4
    tdlpl = (numrec + 1) * 1024

    hdr = struct.pack("<QQHBxL1000x",
                      genctr, numrec, recfmt,
                      dlpf, tdlpl)
    return hdr

if __name__ == "__main__":
    subsys = 'nqn.blktests-subsys-1'
    lpe = format_lpe(subsys)
    if (len(lpe) == 1):
        raise(f'no records for {subsys}')

    hdr = format_hdr(lpe)
    lplen = len(hdr)
    for e in lpe:
        lplen = lplen + len(e)
    num = 0
    print('/* Automatically generated, do not edit */')
    print(f'static size_t disc_data_len = {lplen};')
    print("static char disc_data[" + str(lplen) + "] = {")
    for c in struct.unpack("<1024B", hdr):
        if (num == 0):
            print('\t', end='')
        elif (num % 16) == 0:
            print('\n\t', end='')
        print('0x{:02x}, '.format(c), end='')
        num = num + 1
    for e in lpe:
        for c in struct.unpack("<1024B", e):
            if (num % 16) == 0:
                print('\n\t', end='')
            print('0x{:02x}, '.format(c), end='')
            num = num + 1
    print('\n};')

