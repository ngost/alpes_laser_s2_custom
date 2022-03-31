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
from sdeux.defs import (S2_CURR_LIMIT_MODE_GLOBAL, S2_PACKET_QUERY_CONFIGURATION, S2_CURR_LIMIT_MODE_STORED, S2_PULSING_OFF, S2_PACKET_INFO, S2_PACKET_SET_SETTINGS,
                        S2_PACKET_SET_PERSISTENT_SETTINGS, S2_PACKET_SET_FAST_PRESET, S2_PACKET_DEBUG_INFO,
                        S2_PACKET_QUERY_SETTINGS, S2_PACKET_UPTIME, S2_PACKET_RESET_STATUS_FLAG,
                        S2_PACKET_QUERY_CALIBRATION, S2_PACKET_SET_ADVANCED_SETTINGS, S2_STATUS_OVERCURRENT,
                        S2_PULSING_INTERNAL, S2_PULSING_MODE_A, S2_PULSING_MODE_B,
                        S2_PULSING_BURST, S2_STATUS_OK,
                        S2_STATUS_UNDERVOLTAGE, S2_PULSING_MODE_AB,
                        S2_PACKET_SET_CALIBRATION, S2_PACKET_STORE_CALIBRATION, S2_PACKET_SET_CONFIGURATION,
                        S2_PACKET_BOOTLOADER, S2_PACKET_QUERY_BIT, S2_PULSING_MODE_CSS, S2_PULSING_MODE_CST,
                        S2_PULSING_INTERNAL_FAST,
                        S2_STATUS_OVERVOLTAGE, S2_STATUS_OVERTEMP, S2_PACKET_ADVANCED_INFO)
from sdeux.exceptions import (S2UndervoltageError, S2OvercurrentError, S2InvalidVoltageError,
                              S2InvalidPulseParamsError)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

__author__ = 'gregory'
__copyright__ = "Copyright 2018, Alpes Lasers SA"


class S2Info(S2Payload):
    __slots__ = ('device_id', 'sw_version', 'hw_version', 'input_voltage_measured', 'output_voltage_measured',
                 'output_current_measured', 'MCU_temperature', 'laser_temperature',
                 'output_current_measured_out_of_pulse', 'status', 'pulse_clock_frequency', 'API_version',
                 'laser_id')
    _STRUCT = struct.Struct('<IHHffffffHII8s')


class S2Debug(S2Payload):
    __slots__ = 'output',
    _STRUCT = struct.Struct('<60s')


class S2AdvancedInfo(S2Payload):
    __slots__ = ('input_voltage_measured_raw', 'output_voltage_measured_raw',
                 'output_current_measured_raw',
                 'current_out_of_pulse_raw')
    _STRUCT = struct.Struct('<ffff')


class S2Settings(S2Payload):
    __slots__ = ('pulse_period', 'pulse_width', 'output_voltage_set', 'output_current_limit',
                 'pulsing_mode', 'bias_t', 'burst_ON', 'burst_OFF', 'output_voltage_set_A', 'output_voltage_set_B',
                 'pulse_width_A', 'pulse_width_B', 'current_limit_mode')
    _STRUCT = struct.Struct('<IIffHfIIffIIH')

    @classmethod
    def default(cls):
        """

        :return S2Settings:
        """
        return S2Settings(pulse_period=500, pulse_width=1, output_voltage_set=1.0,
                          output_current_limit=0.1, pulsing_mode=S2_PULSING_OFF, bias_t=0, burst_ON=0, burst_OFF=0,
                          output_voltage_set_A=0, output_voltage_set_B=0, pulse_width_A=0, pulse_width_B=0,
                          current_limit_mode=S2_CURR_LIMIT_MODE_GLOBAL)


class S2AdvancedSettings(S2Payload):
    __slots__ = ('output_voltage_set_raw',
                 'DCDC_period', 'DCDC_mode',
                 'flag_reset_uptime')
    _STRUCT = struct.Struct('<ihbI')

    @classmethod
    def reset_uptime(cls):
        return S2AdvancedSettings(output_voltage_set_raw=0, DCDC_period=-1, DCDC_mode=-1, flag_reset_uptime=0xAA00BCD0)

    @classmethod
    def default(cls):
        return S2AdvancedSettings(DCDC_mode=-1, DCDC_period=0,
                                  output_voltage_set_raw=0,
                                  flag_reset_uptime=0)


class S2Uptime(S2Payload):
    __slots__ = 'uptime', 'total_uptime', 'lasing_time', 'operation_time'
    _STRUCT = struct.Struct('<QQQQ')


