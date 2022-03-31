# -*- coding: utf-8 -*-

import logging
import struct

from sdeux.communication import create_packet, S2Base, S2Payload
from sdeux.defs import S2_PACKET_INFO
from sdeux.gen4 import S2 as S2_gen4
from sdeux.gen5 import S2 as S2_gen5
from sdeux.gen2005 import S2 as S2_gen2005

logger = logging.getLogger(__name__)


__author__ = 'gregory'
__copyright__ = "Copyright 2018, Alpes Lasers SA"

_info_query_packet = create_packet(S2_PACKET_INFO)


class S2Info(S2Payload):
    __slots__ = ('device_id', 'sw_version', 'hw_version')
    _STRUCT = struct.Struct('<IHH')


class S2Generic(S2Base):
    def get_hw_version(self):
        info = self._query_packet(_info_query_packet, S2Info())
        return info.hw_version


def init_driver(th):
    s2 = S2Generic(th)
    hw_version = s2.get_hw_version()
    if hw_version == 4:
        return S2_gen4(th)
    elif hw_version == 5:
        return S2_gen5(th)
    elif hw_version == 2005:
        return S2_gen2005(th)
    raise Exception('Unknown S2 hardware version {}'.format(hw_version))
