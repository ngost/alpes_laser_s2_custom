# -*- coding: utf-8 -*-

import logging
import serial
from sdeux.communication import END

logger = logging.getLogger(__name__)

__author__ = 'gregory'
__copyright__ = "Copyright 2018, Alpes Lasers SA"


class S2CommunicationTimeout(Exception):
    pass


class S2SerialHandler(object):
    def __init__(self, port):
        self._serial = serial.Serial(baudrate=38400, timeout=0.2)
        self._serial.port = port

    def set_port(self, port):
        if self.is_open():
            raise Exception('Cannot change port while connected')
        self._serial.port = port

    def open(self):
        self._serial.open()
        self._serial.flushInput()
        self._serial.flushOutput()

    def close(self):
        self._serial.close()

    def is_open(self):
        return self._serial.is_open

    def write(self, data):
        self._serial.write(data)

    def read(self):
        msg = bytearray()
        while True:
            c = self._serial.read(1)
            if not c:
                raise S2CommunicationTimeout('Timeout')
            if c == END:
                if msg:
                    return msg
            else:
                msg += c