class S2ResetStatus(S2Payload):
    __slots__ = 'status_flag',
    _STRUCT = struct.Struct('<H')


class S2Calibration(S2Payload):
    __slots__ = ('board_version', 'I_a', 'I_b', 'Vout_meas_a', 'Vout_meas_b', 'Vout_set_a', 'Vout_set_b',
                 'hardware_options', 'max_peak_current')
    _STRUCT = struct.Struct('<IffffffBf')


class S2Configuration(S2Payload):
    __slots__ = ('device_id', 'laser_id', 'mode_auto_duty_limit_low', 'mode_auto_duty_limit_high', 'mode_auto_high_secur_delay', 'lasing_min_current',
                 'internal_limit', 'modea_limit', 'modeb_limit', 'modecst_limit', 'modecss_limit', 'modeab_a_limit',
                 'modeab_b_limit', 'integr_t_auto')
    _STRUCT = struct.Struct('<I8sffIffffffffI')


    @classmethod
    def default(cls):
        return S2Configuration(device_id=0, laser_id=b'', mode_auto_duty_limit_low=0.15, mode_auto_duty_limit_high=0.1, mode_auto_high_secur_delay= 1000000,
                               lasing_min_current=0, internal_limit=0, modea_limit=0, modeb_limit=0, modecst_limit=0,
                               modecss_limit=0, modeab_a_limit=0, modeab_b_limit=0, integr_t_auto=1000000 )


class S2FastPresets(S2Payload):
    __slots__ = ('preset_number', 'pulse_period', 'pulse_width')
    _STRUCT = struct.Struct('<bII')


class S2BIT(S2Payload):
    __slots__ = ('overcurrent_first', 'overcurrent_last', 'overcurrent_count', 'undervoltage_first',
                 'undervoltage_last', 'undervoltage_count', 'overvoltage_first', 'overvoltage_last',
                 'overvoltage_count', 'overtemp_first', 'overtemp_last', 'overtemp_count')
    _STRUCT = struct.Struct('<IIIIIIIIIIII')


_packet_type_to_payload = {S2_PACKET_INFO: S2Info,
                           S2_PACKET_ADVANCED_INFO: S2AdvancedInfo,
                           S2_PACKET_SET_SETTINGS: S2Settings,
                           S2_PACKET_SET_PERSISTENT_SETTINGS: S2Settings,
                           S2_PACKET_QUERY_SETTINGS: S2Settings,
                           S2_PACKET_UPTIME: S2Uptime,
                           S2_PACKET_RESET_STATUS_FLAG: S2ResetStatus,
                           S2_PACKET_QUERY_CALIBRATION: S2Calibration,
                           S2_PACKET_SET_ADVANCED_SETTINGS: S2AdvancedSettings,
                           S2_PACKET_SET_CONFIGURATION: S2Configuration,
                           S2_PACKET_QUERY_CONFIGURATION: S2Configuration,
                           S2_PACKET_SET_FAST_PRESET:S2FastPresets,
                           S2_PACKET_DEBUG_INFO:S2Debug,
                           S2_PACKET_QUERY_BIT: S2BIT}

_info_query_packet = create_packet(S2_PACKET_INFO)
_info_advanced_settings = create_packet(S2_PACKET_ADVANCED_INFO)
_info_advanced_info = create_packet(S2_PACKET_ADVANCED_INFO)
_settings_query_packet = create_packet(S2_PACKET_QUERY_SETTINGS)
_calibration_query_packet = create_packet(S2_PACKET_QUERY_CALIBRATION)
_configuration_query_packet = create_packet(S2_PACKET_QUERY_CONFIGURATION)
_uptime_query_packet = create_packet(S2_PACKET_UPTIME)
_reset_overcurrent_packet = create_packet(S2_PACKET_RESET_STATUS_FLAG, S2ResetStatus(S2_STATUS_OVERCURRENT))
_reset_undervoltage_packet = create_packet(S2_PACKET_RESET_STATUS_FLAG, S2ResetStatus(S2_STATUS_UNDERVOLTAGE))
_reset_overtemp_packet = create_packet(S2_PACKET_RESET_STATUS_FLAG, S2ResetStatus(S2_STATUS_OVERTEMP))
_reset_overvoltage_packet = create_packet(S2_PACKET_RESET_STATUS_FLAG, S2ResetStatus(S2_STATUS_OVERVOLTAGE))
_reset_uptime_packet = create_packet(S2_PACKET_SET_ADVANCED_SETTINGS, S2AdvancedSettings.reset_uptime())
_bootloader_packet = create_packet(S2_PACKET_BOOTLOADER)
_bit_stats_query_packet = create_packet(S2_PACKET_QUERY_BIT)
_debug_query_packet = create_packet(S2_PACKET_DEBUG_INFO)


