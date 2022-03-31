# -*- coding: utf-8 -*-
"""
Created by gregory on 14.02.18

Copyright 2018 Alpes Lasers SA, Neuchatel, Switzerland
"""
import time
import threading
import struct
import logging

from sdeux.communication import S2Payload, create_packet, S2Base
from sdeux.defs import (S2_PULSING_OFF, S2_PACKET_INFO, S2_PACKET_SET_SETTINGS,
                        S2_PACKET_SET_PERSISTENT_SETTINGS,
                        S2_PACKET_QUERY_SETTINGS, S2_PACKET_UPTIME, S2_PACKET_RESET_STATUS_FLAG,
                        S2_PACKET_QUERY_CALIBRATION, S2_PACKET_SET_ADVANCED_SETTINGS, S2_STATUS_OVERCURRENT,
                        S2_PULSING_INTERNAL, S2_PULSING_MODE_A, S2_PULSING_MODE_B,
                        S2_PULSING_BURST, S2_PULSING_FULL_EXTERNAL, S2_PULSING_BURST_EXTERNAL_TRIGGER,
                        S2_PULSING_EXTERNAL_TRIGGER, S2_STATUS_OK, S2_STATUS_UNDERVOLTAGE,
                        S2_OPTION_SPECIAL_BURST_MODES, S2_PACKET_STORE_CALIBRATION,
                        S2_PACKET_SET_CALIBRATION, S2_PULSING_MODE_B4, S2_PULSING_MODE_B6,
                        S2_PULSING_MODE_B8, S2_PULSING_MODE_CSS, S2_PULSING_MODE_CST, S2_PACKET_BOOTLOADER,
                        S2_PACKET_ADVANCED_INFO)
from sdeux.exceptions import (S2UndervoltageError, S2OvercurrentError, S2InvalidVoltageError,
                              S2InvalidPulseParamsError)

logger = logging.getLogger(__name__)

__author__ = 'gregory'
__copyright__ = "Copyright 2018, Alpes Lasers SA"


class S2Info(S2Payload):
    __slots__ = ('device_id', 'sw_version', 'hw_version', 'input_voltage_measured', 'output_voltage_measured',
                 'output_current_measured', 'MCU_temperature', 'laser_temperature',
                 'output_current_measured_out_of_pulse', 'status', 'pulse_clock_frequency', 'API_version',
                 'aux_input_measured')
    _STRUCT = struct.Struct('<IHHffffffHIIf')


class S2AdvancedInfo(S2Payload):
    __slots__ = ('input_voltage_measured_raw', 'output_voltage_measured_raw', 'output_current_measured_raw',
                 'current_out_of_pulse_raw')
    _STRUCT = struct.Struct('<ffff')


class S2Settings(S2Payload):
    __slots__ = ('pulse_period', 'pulse_width', 'sync_out_width', 'output_voltage_set', 'output_current_limit',
                 'pulsing_mode', 'bias_t', 'burst_ON', 'burst_OFF', 'aux_output')
    _STRUCT = struct.Struct('<IIIffHfIIf')

    @classmethod
    def default(cls):
        """

        :return S2Settings:
        """
        return S2Settings(pulse_period=500, pulse_width=1,
                          sync_out_width=800, output_voltage_set=1.0,
                          aux_output=0,
                          output_current_limit=0.1,
                          pulsing_mode=S2_PULSING_OFF,
                          bias_t=0, burst_ON=0, burst_OFF=0)


class S2AdvancedSettings(S2Payload):
    __slots__ = ('output_voltage_set_raw', 'DCDC_period', 'DCDC_mode', 'flag_reset_uptime')
    _STRUCT = struct.Struct('<ihbI')

    @classmethod
    def reset_uptime(cls):
        return S2AdvancedSettings(output_voltage_set_raw=0, DCDC_period=-1, DCDC_mode=-1, flag_reset_uptime=0xAA00BCD0)

    @classmethod
    def default(cls):
        return S2AdvancedSettings(output_voltage_set_raw=0,
                                  DCDC_period=250,
                                  DCDC_mode=1, flag_reset_uptime=0)


class S2Uptime(S2Payload):
    __slots__ = 'uptime', 'total_uptime'
    _STRUCT = struct.Struct('<QQ')


