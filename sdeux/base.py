# -*- coding: utf-8 -*-
"""
Created by chiesa on 01.09.15

Copyright 2015 Alpes Lasers SA, Neuchatel, Switzerland
"""
import logging

__author__ = 'chiesa'
__copyright__ = "Copyright 2015, Alpes Lasers SA"


class BaseDriver(object):

    def __init__(self, th):
        """
        Base class for all drivers.
        :param th: the transport handler used to talk to the device.
        :return:
        """
        self.th = th
        self.instrumentRanges = None

    def set_up(self):
        """
        Used to reset the instrument to a known state.
        :return:
        """
        pass

    def shut_down(self):
        """
        Used to switch the device off.
        :return:
        """
        pass

    def is_alive(self):
        """
        Check that the device is connected.
        :return:
        """
        return True

    def whoareyou(self):
        """
        Returns an identifier for the instruments, for instance the response of the
        *IDN? method.
        :return:
        """
        return ""

    def __repr__(self):
        return '<{0}(th={1})>'.format(self.__class__.__name__,
                                      self.th)

    def __str__(self):
        return self.__repr__()
