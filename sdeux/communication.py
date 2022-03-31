# -*- coding: utf-8 -*-
"""
Created by gregory on 14.02.18

Copyright 2018 Alpes Lasers SA, Neuchatel, Switzerland
"""
import logging
import struct
import threading
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

__author__ = 'gregory'
__copyright__ = "Copyright 2018, Alpes Lasers SA"

S2_PACKET_TYPE_SIZE = 2
S2_PACKET_DATA_SIZE = 60
S2_CHECKSUM_SIZE = 2
S2_PACKET_SIZE = S2_PACKET_TYPE_SIZE + S2_PACKET_DATA_SIZE + S2_CHECKSUM_SIZE

END = b'\xc0'
ESC = b'\xdb'
ESC_END = b'\xdb\xdc'
ESC_ESC = b'\xdb\xdd'


_S2PacketTypeStruct = struct.Struct('<H')


class S2Payload(object):
    __slots__ = ()
    _STRUCT = struct.Struct('')

    def __init__(self, *args, **kwargs):
        if args:
            if len(args) != len(self.__slots__):
                raise ValueError('Provide {} positional arguments'.format(len(self.__slots__)))
            for k, v in zip(self.__slots__, args):
                setattr(self, k, v)
        if kwargs:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def pack_into(self, buffer):
        self._STRUCT.pack_into(buffer, S2_PACKET_TYPE_SIZE, *self)

    def unpack_from(self, buffer):
        logger.debug('HEADER: {}'.format(buffer[:2]))
        values = self._STRUCT.unpack_from(buffer, S2_PACKET_TYPE_SIZE)
        for k, v in zip(self.__slots__, values):
            setattr(self, k, v)

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}

    def __iter__(self):
        return (getattr(self, x) for x in self.__slots__)

    def __repr__(self):
        return '{}: {}'.format(type(self).__name__, ', '.join(map(lambda k: '{}={}'.format(k, getattr(self, k)),
                                                                  self.__slots__)))


def _fletcher16(data):
    sum_1 = 0
    sum_2 = 0
    for b in data:
        sum_1 = (sum_1 + b) % 255
        sum_2 = (sum_1 + sum_2) % 255
    return bytearray([sum_1, sum_2])


def _slip_encode(data):
    return END + data.replace(ESC, ESC_ESC).replace(END, ESC_END) + END


def _slip_decode(data):
    return data.strip(END).replace(ESC_END, END).replace(ESC_ESC, ESC)


def _packet_wrap(data):
    if len(data) != S2_PACKET_SIZE:
        raise ValueError('data is not a valid S2 packet')
    chksum = _fletcher16(data[:-S2_CHECKSUM_SIZE])
    data[-S2_CHECKSUM_SIZE:] = chksum
    return _slip_encode(data)


def _packet_unwrap(packet):
    data = _slip_decode(packet)
    if len(data) != S2_PACKET_SIZE:
        raise ValueError('data is not a valid S2 packet\n{}'.format(data))
    chksum = _fletcher16(data[:-S2_CHECKSUM_SIZE])
    if data[-S2_CHECKSUM_SIZE:] != chksum:
        raise ValueError('Invalid checksum')
    return data


def create_packet(packet_type, payload=None):
    data = bytearray(S2_PACKET_SIZE)
    _S2PacketTypeStruct.pack_into(data, 0, packet_type)
    if payload is not None:
        payload.pack_into(data)
    return _packet_wrap(data)


def _parse_packet(packet, payload=None, expected_header=None):
    data = _packet_unwrap(packet)
    header = _S2PacketTypeStruct.unpack(data[:2])[0]
    if expected_header is not None and expected_header != header:
        raise ValueError('expected: {}, got: {}'.format(expected_header, header))
    if payload is not None:
        payload.unpack_from(data)


RETRY_SOME = 'default_some'
RETRY_NO = 'no_retry'


class S2Base(object):

    def check_advanced_mode(self):
        if not self.advanced_mode:
            raise RuntimeError('This is an advanced command that may compromise the device conformity. '
                               'Please set the advanced_mode attribute to True to execute this command.')

    @property
    def comm_failure_rate_percent(self):
        return 100.0 * self._num_commands_failed / self._num_commands_sent if self._num_commands_sent > 0 else 0.0

    @property
    def hw_version(self):
        raise NotImplementedError

    @property
    def device_id(self):
        raise NotImplementedError

    @property
    def available_pulsing_modes(self):
        return []

    def get_al_identifier(self):
        return 'S2-{}-{}'.format('V{}'.format(self.hw_version), self.device_id)

    @property
    def meta_info(self):
        return {'device': {'hw_version': self.hw_version,
                           'device_id': self.device_id,
                           'al_identifier': self.get_al_identifier()},
                'default': {'settings': {'voltage': {'units': 'V'},
                                         'pulse_period': {'units': 'us'},
                                         'pulse_width': {'units': 'us'},
                                         'current_limit': {'units': 'A'}}},
                'settings': {'pulsing_mode': {x: {} for x in self.available_pulsing_modes}}}

    def __init__(self, th, retry_policy=RETRY_SOME):
        self.th = th
        self.max_voltage_step = 0.4  # Voltage step used for the ramping
        self.voltage_ramp_speed = 2.0  # voltage speed in [V/s] used for the ramping
        self._lock = threading.RLock()
        self._num_commands_sent = 0
        self._num_commands_failed = 0
        self._ignore_comm_count = False
        self.retry_policy = retry_policy
        self.advanced_mode = False

    def _read_packet(self, payload=None, expected_header=None, expected_response_time=None):
        """Reads a packet from the transport handler. Discards empty messages as they probably result from the first END
        delimiter of SLIP packets"""
        expected_response_time = expected_response_time or 0
        start = time.time()
        while True:
            while True:
                try:
                    msg = self.th.read()
                    logger.debug('Message read in th [{}]'.format(msg))
                    break
                except Exception as e:
                    if time.time() - start > expected_response_time:
                        raise e
            if len(msg) < S2_PACKET_SIZE:
                continue
            try:
                _parse_packet(msg, payload, expected_header=expected_header)
                logger.debug('Parsed packet [{}]'.format(payload))
                return payload
            except Exception as e:
                logger.debug('Could not parse message "{}": {}'.format(msg, e))
                raise e

    def _query_packet(self, packet, response_payload=None, expected_header=None,
                      expected_response_time=1.0):
        """Method to send a packet to the S2 with a retry if necessary.
        The default retry policy is to try for 3 secs max but
        at least twice"""
        with self._lock:
            start = time.time()
            num_tries = 0
            while True:
                num_tries += 1
                try:
                    if not self._ignore_comm_count:
                        self._num_commands_sent += 1
                    self.th.write(packet)
                    logger.debug('Written packet to th [{}]'.format(packet))
                    return self._read_packet(response_payload, expected_header=expected_header,
                                             expected_response_time=expected_response_time)

                except Exception as e:
                    logger.info('S2 communication error [{}]'.format(e))
                    if self.retry_policy == RETRY_NO:
                        raise
                    if not self._ignore_comm_count:
                        self._num_commands_failed += 1
                    if num_tries >= 2 and time.time() - start >= 3:
                        raise
                    time.sleep(0.1)
                finally:
                    logger.debug('_query_packet() took {:.0f}ms'.format((time.time() - start)*1000.0))

