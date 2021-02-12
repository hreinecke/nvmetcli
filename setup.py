#! /usr/bin/env python
'''
This file is part of ConfigShell.
Copyright (c) 2011-2013 by Datera, Inc

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

from setuptools import setup

setup(
    name = 'nvmetcli',
    version = 0.7,
    description = 'NVMe target configuration tool',
    license = 'Apache 2.0',
    maintainer = 'Christoph Hellwig',
    maintainer_email = 'hch@lst.de',
    test_suite='nose2.collector.collector',
    packages = ['nvmet'],
    scripts=['nvmetcli', 'nvmetproxy']
    )