class S2ResetStatus(S2Payload):
    __slots__ = 'status_flag',
    _STRUCT = struct.Struct('<H')


class S2Calibration(S2Payload):
    __slots__ = ('board_version', 'I_a', 'I_b', 'Vout_meas_a', 'Vout_meas_b', 'Vout_set_a', 'Vout_set_b',
                 'hardware_options', 'max_peak_current')
    _STRUCT = struct.Struct('<IffffffBf')


_packet_type_to_payload = {S2_PACKET_INFO: S2Info,
                           S2_PACKET_ADVANCED_INFO: S2AdvancedInfo,
                           S2_PACKET_SET_SETTINGS: S2Settings,
                           S2_PACKET_SET_PERSISTENT_SETTINGS: S2Settings,
                           S2_PACKET_QUERY_SETTINGS: S2Settings,
                           S2_PACKET_UPTIME: S2Uptime,
                           S2_PACKET_RESET_STATUS_FLAG: S2ResetStatus,
                           S2_PACKET_QUERY_CALIBRATION: S2Calibration,
                           S2_PACKET_STORE_CALIBRATION: S2Calibration,
                           S2_PACKET_SET_CALIBRATION: S2Calibration,
                           S2_PACKET_SET_ADVANCED_SETTINGS: S2AdvancedSettings}


_info_query_packet = create_packet(S2_PACKET_INFO)
_info_advanced_info = create_packet(S2_PACKET_ADVANCED_INFO)
_info_advanced_settings = create_packet(S2_PACKET_ADVANCED_INFO)
_settings_query_packet = create_packet(S2_PACKET_QUERY_SETTINGS)
_calibration_query_packet = create_packet(S2_PACKET_QUERY_CALIBRATION)
_uptime_query_packet = create_packet(S2_PACKET_UPTIME)
_reset_overcurrent_packet = create_packet(S2_PACKET_RESET_STATUS_FLAG, S2ResetStatus(S2_STATUS_OVERCURRENT))
_reset_uptime_packet = create_packet(S2_PACKET_SET_ADVANCED_SETTINGS, S2AdvancedSettings.reset_uptime())
_bootloader_packet = create_packet(S2_PACKET_BOOTLOADER)


