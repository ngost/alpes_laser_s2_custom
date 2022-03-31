# -*- coding: utf-8 -*-

import logging
import os
import subprocess
import time
from copy import deepcopy

from sdeux.auto_detect import init_driver
from sdeux.serial_handler import S2SerialHandler


logger = logging.getLogger(__name__)
terminalLogger = logging.getLogger('{}.{}'.format(__name__, 'terminal'))

__author__ = 'chiesa'
__copyright__ = "Copyright 2018, Alpes Lasers SA"


class FirmwareUpdater:

    FINISHED_STEP = 'finished'

    def __init__(self,
                 port,
                 firmware_path,
                 stm32flash_path,
                 new_firmware_version,
                 hw_version,
                 device_serial=None,
                 configuration=None):
        """
        :param port: the RS232 port path,
        :param firmware_path: the path to the firmware binary,
        :param stm32flash_path: the path to the stm32flash installation program,
        :param int new_firmware_version: the version number of the firmware binary to be installed,
        """

        self.port = port
        self.firmwarePath = firmware_path
        self.stm32flashPath = stm32flash_path
        self.newFirwareVersion = int(new_firmware_version)
        self.hwVersion = int(hw_version)
        self.s2DeviceId = None
        self.th = None
        self.s2 = None
        self.s2Info = None
        self.s2Settings = None
        self.s2Calibration = None
        self.s2InfoAfter = None
        self.s2SettingsAfter = None
        self.s2CalibrationAfter = None
        self.s2ConfigurationAfter = None
        self.configuration = configuration or {}
        self.deviceSerial = int(device_serial) if device_serial else None
        self.totalSteps = None
        if not os.path.exists(self.stm32flashPath):
            raise Exception
        if not os.path.exists(self.firmwarePath):
            raise Exception
        if not os.access(self.firmwarePath, os.R_OK):
            raise Exception
        if not os.access(self.stm32flashPath, os.X_OK):
            raise Exception

    def connect(self):
        self.th = S2SerialHandler(self.port)
        self.th.open()
        self.s2 = init_driver(self.th)
        self.s2.set_up()
        self.s2.advanced_mode = True

    def disconnect(self):
        if self.th:
            self.th.close()
            self.th = None
            self.s2 = None

    def is_connected(self):
        try:
            self.connect()
            return True
        except Exception as e:
            logger.debug(e, exc_info=1)
            return False
        finally:
            self.disconnect()

    def log_step(self, step, message):
        terminalLogger.info('[{}/{}, S2 #{}] {}'.format(step if step != self.FINISHED_STEP else self.totalSteps,
                                                        self.totalSteps,
                                                        self.s2DeviceId,
                                                        message))

    def install(self, resurrection=False):
        if self.hwVersion == 2005 and self.deviceSerial is None:
            raise RuntimeError('device serial must be specified for gen2005')
        try:
            self.totalSteps = 3
            self.log_step(0, 'Writing firmware: DO NOT DISCONNECT THE DEVICE!!!')
            self.write_firmware(resurrection)
            self.log_step(1, 'Boot to operational mode')
            if not resurrection:
                self.boot_to_firmware()
            self.log_step(2, 'Checking communication')
            self.connect()
            if not self.s2.sw_version == self.newFirwareVersion:
                raise Exception('S-2 sw_version={}, but {} was expected'.format(self.s2.sw_version,
                                                                                self.newFirwareVersion))
            if self.hwVersion == 2005 and self.deviceSerial:
                self.s2.set_configuration(device_id=self.deviceSerial)
            self.disconnect()
        except Exception as e:
            logger.exception(e)
            self.log_error_occurred()
        finally:
            self.disconnect()
            terminalLogger.info('Update procedure finished: you may now disconnect the S2.')

    def upgrade(self):
        self.totalSteps = 6
        try:
            self.connect()
            if self.s2.info.sw_version == self.newFirwareVersion:
                self.log_step(self.FINISHED_STEP,
                              'S2 already at firmware version {}: doing nothing.'.format(self.newFirwareVersion))
                return
            self.s2Info = self.s2.info
            self.s2Settings = self.s2.settings
            self.s2Calibration = self.s2.calibration
            self.s2DeviceId = self.s2.device_id
            terminalLogger.info('Connected to S2 #{}.'
                                '\n >> DO NOT DISCONNECT THE DEVICE! '
                                '\n >> DO NOT SWITCH ANYTHING OFF'.format(self.s2DeviceId))
            logger.info('before={}'.format(dict(info=self.s2Info.to_dict(),
                                                settings=self.s2Settings.to_dict(),
                                                calibration=self.s2Calibration.to_dict())))
            self.log_step(0, 'Rebooting to bootloader mode.')
            self.s2.reboot_to_bootloader()
            time.sleep(2)
            self.disconnect()
            self.log_step(1, 'Writing firmware.')
            self.write_firmware()
            self.log_step(2, 'Rebooting to operational mode.')
            self.boot_to_firmware()
            self.log_step(3, 'Checking communication.')
            self.connect()
            self.log_step(4, 'Rewriting configuration.')
            self.s2.apply_calibration(self.s2Calibration, store=True)
            self.s2.reload_calibration()

            s2_config = self.configuration
            s2_config.update(device_id=self.s2Info.device_id,
                             laser_id=self.s2Info.laser_id)
            self.s2.set_configuration(**s2_config)
            self.s2.reload_info()
            self.s2.reload_configuration()
            self.s2.reload_settings()
            self.s2InfoAfter = self.s2.info
            self.s2SettingsAfter = self.s2.settings
            self.s2CalibrationAfter = self.s2.calibration
            self.s2ConfigurationAfter = self.s2.configuration
            logger.info('after={}'.format(dict(info=self.s2InfoAfter.to_dict(),
                                               settings=self.s2SettingsAfter.to_dict(),
                                               calibration=self.s2CalibrationAfter.to_dict(),
                                               configuration=self.s2ConfigurationAfter.to_dict())))

            self.disconnect()
            if self.is_correctly_updated():
                self.log_step(self.FINISHED_STEP, 'Firmware update finalized.')
            else:
                self.log_error_occurred()
        except Exception as e:
            logger.exception(e)
            self.log_error_occurred()
        finally:
            self.disconnect()
            terminalLogger.info('Update procedure finished: you may now disconnect the S2.')

    def log_error_occurred(self):
        terminalLogger.error('Some errors occurred. Please submit log file to AlpesLasers')

    def is_correctly_updated(self):
        return True

    def boot_to_firmware(self):
        retry_count = 3
        while retry_count > 0:
            try:
                subprocess.run([self.stm32flashPath,
                                '-b', '38400', '-g', '0', self.port],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               check=True)
                break
            except Exception as e:
                logger.debug(e, exc_info=1)
                retry_count -= 1
                if retry_count == 0:
                    raise
                else:
                    time.sleep(1)
        time.sleep(1)

    def resurrection(self):
        subprocess.run([self.stm32flashPath, '-g', '0', '-b', '38400', '-w',
                        self.firmwarePath, self.port],
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE,
                       check=True)

    def write_firmware(self, resurrection=False):
        retry_count = 2
        while retry_count > 0:
            try:
                params = [self.stm32flashPath]
                if resurrection:
                    params += ['-g', '0']
                params += ['-b', '38400', '-w',
                           self.firmwarePath, self.port]
                subprocess.run(params,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               check=True)
                break
            except Exception as e:
                logger.debug(e, exc_info=1)
                retry_count -= 1
                if retry_count == 0:
                    raise
                else:
                    time.sleep(1)
        time.sleep(1)

