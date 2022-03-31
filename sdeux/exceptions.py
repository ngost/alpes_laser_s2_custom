# -*- coding: utf-8 -*-

import logging

logger = logging.getLogger(__name__)

__author__ = 'gregory'
__copyright__ = "Copyright 2018, Alpes Lasers SA"


class S2OvercurrentError(Exception):
    pass


class S2UndervoltageError(Exception):
    pass


class S2InvalidVoltageError(Exception):
    pass


class S2InvalidPulseParamsError(Exception):
    pass


class S2CommandError(Exception):
    def __init__(self, msg, return_code):
        super(S2CommandError, self).__init__(msg)
        self.return_code = return_code
