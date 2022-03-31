# -*- coding: utf-8 -*-
"""
Method used by the mcpclient to ensure it's locked when doing server queries 
as the jsonrpclib.Server isn't thread safe.

It's an object method, thus the 'self' as first argument to the wrapper.
"""


def synchronized(f):
    def wrapper(self, *args, **kargs):
        try:
            self._myLock.acquire()
            return f(self, *args, **kargs)
        finally:
            self._myLock.release()
    return wrapper