===============================
sdeux
===============================

By: chiesa 
Date: March 31, 2020
Copyright Alpes Lasers SA, Neuchatel, Switzerland

Driver for the Alpes Lasers S-2 pulser. Visit https://www.alpeslasers.ch/ for more informations.

Usage
-----

See also the examples folder in the sdeux package.

.. code::

   import os

   from sdeux.auto_detect import init_driver
   from sdeux.communication import RETRY_NO, RETRY_SOME
   from sdeux.serial_handler import S2SerialHandler

   th = None

   port = os.path.expanduser('~/tty.AL-S2')

   retry_policy = RETRY_SOME  # on communication errors, retries up to 3 times until a timeout of 3 seconds

   # retry_policy = RETRY_NO   # on communications errors, raise an exception directly


   def print_status(s2_instance):
       print_status = 'Measured current (A): {:.5f}\n'.format(s2_instance.measured_current) + \
                      'Measured voltage (V): {:.5f}\n'.format(s2_instance.measured_voltage) + \
                      'Target voltage (V): {:.5f}\n'.format(s2_instance.applied_voltage) + \
                      'Laser temperature (degC): {:.5f}\n'.format(s2_instance._info.laser_temperature) + \
                      'Overcurrent Limit (A): {:.5f}\n'.format(s2_instance.current_limit) + \
                      'MCU temperature (degC): {:.5f}\n'.format(s2_instance._info.MCU_temperature) + \
                      'Pulse Mode: {}\n'.format(s2_instance.pulsing_mode) + \
                      'Board Status: {}\n'.format(s2_instance.status_label)
       print(print_status)


   try:
       th = S2SerialHandler(port)
       th.open()
       s2 = init_driver(th)
       s2.set_up()
       s2.retry_policy = retry_policy
       print_status(s2)

   finally:
       if th:
           th.close()