class S2(S2Base):
    """Driver to control the S2 with a serial transport handler"""

    PULSING_MODES_LABELS = {S2_PULSING_OFF: 'off',
                            S2_PULSING_INTERNAL: 'internal',
                            S2_PULSING_MODE_A: 'modeA',
                            S2_PULSING_MODE_B: 'modeB',
                            S2_PULSING_BURST: 'burst_mode',
                            S2_PULSING_MODE_AB: 'modeAB',
                            S2_PULSING_MODE_CSS: 'modeCSS',
                            S2_PULSING_MODE_CST: 'modeCST',
                            S2_PULSING_INTERNAL_FAST: 'internal_fast'
                            }

    PULSING_MODES = {v: k for k, v in PULSING_MODES_LABELS.items()}

    STATUS_LABELS = {S2_STATUS_OK: 'ok',
                     S2_STATUS_OVERCURRENT: 'overcurrent',
                     S2_STATUS_UNDERVOLTAGE: 'undervoltage',
                     S2_STATUS_OVERVOLTAGE: 'overvoltage',
                     S2_STATUS_OVERTEMP: 'overtemp'}

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
    def configuration(self):
        return self._configuration

    @property
    def bit_stats(self):
        return self._bit_stats

    @property
    def pulsing_mode_label(self):
        return self.PULSING_MODES_LABELS.get(self._settings.pulsing_mode, 'unknown pulsing mode')

    @property
    def available_pulsing_modes(self):
        return self._available_pulsing_modes

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
    def output_voltage_measured_raw(self):
        return self._advancedSettings.output_voltage_set_raw

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
        self._configuration = S2Configuration.default()
        self._info = S2Info()
        self._debug_info = S2Debug()
        self._uptime = S2Uptime()
        self._advancedInfo = S2AdvancedInfo()
        self._calibration = S2Calibration()
        self._bit_stats = S2BIT()
        self._fast_presets = S2FastPresets()
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
        self._max_API_version = 2020082601
        self._available_pulsing_modes = list(sorted(self.PULSING_MODES.keys(), key=lambda x: self.PULSING_MODES[x]))

    def set_up(self):
        """Sets up, clears potential overcurrent flags."""
        with self._lock:
            self._ignore_comm_count = True
            self._num_commands_failed = 0
            self._num_commands_sent = 0
            try:
                self.reload_info()
            finally:
                self._ignore_comm_count = False

            if self._info.hw_version != 2005:
                raise Exception('S-2 hardware version {} not supported by this '
                                'gen 2005 driver'.format(self._info.hw_version))
            if self._info.sw_version < 3500:
                raise Exception('Unsupported firmware version {}, please update the S-2 #{}'.format(
                    self._info.sw_version, self._info.device_id))
            api_version = self._info.API_version
            if api_version > self._max_API_version:
                raise Exception('S-2 firmware too recent ({}). Please update this program [S-2 #{}]'.format(
                    self._info.API_version, self._info.device_id))
            elif api_version < 2018102501:
                logger.debug('CSS and CST modes not available')
                for mode in [S2_PULSING_MODE_CSS, S2_PULSING_MODE_CST]:
                    self._available_pulsing_modes.remove(self.PULSING_MODES_LABELS[mode])
            if api_version < 2017102401:
                raise Exception('S-2 firmware too old ({}). Please update the S-2 #{}'.format(
                    self._info.API_version, self._info.device_id))
            self.reload_settings()
            self.reload_calibration()
            self.reload_bit_stats()
            self.reload_configuration()

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
        self._query_packet(_calibration_query_packet, self._calibration,
                           expected_header=S2_PACKET_QUERY_CALIBRATION,
                           expected_response_time=5.0)

    def reload_info(self):
        self._query_packet(_info_query_packet, self._info,
                           expected_header=S2_PACKET_INFO,
                           expected_response_time=5.0)
        self._last_info_time = time.time()

    def reload_settings(self):
        self._query_packet(_settings_query_packet, self._settings,
                           expected_header=S2_PACKET_QUERY_SETTINGS,
                           expected_response_time=5.0)

    def reload_configuration(self):
        self._query_packet(_configuration_query_packet, self._configuration,
                           expected_header=S2_PACKET_QUERY_CONFIGURATION,
                           expected_response_time=5.0)

    def reload_advanced_info(self):
        self._query_packet(_info_advanced_info, self._advancedInfo)

    def reload_bit_stats(self):
        self._query_packet(_bit_stats_query_packet, self._bit_stats,
                           expected_header=S2_PACKET_QUERY_BIT,
                           expected_response_time=5.0)

    def apply_current_settings(self, persistent):
        logger.debug('Applying {}'.format(self._settings))
        if persistent == False:
            packet = create_packet(S2_PACKET_SET_SETTINGS, self._settings)
        else:
            packet = create_packet(S2_PACKET_SET_PERSISTENT_SETTINGS, self._settings)
        self._query_packet(packet, self._settings, expected_header=S2_PACKET_QUERY_SETTINGS,
                           expected_response_time=10.0)
        self._set_settings_time = time.time()

    def apply_calibration(self, calibration, store=False):
        self.check_advanced_mode()
        if store:
            packet = create_packet(S2_PACKET_STORE_CALIBRATION, calibration)
        else:
            packet = create_packet(S2_PACKET_SET_CALIBRATION, calibration)
        return self._query_packet(packet, self._calibration, expected_header=S2_PACKET_QUERY_CALIBRATION,
                                  expected_response_time=5.0)

    def reset_overcurrent_flag(self):
        self._query_packet(_reset_overcurrent_packet, expected_response_time=5.0)

    def reset_undervoltage_flag(self):
        self._query_packet(_reset_undervoltage_packet, expected_response_time=5.0)

    def reset_overvoltage_flag(self):
        self._query_packet(_reset_overvoltage_packet, expected_response_time=5.0)

    def reset_overtemp_flag(self):
        self._query_packet(_reset_overtemp_packet, expected_response_time=5.0)

    def reset_uptime_counters(self):
        self._query_packet(_reset_uptime_packet, expected_response_time=5.0)

    def set_settings(self, pulsing_mode=None, voltage=None, pulse_period=None, pulse_width=None, current_limit=None,
                     voltage_A=None, voltage_B=None, pulse_width_A=None, pulse_width_B=None,
                     burst_ON=None, burst_OFF=None, current_limit_mode =None, persistent = False):
        """Set the specified settings. The unspecified parameters (=None) are not changed. Ramps up or down slowly the
        applied voltage"""
        with self._lock:
            was_off = self._settings.pulsing_mode == S2_PULSING_OFF
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
                if pulsing_mode == S2_PULSING_MODE_A:
                    self._settings.output_voltage_set_A = voltage
                elif pulsing_mode == S2_PULSING_MODE_B:
                    self._settings.output_voltage_set_B = voltage
                elif pulsing_mode == S2_PULSING_MODE_AB:
                    self._settings.output_voltage_set_A = voltage
                    self._settings.output_voltage_set_B = voltage
                else:
                    self._settings.output_voltage_set = voltage

            if voltage_A is not None:
                if not self._min_voltage <= voltage_A <= self._max_voltage:
                    raise S2InvalidVoltageError('Voltage A {} out of bounds ({}, {})'.format(voltage_A,
                                                                                             self._min_voltage,
                                                                                             self._max_voltage))
                self._settings.output_voltage_set_A = voltage_A

            if voltage_B is not None:
                if not self._min_voltage <= voltage_B <= self._max_voltage:
                    raise S2InvalidVoltageError('Voltage B {} out of bounds ({}, {})'.format(voltage_B,
                                                                                             self._min_voltage,
                                                                                             self._max_voltage))
                self._settings.output_voltage_set_B = voltage_B

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
                if pulse_width is not None:
                    if not self._pulse_width_min <= pulse_width <= self._pulse_width_max:
                        raise S2InvalidPulseParamsError('Pulse width {} out of bounds ({}, {})'.
                                                        format(pulse_width,
                                                               self._pulse_width_min, self._pulse_width_max))
                self._settings.pulse_width = int(1e-9 * pulse_width * self._info.pulse_clock_frequency)
            if pulse_width_A is not None:
                if not self._pulse_width_min <= pulse_width_A <= self._pulse_width_max:
                    raise S2InvalidPulseParamsError('Pulse width {} out of bounds ({}, {})'.
                                                    format(pulse_width_A,
                                                           self._pulse_width_min, self._pulse_width_max))
                self._settings.pulse_width_A = int(1e-9 * pulse_width_A * self._info.pulse_clock_frequency)
            if pulse_width_B is not None:
                if not self._pulse_width_min <= pulse_width_B <= self._pulse_width_max:
                    raise S2InvalidPulseParamsError('Pulse width {} out of bounds ({}, {})'.
                                                    format(pulse_width_B,
                                                           self._pulse_width_min, self._pulse_width_max))
                self._settings.pulse_width_B = int(1e-9 * pulse_width_B * self._info.pulse_clock_frequency)
            if current_limit is not None:
                self._settings.output_current_limit = current_limit

            if current_limit_mode is not None:
                self._settings.current_limit_mode = current_limit_mode

            self._settings.pulsing_mode = pulsing_mode

            self.apply_current_settings(persistent)

            return self._settings

    def get_uptime(self):
        return self._query_packet(_uptime_query_packet, self._uptime,
                                  expected_response_time=1.0)

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

    def set_configuration(self, device_id=0, laser_id=b'', lasing_min_current=0, internal_limit=0, modea_limit=0, modeb_limit=0, modecst_limit=0,
                               modecss_limit=0, modeab_a_limit=0, modeab_b_limit=0, mode_auto_duty_limit_low=None,
                          mode_auto_duty_limit_high=None):
        self.check_advanced_mode()
        if self.sw_version >= 3832:
            self.reload_configuration()
        self._configuration.device_id = device_id
        self._configuration.laser_id = laser_id
        self._configuration.mode_auto_duty_limit_low = 0.3
        self._configuration.mode_auto_duty_limit_high = 0.25
        self._configuration.mode_auto_high_secur_delay = 0
        self._configuration.integr_t_auto = 450
        self._configuration.lasing_min_current = lasing_min_current
        self._configuration.internal_limit = internal_limit
        self._configuration.modea_limit = modea_limit
        self._configuration.modeb_limit= modeb_limit
        self._configuration.modecst_limit=modecst_limit
        self._configuration.modecss_limit=modecss_limit
        self._configuration.modeab_a_limit= modeab_a_limit
        self._configuration.modeab_b_limit = modeab_b_limit
        if mode_auto_duty_limit_high is not None:
            self._configuration.mode_auto_duty_limit_high = mode_auto_duty_limit_high
        if mode_auto_duty_limit_low is not None:
            self._configuration.mode_auto_duty_limit_low = mode_auto_duty_limit_low
        packet = create_packet(S2_PACKET_SET_CONFIGURATION, self._configuration)
        if self.sw_version >= 3832:
            self._query_packet(packet, self._configuration, expected_header=S2_PACKET_QUERY_CONFIGURATION,
                               expected_response_time=5)
        return self._configuration

    def reboot_to_bootloader(self):
        self.check_advanced_mode()
        return self._query_packet(_bootloader_packet)

    def configure_fast_mode_presets(self, preset_number = None, pulse_period= None, pulse_width= None):
        if preset_number is not None:
            self._fast_presets.preset_number= preset_number
        if pulse_period is not None:
            self._fast_presets.pulse_period = pulse_period
        if pulse_width is not None:
            self._fast_presets.pulse_width = pulse_width
        packet = create_packet(S2_PACKET_SET_FAST_PRESET, self._fast_presets)
        return self._query_packet(packet, self._fast_presets, expected_response_time=5)

    def query_debug_info(self):
        return self._query_packet(_debug_query_packet, self._debug_info, expected_response_time=5)

if __name__ == '__main__':
    import serial
    from sdeux.gen2005 import S2
    from sdeux.serial_handler import S2SerialHandler

    #th = serial('/dev/ttyUSB0')
    th = S2SerialHandler('/dev/ttyUSB0')
    # import dms
    # dms = dms.DMSManager()
    # th = dms.get_instrument('PROD/DUE/INSTRUMENTS/S2_RED')
    # with dms.acquire_instruments(th):
    th.open()
    s2 = S2(th)
    s2.set_up()
    print(s2.info)
    # s2.set_configuration(laser_id='SW999')
    # s2.set_up()
    # s2.reload_settings()
    # s2.settings
    # s2.set_settings('modeAB', 5, 1000, 500, 5)
    # print(s2.settings)
    # s2.settings.pulsing_mode = 1
    # s2.settings.pulse_period = 1200
    # s2.settings.pulse_width = 60
    # s2.settings.output_voltage_set = 2.0
    # s2.settings.output_current_limit = 0.5
    # s2.settings.sync_out_width = 100
    # s2.apply_current_settings()
    # print(s2.settings)
    # s2.reload_info()
    # print(s2.info)