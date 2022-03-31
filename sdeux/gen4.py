# -*- coding: utf-8 -*-

import logging
import struct
import math
import time

from sdeux.exceptions import (S2InvalidVoltageError, S2InvalidPulseParamsError, S2UndervoltageError,
                              S2OvercurrentError)
from sdeux.communication import S2Payload, S2Base, create_packet
from sdeux.defs import S2_PULSING_OFF, S2_PULSING_MODE_A, S2_PULSING_INTERNAL, S2_PULSING_MODE_B, \
    S2_PULSING_BURST_EXTERNAL, S2_PULSING_EXTERNAL, S2_STATUS_OK, S2_STATUS_OVERCURRENT, S2_STATUS_UNDERVOLTAGE, \
    S2_PACKET_INFO, S2_PACKET_QUERY_SETTINGS, S2_PACKET_QUERY_CALIBRATION, S2_PACKET_RESET_STATUS_FLAG, S2_PULSING_BURST, \
    S2_PACKET_SET_SETTINGS, S2_OPTION_SPECIAL_BURST_MODES, S2_OPTION_ALT_EXT_INPUT

logger = logging.getLogger(__name__)

__author__ = 'gregory'
__copyright__ = "Copyright 2018, Alpes Lasers SA"


class S2Info(S2Payload):
    __slots__ = ('device_id', 'sw_version', 'hw_version', 'input_voltage_measured', 'output_voltage_measured',
                 'output_current_measured', 'MCU_temperature', 'laser_temperature', 'reserved',
                 'output_current_measured_out_of_pulse', 'status', 'pulse_clock_frequency', 'API_version')
    _STRUCT = struct.Struct('<IHHfffff16sfHII')


class S2Settings(S2Payload):
    __slots__ = ('pulse_period', 'pulse_width', 'sync_out_width', 'output_voltage_set', 'output_current_limit',
                 'pulsing_mode', 'reserved_1', 'bias_t', 'reserved_2', 'reserved_3', 'reserved_4',
                 'pulse_period_prescaler', 'pulse_width_prescaler', 'burst_ON', 'burst_OFF')
    _STRUCT = struct.Struct('<HHHffHBfBBBHHII')

    @classmethod
    def default(cls):
        """

        :return S2Settings:
        """
        return S2Settings(pulse_period=500, pulse_width=1, sync_out_width=200, output_voltage_set=0.0,
                          output_current_limit=0.1, pulsing_mode=S2_PULSING_OFF, bias_t=0,
                          pulse_period_prescaler=1, pulse_width_prescaler=1, burst_ON=0, burst_OFF=0,
                          reserved_1=0, reserved_2=0, reserved_3=0, reserved_4=0)


class S2AdvancedSettings(S2Payload):
    __slots__ = ('output_voltage_set_raw', 'DCDC_period', 'DCDC_mode')
    _STRUCT = struct.Struct('<ihb')


class S2AdvancedInfo(S2Payload):
    __slots__ = ('input_voltage_measured_raw', 'output_voltage_measured_raw', 'output_current_measured_raw',
                 'current_out_of_pulse_raw')
    _STRUCT = struct.Struct('<ffff')


class S2ResetStatus(S2Payload):
    __slots__ = 'status_flag',
    _STRUCT = struct.Struct('<H')


class S2Calibration(S2Payload):
    __slots__ = ('board_version', 'I_a', 'I_b', 'Vout_meas_a', 'Vout_meas_b', 'Vout_set_a', 'Vout_set_b',
                 'hardware_options', 'max_peak_current')
    _STRUCT = struct.Struct('<IffffffBf')


_info_query_packet = create_packet(S2_PACKET_INFO)
_settings_query_packet = create_packet(S2_PACKET_QUERY_SETTINGS)
_calibration_query_packet = create_packet(S2_PACKET_QUERY_CALIBRATION)
_reset_overcurrent_packet = create_packet(S2_PACKET_RESET_STATUS_FLAG, S2ResetStatus(S2_STATUS_OVERCURRENT))


