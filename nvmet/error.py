'''
Implements access to the NVMe target hierarchy

Copyright (c) 2023 SUSE Linux

SPDX-Licence-Identifier: Apache-2.0
'''

class CFSError(Exception):
    '''
    Generic slib error.
    '''
    pass


class CFSNotFound(CFSError):
    '''
    The underlying object does not exist. Happens when
    calling methods of an object that is instantiated but have
    been deleted, or when trying to lookup an object that does not exist.
    '''
    pass
