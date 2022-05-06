import sys
import time

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QMessageBox, QLineEdit, QLabel, QComboBox, QAction
from PyQt5.QtGui import QPainter, QPen, QIntValidator, QDoubleValidator
from PyQt5.QtCore import QCoreApplication
from PyQt5 import QtCore
import sdeux.gen5 as alpes
import serial
from sdeux.serial_handler import S2SerialHandler

# ---------------------- s2 import
# from s2_py_00 import serial_open, serial_close, s2_serial_setup, s2_query_info, s2_set_settings, s2_query_settings
#
# from s2_py_00 import S2_info, S2_settings, S2_BAUD, NULL
# from s2_py_00 import S2_PULSING_OFF, S2_PULSING_INTERNAL, S2_PULSING_EXTERNAL, S2_PULSING_BURST, S2_PULSING_BURST_EXTERNAL
import logging
from logging import info, error

logging.getLogger().setLevel(logging.INFO)
# from tests.s2_local_settings import s2_port_name

# ---------------------- s2 import ended
# '/dev/ttyUSB0'

global s2_port_name  # = 'COM3'
global connected_status  # = False
global measurement_state
global measurer
global th
global refresher
global s2
global list_input_voltage_measure_result
global list_output_voltage_measure_result
global list_output_current_measure_result
global list_output_current_out_of_pulse_measure_result
global list_voltage_set_measure_result
global list_pulse_period
global list_pulse_width
global list_measure_timespan_result


class ValueUpdater(QThread):
    callback = QtCore.pyqtSignal(object)
    isRunning = False

    def __init__(self, parent, loop_time=1.0):  # parent는 WndowClass에서 전달하는 self이다.(WidnowClass의 인스턴스)
        super().__init__(parent)
        self.parent = parent  # self.parent를 사용하여 WindowClass 위젯을 제어할 수 있다.
        self.loop_time = loop_time

    def run(self):
        # 함수 런
        self.isRunning = True
        index = 0
        while self.isRunning:
            index += 1
            time.sleep(self.loop_time)
            self.callback.emit(str(index))

    def stop(self):
        try:
            self.isRunning = False
            self.quit()
            self.wait(1000)
        except Exception as e:
            print(e)


class MyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def paintEvent(self, event):

        # ----------------------------------구분선
        self.line_ = QPainter(self)
        self.line_.begin(self)
        self.line_.setPen(QPen(Qt.black, 1))
        self.line_.drawLine(50, 460, 550, 460)
        self.line_.end()
        # ----------------------------------구분선

        self.line_ = QPainter(self)
        self.line_.begin(self)
        self.line_.setPen(QPen(Qt.black, 1))
        self.line_.drawLine(50, 280, 550, 280)
        self.line_.end()
        # ----------------------------------구분선

    def initUI(self):
        global connected_status
        global s2_port_name
        global measurement_state
        measurement_state = False
        connected_status = False
        s2_port_name = 'COM4'

        self.text_title = QLabel("ALPES LASERS for KIST", self)
        self.text_title.setAlignment(Qt.AlignCenter)
        self.text_title.move(150, 20)
        self.font_title = self.text_title.font()
        self.font_title.setPointSize(20)
        self.font_title.setBold(True)
        self.text_title.setFont(self.font_title)

        # 실행 버튼
        self.btn_measure = QPushButton('측정', self)
        self.btn_measure.resize(100, 20)
        self.btn_measure.move(220, 420)
        self.btn_measure.clicked.connect(self.start_measure)

        # 포트입력 및 연결 테스트 버튼
        self.btn_conn = QPushButton('Not Connected', self)
        self.btn_conn.resize(120, 22)
        self.btn_conn.move(400, 99)
        self.btn_conn.clicked.connect(self.open_connection)  # QCoreApplication.instance().quit

        self.text_port = QLabel("Port", self)
        self.text_port.setAlignment(Qt.AlignCenter)
        self.text_port.move(50, 103)

        self.line_edit = QLineEdit(self)
        self.line_edit.move(200, 100)
        self.line_edit.setText(s2_port_name)

        # period, ns
        self.text_period = QLabel("Period, ns", self)
        self.text_period.setAlignment(Qt.AlignCenter)
        self.text_period.move(50, 133)

        self.edit_period = QLineEdit(self)
        self.edit_period.move(200, 130)
        self.edit_period.setValidator(QIntValidator())
        self.edit_period.setText('50000')

        # pulse_width
        self.text_pulse_width = QLabel("Pulse_width, ns", self)
        self.text_pulse_width.setAlignment(Qt.AlignCenter)
        self.text_pulse_width.move(50, 163)
        self.edit_pulse_width = QLineEdit(self)
        self.edit_pulse_width.move(200, 160)
        self.edit_pulse_width.setValidator(QIntValidator())
        self.edit_pulse_width.setText('500')

        # output_voltage_set
        self.text_voltage_set = QLabel("Output_voltage_set", self)
        self.text_voltage_set.setAlignment(Qt.AlignCenter)
        self.text_voltage_set.move(50, 193)
        self.edit_voltage_set = QLineEdit(self)
        self.edit_voltage_set.move(200, 190)
        self.edit_voltage_set.setValidator(QDoubleValidator())
        self.edit_voltage_set.setText('0')

        # output_current_limit
        self.text_output_current_limit = QLabel("Output_current_limit", self)
        self.text_output_current_limit.setAlignment(Qt.AlignCenter)
        self.text_output_current_limit.move(50, 223)
        self.edit_output_current_limit = QLineEdit(self)
        self.edit_output_current_limit.move(200, 220)
        self.edit_output_current_limit.setValidator(QDoubleValidator())
        self.edit_output_current_limit.setText('1')

        # s2_pulsing_mode comboBox
        self.text_box_pulsing = QLabel("S2_Pulsing_Mode", self)
        self.text_box_pulsing.setAlignment(Qt.AlignCenter)
        self.text_box_pulsing.move(50, 253)

        self.combo_box_pulsing = QComboBox(self)
        self.combo_box_pulsing.move(200, 250)
        #        S2_PULSING_OFF, S2_PULSING_INTERNAL, S2_PULSING_EXTERNAL, S2_PULSING_BURST, S2_PULSING_BURST_EXTERNAL
        self.combo_box_pulsing.addItem("S2_PULSING_OFF")
        self.combo_box_pulsing.addItem("S2_PULSING_INTERNAL")
        self.combo_box_pulsing.addItem("S2_PULSING_EXTERNAL")
        self.combo_box_pulsing.addItem("S2_PULSING_BURST")
        self.combo_box_pulsing.addItem("S2_PULSING_BURST_EXTERNAL")

        ############################# 측정용 UI

        # voltage_set_min
        self.text_voltage_set_min = QLabel("Voltage_Set_Min, (V)", self)
        self.text_voltage_set_min.setAlignment(Qt.AlignCenter)
        self.text_voltage_set_min.move(50, 303)

        self.edit_voltage_set_min = QLineEdit(self)  # Voltage_set_min
        self.edit_voltage_set_min.move(280, 300)
        self.edit_voltage_set_min.setText('0')
        self.edit_voltage_set_min.setValidator(QDoubleValidator())
        self.edit_voltage_set_min.setEnabled(True)

        # voltage_set_max
        self.text_voltage_set_max = QLabel("Voltage_Set_Max, (V)", self)
        self.text_voltage_set_max.setAlignment(Qt.AlignCenter)
        self.text_voltage_set_max.move(50, 333)

        self.edit_voltage_set_max = QLineEdit(self)  # Voltage_set_max
        self.edit_voltage_set_max.move(280, 330)
        self.edit_voltage_set_max.setText('1')
        self.edit_voltage_set_max.setValidator(QDoubleValidator())
        self.edit_voltage_set_max.setEnabled(True)

        # voltage_interval
        self.text_voltage_set_rise = QLabel("Voltage_Set_Rise, (V)", self)
        self.text_voltage_set_rise.setAlignment(Qt.AlignCenter)
        self.text_voltage_set_rise.move(50, 363)

        self.edit_voltage_set_rise = QLineEdit(self)  # Voltage_set_rise
        self.edit_voltage_set_rise.move(280, 360)
        self.edit_voltage_set_rise.setText('0.01')
        self.edit_voltage_set_rise.setValidator(QDoubleValidator())
        self.edit_voltage_set_rise.setEnabled(True)

        # Voltage_Measurement_Cycle (voltage 상승 주기 para)
        self.text_voltage_rise_time = QLabel("Voltage_Rise_Time, (ms)", self)
        self.text_voltage_rise_time.setAlignment(Qt.AlignCenter)
        self.text_voltage_rise_time.move(50, 393)

        self.edit_voltage_rise_time = QLineEdit(self)  # Voltage_set_rise_time
        self.edit_voltage_rise_time.move(280, 390)
        self.edit_voltage_rise_time.setText('10')
        self.edit_voltage_rise_time.setValidator(QDoubleValidator())
        self.edit_voltage_rise_time.setEnabled(True)

        # 측정 결과 UI
        # -----------------------------------------
        self.text_result = QLabel("Result", self)
        self.text_result.setAlignment(Qt.AlignCenter)
        self.text_result.move(280, 470)
        self.font_result = self.text_title.font()
        self.font_result.setPointSize(14)
        self.font_result.setBold(True)
        self.text_result.setFont(self.font_result)
        # -----------------------------------------

        # input_voltage_measured
        self.text_input_voltage_measured = QLabel("input_voltage", self)
        self.text_input_voltage_measured.setAlignment(Qt.AlignCenter)
        self.text_input_voltage_measured.move(50, 500)
        self.edit_input_voltage_measured = QLabel(self)
        self.edit_input_voltage_measured.move(250, 500)
        self.edit_input_voltage_measured.resize(150, 22)
        self.edit_input_voltage_measured.setText('0')

        # output_voltage_measured
        self.text_output_voltage_measured = QLabel("output_voltage", self)
        self.text_output_voltage_measured.setAlignment(Qt.AlignCenter)
        self.text_output_voltage_measured.move(50, 530)
        self.edit_output_voltage_measured = QLabel(self)
        self.edit_output_voltage_measured.move(250, 530)
        self.edit_output_voltage_measured.resize(150, 22)
        self.edit_output_voltage_measured.setText('0')

        # output_current_measured
        self.text_output_current_measured = QLabel("output_current", self)
        self.text_output_current_measured.setAlignment(Qt.AlignCenter)
        self.text_output_current_measured.move(50, 560)
        self.edit_output_current_measured = QLabel(self)
        self.edit_output_current_measured.move(250, 560)
        self.edit_output_current_measured.resize(150, 22)
        self.edit_output_current_measured.setText('0')

        # output_current_measured_out_of_pulse
        self.text_output_current_measured_out_of_pulse = QLabel("output_current_out_of_pulse", self)
        self.text_output_current_measured_out_of_pulse.setAlignment(Qt.AlignCenter)
        self.text_output_current_measured_out_of_pulse.move(50, 590)
        self.edit_output_current_measured_out_of_pulse = QLabel(self)
        self.edit_output_current_measured_out_of_pulse.move(250, 590)
        self.edit_output_current_measured_out_of_pulse.resize(150, 22)
        self.edit_output_current_measured_out_of_pulse.setText('0')

        self.quit = QAction("quit", self)
        self.quit.triggered.connect(self.closeEvent)

        self.setWindowTitle('ALPES LASERS for KIST')
        self.setGeometry(700, 200, 600, 700)
        self.show()

    def start_measure(self):
        if int(self.edit_voltage_rise_time.text()) < 10:
            QMessageBox.about(self, '실패', 'rise time 값이 너무 작습니다.')
            return

        if self.edit_voltage_set_min.text() == self.edit_voltage_set_max.text():
            QMessageBox.about(self, '실패', 'voltage min, max값 설정이 올바르지 않습니다.')
            return

        global measurement_state
        global measurer
        self.btn_measure.setText("측정중")
        self.btn_measure.setEnabled(False)
        self.edit_voltage_set.setEnabled(False)

        print("measure start...")
        global list_input_voltage_measure_result
        global list_output_voltage_measure_result
        global list_output_current_measure_result
        global list_output_current_out_of_pulse_measure_result
        global list_voltage_set_measure_result
        global list_measure_timespan_result
        global list_pulse_period
        global list_pulse_width

        list_input_voltage_measure_result = list()
        list_output_voltage_measure_result = list()
        list_output_current_measure_result = list()
        list_output_current_out_of_pulse_measure_result = list()
        list_voltage_set_measure_result = list()
        list_measure_timespan_result = list()
        list_pulse_period = list()
        list_pulse_width = list()


        measurer = ValueUpdater(self, loop_time=float(self.edit_voltage_rise_time.text()) * 0.001)
        measurer.callback.connect(self.voltage_measure_callback)
        measurer.start()

    def voltage_measure_callback(self):
        global list_input_voltage_measure_result
        global list_output_voltage_measure_result
        global list_output_current_measure_result
        global list_output_current_out_of_pulse_measure_result
        global list_voltage_set_measure_result
        global list_measure_timespan_result
        global list_pulse_period
        global list_pulse_width

        import math

        if measurer.isRunning == False:
            print("callback 종료됨.. 결과 엑셀 출력 예정")
            self.edit_voltage_set.setText('0')
            import pandas as pd
            import os
            import datetime
            now = datetime.datetime.now()

            raw_data = {'input': list_input_voltage_measure_result, 'output': list_output_voltage_measure_result,
                        'current': list_output_current_measure_result,
                        'current_pulse': list_output_current_out_of_pulse_measure_result,
                        'voltage_set': list_voltage_set_measure_result,
                        'pulse_period': list_pulse_period,
                        'pulse_width': list_pulse_width,
                        'measure_time': list_measure_timespan_result
                        }  # 리스트 자료형으로 생성
            pd_data = pd.DataFrame(raw_data)  # 데이터 프레임으로 전환
            path = os.path.join(os.path.expanduser("~"), "Desktop", "voltage_sample_"
                                +str(now.hour)+str(now.minute)+str(now.second) + ".xlsx")
            pd_data.to_excel(path)  # 엑셀로 저장
            QMessageBox.about(self, '완료', '측정이 완료되었습니다.')
            return

        global measurement_state
        if measurement_state == False:
            measurement_state = True
            current_voltage = round(float(self.edit_voltage_set_min.text()), 6)
        else:
            current_voltage = round(float(self.edit_voltage_set.text()), 6)

        # float(self.edit_voltage_set_min.text())
        # float(self.edit_voltage_set_max.text())

        voltage_set_rise = round(float(self.edit_voltage_set_rise.text(), ), 6)
        max_voltage = float(self.edit_voltage_set_max.text())

        if current_voltage <= max_voltage:
            import datetime
            # todo 측정
            # DEBUG..
            self.update_setting()

            try:
                input_voltage = s2.input_voltage_measured
                output_voltage = s2.measured_voltage
                output_current = s2.measured_current
                output_current_pulse = s2._info.output_current_measured_out_of_pulse
                pulse_period = s2.pulse_period
                pulse_width = s2.pulse_width
                now = datetime.datetime.now()

                #값 저장
                list_input_voltage_measure_result.append(input_voltage)
                list_output_voltage_measure_result.append(output_voltage)
                list_output_current_measure_result.append(output_current)
                list_output_current_out_of_pulse_measure_result.append(output_current_pulse)
                list_pulse_period.append(pulse_period)
                list_pulse_width.append(pulse_width)
                list_measure_timespan_result.append(
                    str(now.hour) + ':' + str(now.minute) + ':' + str(now.second) + ':' + str(now.microsecond))
            except Exception as e:
                # DEBUG
                import random
                print("measure fail, random value replaced")
                input_voltage = random.random()
                output_voltage = random.random()
                output_current = random.random()
                output_current_pulse = random.random()
                now = datetime.datetime.now()

                list_input_voltage_measure_result.append(input_voltage)
                list_output_voltage_measure_result.append(output_voltage)
                list_output_current_measure_result.append(output_current)
                list_output_current_out_of_pulse_measure_result.append(output_current_pulse)
                list_measure_timespan_result.append(str(now.hour)+':'+str(now.minute)+':'+str(now.second)+':'+str(now.microsecond))


            list_voltage_set_measure_result.append(self.edit_voltage_set.text())
            self.edit_voltage_set.setText(str(round(current_voltage + voltage_set_rise, 6)))
        else:
            print("측정 종료")
            measurement_state = False
            self.btn_measure.setText("측정")
            self.btn_measure.setEnabled(True)
            self.edit_voltage_set.setEnabled(True)
            measurer.stop()

    def start_refresh(self):
        global refresher

        refresher = ValueUpdater(self, loop_time=0.5)
        refresher.callback.connect(self.thread_callback)
        refresher.start()

    # def stop_refresh(self):
    #     global refresher
    #     refresher.quit()
    #     refresher.wait(3000)

    def thread_callback(self, index):
        global s2
        global connected_status

        # DEBUG
        # if connected_status is False:
        #     import random
        #     input_voltage = random.random()
        #     output_voltage = random.random()
        #     output_current = random.random()
        #     output_current_pulse = random.random()
        #     self.edit_input_voltage_measured.setText(str(input_voltage))
        #     self.edit_output_voltage_measured.setText(str(output_voltage))
        #     self.edit_output_current_measured.setText(str(output_current))
        #     self.edit_output_current_measured_out_of_pulse.setText(str(output_current_pulse))
        #     return

        # 'output_current_measured', 'MCU_temperature', 'laser_temperature',
        # 'output_current_measured_out_of_pulse', 'status', 'pulse_clock_frequency', 'API_version',
        try:
            self.update_setting()
            input_voltage = s2.input_voltage_measured
            output_voltage = s2.measured_voltage
            output_current = s2.measured_current
            output_current_pulse = s2._info.output_current_measured_out_of_pulse

            # print(str(input_voltage))
            # print(str(output_voltage))
            # print(str(output_current))
            # print(str(output_current_pulse))
            self.edit_input_voltage_measured.setText(str(input_voltage))
            self.edit_output_voltage_measured.setText(str(output_voltage))
            self.edit_output_current_measured.setText(str(output_current))
            self.edit_output_current_measured_out_of_pulse.setText(str(output_current_pulse))
        except Exception as e:
            print(e)

    def open_connection(self):
        global connected_status
        global th
        global s2

        if connected_status == False:
            try:
                # 초기화
                # th = S2SerialHandler(str(self.line_edit.text().encode('utf-8')))
                th = S2SerialHandler(self.line_edit.text())
                # 열려라 포트
                th.open()
                # 초기값 초기화
                s2 = alpes.S2(th)
                s2.set_up()
                s2.settings.pulsing_mode = 0  # 무조건 OFF 초기화
                self.combo_box_pulsing.setCurrentText('S2_PULSING_OFF')
                s2.settings.pulse_period = int(self.edit_period.text())
                s2.settings.pulse_width = int(self.edit_pulse_width.text())
                s2.settings.output_voltage_set = float(self.edit_voltage_set.text())
                s2.settings.output_current_limit = float(self.edit_output_current_limit.text())
                # 초기 설정값 적용
                s2.apply_current_settings()
                s2.reload_info()
                # 측정값 업데이트 시작
                self.start_refresh()
                # UI 업데이트
                self.btn_conn.setText("Connected")
                connected_status = True
            except Exception as e:
                QMessageBox.about(self, '연결 실패', '포트를 확인해야합니다 : ' + self.line_edit.text() + ',' + str(e))
                connected_status = False
                # Debug
                # self.start_refresh()
                return
        elif connected_status == True:
            try:
                # 닫혀라 참깨 포트
                th.close()
                self.btn_conn.setText("Not Connected")
                connected_status = False
                refresher.stop()
            except Exception as e:
                print(e)
                QMessageBox.about(self, '에러', '이미 연결이 해제되어 있습니다.')
                connected_status = False
                return

    # def simple_connection_test(self):
    #     test_port_name = self.line_edit.text()
    #     s2port = serial_open(test_port_name.encode('utf-8'))
    #     print(test_port_name.encode('utf-8'))
    #     if s2port == NULL:
    #         QMessageBox.about(self, '연결 테스트 실패', 'port connect fail, Name is :' + str(test_port_name.encode('utf-8')))
    #         return
    #     else:
    #         QMessageBox.about(self, '연결 테스트 성공', 'port connect Success, Name is :' + str(test_port_name.encode('utf-8')))
    #         return

    def update_setting(self):
        global s2

        if connected_status == False:
            QMessageBox.about(self, '알림', '연결 상태를 확인하신 후 재시도 바랍니다.')
            return

        s2 = alpes.S2(th)
        s2.set_up()

        #  S2_PULSING_OFF = 0        S2_PULSING_INTERNAL = 1        S2_PULSING_FULL_EXTERNAL = 2        S2_PULSING_EXTERNAL = 2        S2_PULSING_BURST = 3
        #  S2_PULSING_MODE_A = 4        # S2_PULSING_MODE_B = 5     S2_PULSING_BURST_EXTERNAL_TRIGGER = 6                   S2_PULSING_BURST_EXTERNAL = 6

        # pulsing mode 설정
        if self.combo_box_pulsing.currentText() == 'S2_PULSING_OFF':
            s2.settings.pulsing_mode = 0
        elif self.combo_box_pulsing.currentText() == 'S2_PULSING_INTERNAL':
            s2.settings.pulsing_mode = 1
        elif self.combo_box_pulsing.currentText() == 'S2_PULSING_EXTERNAL':
            s2.settings.pulsing_mode = 2
        elif self.combo_box_pulsing.currentText() == 'S2_PULSING_BURST':
            s2.settings.pulsing_mode = 3
        elif self.combo_box_pulsing.currentText() == 'S2_PULSING_BURST_EXTERNAL':
            s2.settings.pulsing_mode = 6

        # setting값 설정
        s2.settings.pulse_period = int(self.edit_period.text())
        s2.settings.pulse_width = int(self.edit_pulse_width.text())
        s2.settings.output_voltage_set = float(self.edit_voltage_set.text())
        s2.settings.output_current_limit = float(self.edit_output_current_limit.text())
        s2.apply_current_settings()

        # print(s2.settings)
        s2.reload_info()
        # print(s2.info)

    def closeEvent(self, event):
        SavePreference()