class S2(S2Base):
    """Driver to control the S2 with a serial transport handler"""

    PULSING_MODES_LABELS = {S2_PULSING_OFF: 'off',
                            S2_PULSING_INTERNAL: 'internal',
                            S2_PULSING_MODE_A: 'modeA',
                            S2_PULSING_MODE_B: 'modeB',
                            S2_PULSING_BURST: 'burst_mode',
                            S2_PULSING_BURST_EXTERNAL: 'burst_external',
                            S2_PULSING_EXTERNAL: 'external'
                            }

    PULSING_MODES = {v: k for k, v in PULSING_MODES_LABELS.items()}
    PULSING_MODES.update(modeC=S2_PULSING_BURST)

    STATUS_LABELS = {S2_STATUS_OK: 'ok',
                     S2_STATUS_OVERCURRENT: 'overcurrent',
                     S2_STATUS_UNDERVOLTAGE: 'undervoltage'}

    @property
    def settings(self):
        """:rtype: S2Settings"""
        return self._settings

    @property
    def info(self):
        """:rtype: S2Info"""
        return self._info

    @property
    def calibration(self):
        return self._calibration

    @property
    def pulsing_mode_label(self):
        if self._in_mode_C:
            return 'modeC'
        return self.PULSING_MODES_LABELS.get(self._settings.pulsing_mode, 'unknown pulsing mode')

    @property
    def available_pulsing_modes(self):
        spec_modes = (self._calibration.hardware_options & S2_OPTION_SPECIAL_BURST_MODES) != 0
        modes = set(self.PULSING_MODES.keys())
        if not spec_modes:
            modes -= {self.PULSING_MODES_LABELS[S2_PULSING_MODE_A], self.PULSING_MODES_LABELS[S2_PULSING_MODE_B]}
        return [y for y in sorted(modes, key=lambda x: self.PULSING_MODES[x])]

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self._info.status, 'unknown status')

    @property
    def is_overcurrent(self):
        return self._info.status == S2_STATUS_OVERCURRENT

    @property
    def is_undervoltage(self):
        return self._info.status == S2_STATUS_UNDERVOLTAGE

    @property
    def measured_current(self):
        return self._info.output_current_measured

    @property
    def measured_voltage(self):
        return self._info.output_voltage_measured

    @property
    def device_id(self):
        return self._info.device_id

    @property
    def sw_version(self):
        return self._info.sw_version

    @property
    def hw_version(self):
        return self._info.hw_version

    @property
    def pulse_width_min(self):
        return self._pulse_width_min

    @property
    def pulse_width_max(self):
        return self._pulse_width_max

    @property
    def pulse_period_min(self):
        return self._pulse_period_min

    @property
    def pulse_period_max(self):
        return self._pulse_period_max

    @property
    def min_pulse_width_meas(self):
        return 200.0

    @property
    def step_ns(self):
        return 1e9 / self._info.pulse_clock_frequency

    @property
    def voltage_min(self):
        return self._min_voltage

    @property
    def voltage_max(self):
        return self._max_voltage

    @property
    def pulse_period(self):
        return self._settings.pulse_period * self._settings.pulse_period_prescaler * self.step_ns

    @property
    def pulse_width(self):
        return self._settings.pulse_width * self._settings.pulse_width_prescaler * self.step_ns

    @property
    def duty_cycle(self):
        return float(self.pulse_width) / float(self.pulse_period)

    @property
    def applied_voltage(self):
        return self._settings.output_voltage_set

    @property
    def current_limit(self):
        return self._settings.output_current_limit

    @property
    def max_peak_current(self):
        return self._calibration.max_peak_current

    @property
    def last_info_time(self):
        return self._last_info_time

    @property
    def set_settings_time(self):
        return self._set_settings_time

    def __init__(self, th):
        super(S2, self).__init__(th)
        self._settings = S2Settings.default()
        self._info = S2Info()
        self._calibration = S2Calibration()
        self._last_info_time = 0
        self._set_settings_time = 0
        self._min_voltage = 0
        self._max_voltage = 25
        self._pulse_period_min = 200
        self._pulse_period_max = 1310700
        self._pulse_width_min = 20
        self._pulse_width_max = 1310700
        self._max_API_version = 2016091301
        self._in_mode_C = False

    def set_up(self):
        with self._lock:
            self._ignore_comm_count = True
            self._num_commands_failed = 0
            self._num_commands_sent = 0
            try:
                self.reload_info()
            finally:
                self._ignore_comm_count = False
            if self._info.hw_version != 4:
                raise Exception('S2 hardware version {} not supported by this '
                                'gen 4 driver'.format(self._info.hw_version))
            api_version = self._info.API_version
            if api_version > self._max_API_version:
                raise Exception('S2 firmware too recent ({}). Please update this program [S2 #{}]'.format(
                    self._info.API_version, self._info.device_id))
            if api_version < 2016091301:
                logger.info('[S2 #{}] no option to remove internal current limit'.format(self.device_id))
            if api_version < 2016083001:
                logger.info('[S2 #{}] burst external mode not available'.format(self.device_id))
            # if api_version < 2016072001:
            #     raise Exception('S2 firmware too old ({}). Please update the S2 #{}'.format(
            #         self._info.API_version, self._info.device_id))
            self.reload_settings()
            self._query_packet(_calibration_query_packet, self._calibration)

    def shut_down(self):
        """Shuts down, stops s2 output"""
        with self._lock:
            if self.comm_failure_rate_percent > 5:
                logger.warning('High comm error rate [{:.1f}%] with S2 #{}'.format(self.comm_failure_rate_percent,
                                                                                   self.device_id))
            else:
                logger.debug('Error rate [{:.1f}%] S2 #{}'.format(self.comm_failure_rate_percent, self.device_id))
            self.set_settings(pulsing_mode='off')

    def reload_info(self):
        self._query_packet(_info_query_packet, self._info)
        self._info.pulse_clock_frequency = 50000000  # NB not implemented on older firmware versions
        self._last_info_time = time.time()

    def reload_settings(self):
        self._query_packet(_settings_query_packet, self._settings)
        self._in_mode_C = self._is_probably_mode_C()

    def apply_current_settings(self):
        logger.debug('Applying {}'.format(self._settings))
        if (self._calibration.hardware_options & S2_OPTION_SPECIAL_BURST_MODES) == 0:
            if self._settings.pulsing_mode in (S2_PULSING_MODE_A, S2_PULSING_MODE_B):
                raise ValueError('Special burst modes not enabled')
        if (self._calibration.hardware_options & S2_OPTION_ALT_EXT_INPUT) == 0:
            if self._settings.pulsing_mode == S2_PULSING_BURST_EXTERNAL:
                raise ValueError('Burst external mode not enabled on this board')
        packet = create_packet(S2_PACKET_SET_SETTINGS, self._settings)
        self._query_packet(packet, self._settings)
        self._set_settings_time = time.time()

    def reset_overcurrent_flag(self):
        self._query_packet(_reset_overcurrent_packet)

    def set_settings(self, pulsing_mode=None, voltage=None, pulse_period=None, pulse_width=None, current_limit=None):
        """Set the specified settings. The unspecified parameters (=None) are not changed. Ramps up or down slowly the
        applied voltage"""
        with self._lock:
            was_off = self._settings.pulsing_mode == S2_PULSING_OFF
            previous_voltage = self._settings.output_voltage_set if not was_off else 0.0
            if pulsing_mode is None:
                pulsing_mode = self._settings.pulsing_mode
            elif pulsing_mode in self.PULSING_MODES:
                self._in_mode_C = pulsing_mode == 'modeC'
                pulsing_mode = self.PULSING_MODES[pulsing_mode]
            if pulsing_mode not in self.PULSING_MODES_LABELS:
                raise S2InvalidPulseParamsError('Unknown pulsing mode "{}"'.format(pulsing_mode))

            if voltage is not None:
                if not self._min_voltage <= voltage <= self._max_voltage:
                    raise S2InvalidVoltageError('Voltage {} out of bounds ({}, {})'.format(voltage,
                                                                                           self._min_voltage,
                                                                                           self._max_voltage))
                self._settings.output_voltage_set = voltage
            if pulse_period is not None:
                if not self._pulse_period_min <= pulse_period <= self._pulse_period_max:
                    raise S2InvalidPulseParamsError('Pulse period {} out of bounds ({}, {})'.
                                                    format(pulse_period,
                                                           self._pulse_period_min, self._pulse_period_max))
                self._settings.pulse_period = int(1e-9 * pulse_period * self._info.pulse_clock_frequency)
            if pulse_width is not None:
                if not self._pulse_width_min <= pulse_width <= self._pulse_width_max:
                    raise S2InvalidPulseParamsError('Pulse width {} out of bounds ({}, {})'.
                                                    format(pulse_width,
                                                           self._pulse_width_min, self._pulse_width_max))
                self._settings.pulse_width = int(1e-9 * pulse_width * self._info.pulse_clock_frequency)
            if current_limit is not None:
                self._settings.output_current_limit = current_limit

            if self._in_mode_C:
                self._settings.burst_ON, self._settings.burst_OFF = self._mode_C_timings()

            # Ramping of the voltage.
            # shut_down = pulsing_mode == S2_PULSING_OFF
            # target_voltage = self._settings.output_voltage_set if not shut_down else 0.0
            # applied_voltage = previous_voltage
            # if was_off:
            #     self._settings.pulsing_mode = pulsing_mode
            #
            # while abs(applied_voltage - target_voltage) > self.max_voltage_step:
            #     applied_voltage += math.copysign(self.max_voltage_step, target_voltage - applied_voltage)
            #     self._settings.output_voltage_set = applied_voltage
            #     self.apply_current_settings()
            #     time.sleep(self.max_voltage_step / self.voltage_ramp_speed)
            #
            # # Final set
            # self._settings.output_voltage_set = target_voltage
            self._settings.pulsing_mode = pulsing_mode

            self.apply_current_settings()

            return self._settings

    def get_measure(self, immediate=False):
        """Returns a tuple (current, voltage). Raises an exception if the S2 status is overcurrent or undervoltage.

        :param immediate: If False (default), the method waits until the signal is stabilized by waiting 0.5s
         since the last set_settings call. If True, performs the measurement immediately, regardless of the time of the
         last set_settings call."""
        delta = time.time() - self._set_settings_time - 0.5
        if delta < 0 and not immediate:
            time.sleep(-delta)
        self.reload_info()
        if self._info.status == S2_STATUS_UNDERVOLTAGE:
            raise S2UndervoltageError()
        if self._info.status == S2_STATUS_OVERCURRENT:
            raise S2OvercurrentError()

        return self._info.output_current_measured, self._info.output_voltage_measured

    def _is_probably_mode_C(self):
        if self.pulsing_mode_label != 'modeC':
            return False
        burst_ON, burst_OFF = self._mode_C_timings()
        return burst_OFF == self._settings.burst_OFF and burst_ON == self._settings.burst_ON

    def _mode_C_timings(self):
        burst_ON = (5 * self._info.pulse_clock_frequency) // (1000 * self._settings.pulse_width)
        burst_OFF = (25 * self._info.pulse_clock_frequency) // (1000 * self._settings.pulse_width)
        return burst_ON, burst_OFF


if __name__ == '__main__':
    import serial
    from sdeux.serial_handler import S2SerialHandler
    th = S2SerialHandler('/dev/ttyUSB0')
    th.open()
    s2 = S2(th)
    s2.set_up()
    #s2.settings.burst_ON = 50
    #s2.settings.burst_OFF = 450
    s2.set_settings('internal', 5, 2000, 2000)