class S2(S2Base):
    """Driver to control the S2 with a serial transport handler"""

    PULSING_MODES_LABELS = {S2_PULSING_OFF: 'off',
                            S2_PULSING_INTERNAL: 'internal',
                            S2_PULSING_MODE_A: 'modeA',
                            S2_PULSING_MODE_B: 'modeB',
                            S2_PULSING_MODE_B4: 'modeB4',
                            S2_PULSING_MODE_B6: 'modeB6',
                            S2_PULSING_MODE_B8: 'modeB8',
                            S2_PULSING_MODE_CSS: 'modeCSS',
                            S2_PULSING_MODE_CST: 'modeCST',
                            S2_PULSING_BURST: 'burst_mode',
                            S2_PULSING_FULL_EXTERNAL: 'full_external',
                            S2_PULSING_BURST_EXTERNAL_TRIGGER: 'burst_mode_external_trigger',
                            S2_PULSING_EXTERNAL_TRIGGER: 'external_trigger'}

    PULSING_MODES = {v: k for k, v in PULSING_MODES_LABELS.items()}

    STATUS_LABELS = {S2_STATUS_OK: 'ok',
                     S2_STATUS_OVERCURRENT: 'overcurrent',
                     S2_STATUS_UNDERVOLTAGE: 'undervoltage'}
    
    @property
    def pulsing_mode(self):
        return self._settings.pulsing_mode

    @property
    def settings(self):
        return self._settings

    @property
    def info(self):
        return self._info

    @property
    def calibration(self):
        return self._calibration

    @property
    def pulsing_mode_label(self):
        return self.PULSING_MODES_LABELS.get(self._settings.pulsing_mode, 'unknown pulsing mode')

    @property
    def available_pulsing_modes(self):
        spec_modes = (self._calibration.hardware_options & S2_OPTION_SPECIAL_BURST_MODES) != 0
        modes = set(self.PULSING_MODES.keys())
        # if not spec_modes:
        #     modes -= {self.PULSING_MODES_LABELS[S2_PULSING_MODE_A], self.PULSING_MODES_LABELS[S2_PULSING_MODE_B]}
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
        if self._info.pulse_clock_frequency:
            return 1e9 / self._info.pulse_clock_frequency

    @property
    def voltage_min(self):
        return self._min_voltage

    @property
    def voltage_max(self):
        return self._max_voltage

    @property
    def pulse_period(self):
        if self.step_ns is not None:
            return self._settings.pulse_period * self.step_ns

    @property
    def pulse_width(self):
        if self.step_ns is not None:
            return self._settings.pulse_width * self.step_ns

    @property
    def duty_cycle(self):
        return float(self._settings.pulse_width) / float(self._settings.pulse_period)

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

    @property
    def input_voltage_measured_raw(self):
        return self._advancedInfo.input_voltage_measured_raw

    @property
    def output_voltage_measured_raw(self):
        return self._advancedInfo.output_voltage_measured_raw

    @property
    def output_current_measured_raw(self):
        return self._advancedInfo.output_current_measured_raw

    @property
    def current_out_of_pulse_raw(self):
        return self._advancedInfo.current_out_of_pulse_raw

    @property
    def input_voltage_measured(self):
        return self._info.input_voltage_measured

    @property
    def meta_info(self):
        d = super(S2, self).meta_info
        d['settings']['pulsing_mode']['burst_mode'] = {'burst_ON': {'units': 'a.u.'},
                                                       'burst_OFF': {'units': 'a.u.'}}
        return d

    def __init__(self, th):
        super(S2, self).__init__(th)

        self._settings = S2Settings.default()
        self._advancedSettings = S2AdvancedSettings.default()
        self._info = S2Info()
        self._advancedInfo = S2AdvancedInfo()
        self._uptime = S2Uptime()
        self._calibration = S2Calibration()
        self._lock = threading.RLock()
        self._last_info_time = 0
        self._set_settings_time = 0
        self._num_commands_sent = 0
        self._num_commands_failed = 0
        self._ignore_comm_count = False
        self._min_voltage = 0
        self._max_voltage = 25
        self._pulse_period_min = 500
        self._pulse_period_max = 42949672950
        self._pulse_width_min = 10
        self._pulse_width_max = 42949672950
        self._max_API_version = 2017102401

    def set_up(self):
        """Sets up, clears potential overcurrent flags."""
        with self._lock:
            self._ignore_comm_count = True
            self._num_commands_failed = 0
            self._num_commands_sent = 0
            try:
                self.reload_info()
                if self.step_ns != 10:
                    raise Exception(
                        'Step size sanity check failed (reports: {} instead of {})'.format(self.step_ns, 10))
            finally:
                self._ignore_comm_count = False
            if self._info.hw_version != 5:
                raise Exception('S2 hardware version {} not supported by this '
                                'gen 5 driver'.format(self._info.hw_version))
            api_version = self._info.API_version
            if api_version > self._max_API_version:
                raise Exception('S2 firmware too recent ({}). Please update this program [S2 #{}]'.format(
                    self._info.API_version, self._info.device_id))
            if api_version < 2017102401:
                logger.info('[S2 #{}] Uptime information not available'.format(self.device_id))
            if api_version < 2017083101:
                logger.info('[S2 #{}] Aux input/output not available'.format(self.device_id))
            if api_version < 2017081701:
                raise Exception('S2 firmware too old ({}). Please update the S2 #{}'.format(
                    self._info.API_version, self._info.device_id))
            if self._info.sw_version < 2146:
                logger.warning('S2 #{} firmware version {} is older than 2146 and has faulty communications.'
                               ' It is strongly advised to update it!'.format(self.device_id, self.sw_version))
            self.reload_settings()
            self._query_packet(_calibration_query_packet, self._calibration, expected_header=S2_PACKET_QUERY_CALIBRATION,
                           expected_response_time=5.0)

    def shut_down(self):
        """Shuts down, stops s2 output"""
        with self._lock:
            if self.comm_failure_rate_percent > 5:
                logger.warning('High comm error rate [{:.1f}%] with S2 #{}'.format(self.comm_failure_rate_percent,
                                                                                   self.device_id))
            else:
                logger.debug('Error rate [{:.1f}%] S2 #{}'.format(self.comm_failure_rate_percent, self.device_id))
            self.set_settings(pulsing_mode='off')

    def reload_calibration(self):
        self._query_packet(_calibration_query_packet, self._calibration, expected_header=S2_PACKET_QUERY_CALIBRATION,
                           expected_response_time=5.0)

    def reload_info(self):
        self._query_packet(_info_query_packet, self._info, expected_header=S2_PACKET_INFO,
                           expected_response_time=5.0)
        self._last_info_time = time.time()

    def reload_settings(self):
        self._query_packet(_settings_query_packet, self._settings,  expected_header=S2_PACKET_QUERY_SETTINGS,
                           expected_response_time=5.0)

    def reload_advanced_info(self):
        self._query_packet(_info_advanced_info, self._advancedInfo, expected_response_time=5.0)

    def apply_current_settings(self):
        logger.debug('Applying {}'.format(self._settings))
        # if (self._calibration.hardware_options & S2_OPTION_SPECIAL_BURST_MODES) == 0:
        #     if self._settings.pulsing_mode in (S2_PULSING_MODE_A, S2_PULSING_MODE_B):
        #         self.reload_settings()
        #         raise ValueError('Special burst modes not enabled')
        packet = create_packet(S2_PACKET_SET_SETTINGS, self._settings)
        self._query_packet(packet, self._settings, expected_header=S2_PACKET_QUERY_SETTINGS,
                           expected_response_time=10.0)
        self._set_settings_time = time.time()

    def reset_overcurrent_flag(self):
        self._query_packet(_reset_overcurrent_packet, expected_response_time=5.0)

    def reset_uptime_counters(self):
        self._query_packet(_reset_uptime_packet, expected_response_time=5.0)

    def set_settings(self, pulsing_mode=None, voltage=None,
                     pulse_period=None, pulse_width=None, current_limit=None,
                     burst_ON=None, burst_OFF=None):
        """Set the specified settings. The unspecified parameters (=None) are not changed. Ramps up or down slowly the
        applied voltage"""
        with self._lock:
            was_off = self._settings.pulsing_mode == S2_PULSING_OFF
            previous_voltage = self._settings.output_voltage_set if not was_off else 0.0
            if pulsing_mode is None:
                pulsing_mode = self._settings.pulsing_mode
            elif pulsing_mode in self.PULSING_MODES:
                pulsing_mode = self.PULSING_MODES[pulsing_mode]
            if pulsing_mode not in self.PULSING_MODES_LABELS:
                raise S2InvalidPulseParamsError('Unknown pulsing mode "{}"'.format(pulsing_mode))

            if pulsing_mode == S2_PULSING_BURST:
                if burst_ON is not None:
                    self._settings.burst_ON = burst_ON
                if burst_OFF is not None:
                    self._settings.burst_OFF = burst_OFF

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

    def get_uptime(self):
        return self._query_packet(_uptime_query_packet, self._uptime, expected_response_time=1.0)

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

    def set_advanced_settings(self, DCDC_period=None,
                              DCDC_mode=None,
                              output_voltage_set_raw=None):
        self.check_advanced_mode()
        if DCDC_period is not None:
            self._advancedSettings.DCDC_period = DCDC_period
        if DCDC_mode is not None:
            self._advancedSettings.DCDC_mode = DCDC_mode
        if output_voltage_set_raw is not None:
            self._advancedSettings.output_voltage_set_raw = output_voltage_set_raw
        packet = create_packet(S2_PACKET_SET_ADVANCED_SETTINGS, self._advancedSettings)
        return self._query_packet(packet, self._advancedSettings)

    def apply_calibration(self, calibration, store=False):
        self.check_advanced_mode()
        if store:
            packet = create_packet(S2_PACKET_STORE_CALIBRATION, calibration)
        else:
            packet = create_packet(S2_PACKET_SET_CALIBRATION, calibration)
        return self._query_packet(packet, self._calibration, expected_header=S2_PACKET_QUERY_CALIBRATION,
                                  expected_response_time=5.0)

    def reboot_to_bootloader(self):
        self.check_advanced_mode()
        return self._query_packet(_bootloader_packet)