def SavePreference():
    import os
    import shelve
    path = os.path.expanduser('~/alpes_preference')
    db = shelve.open(path)

    # 저장할 datas
    db['port'] = ex.line_edit.text()
    db['period'] = ex.edit_period.text()
    db['pulse_width'] = ex.edit_pulse_width.text()
    db['out_voltage_set'] = ex.edit_voltage_set.text()
    db['out_current_limit'] = ex.edit_output_current_limit.text()
    db['voltage_set_min'] = ex.edit_voltage_set_min.text()
    db['voltage_set_max'] = ex.edit_voltage_set_max.text()
    db['voltage_set_rise'] = ex.edit_voltage_set_rise.text()
    db['voltage_set_rise_time'] = ex.edit_voltage_rise_time.text()
    print("saved")

    # del db['test']
    db.close()

def LoadPreference():
    print("프로그램 시작")
    import os
    import shelve

    path = os.path.expanduser('~/alpes_preference')
    db = shelve.open(path)

    global serverIP  # 전역 변수 사용할것이다 라는 뜻..
    global serverPort  # 전역 변수 사용할것이다 라는 뜻..
    global routine_time  # 반복 시간
    global delay_start_time  # 지연 시작 시간

    try:
        # 불러올 datas
        ex.line_edit.setText(db['port'])
        ex.edit_period.setText(db['period'])
        ex.edit_pulse_width.setText(db['pulse_width'])
        ex.edit_voltage_set.setText(db['out_voltage_set'])
        ex.edit_output_current_limit.setText(db['out_current_limit'])
        ex.edit_voltage_set_min.setText(db['voltage_set_min'])
        ex.edit_voltage_set_max.setText(db['voltage_set_max'])
        ex.edit_voltage_set_rise.setText(db['voltage_set_rise'])
        ex.edit_voltage_rise_time.setText(db['voltage_set_rise_time'])

    except Exception:
        pass
    except KeyError:
        pass

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        ex = MyApp()
        LoadPreference()
        sys.exit(app.exec_())
    except Exception as e:
        print(e)