import sys
import time

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton,QMessageBox,QLineEdit,QLabel,QComboBox
from PyQt5.QtGui import QPainter, QPen,QIntValidator,QDoubleValidator
from PyQt5.QtCore import QCoreApplication
from PyQt5 import QtCore
import sdeux.gen5 as alpes
import serial
from sdeux.serial_handler import S2SerialHandler

#---------------------- s2 import
# from s2_py_00 import serial_open, serial_close, s2_serial_setup, s2_query_info, s2_set_settings, s2_query_settings
#
# from s2_py_00 import S2_info, S2_settings, S2_BAUD, NULL
# from s2_py_00 import S2_PULSING_OFF, S2_PULSING_INTERNAL, S2_PULSING_EXTERNAL, S2_PULSING_BURST, S2_PULSING_BURST_EXTERNAL
import logging
from logging import info, error
logging.getLogger().setLevel(logging.INFO)
#from tests.s2_local_settings import s2_port_name

#---------------------- s2 import ended
#'/dev/ttyUSB0'

global s2_port_name# = 'COM3'
global connected_status# = False
global th
global refresher
global s2


class ValueUpdater(QThread):
    callback = QtCore.pyqtSignal(object)
    isRunning = False

    def __init__(self, parent, loop_time=1): #parent는 WndowClass에서 전달하는 self이다.(WidnowClass의 인스턴스)
        super().__init__(parent)
        self.parent = parent    #self.parent를 사용하여 WindowClass 위젯을 제어할 수 있다.
        self.loop_time = loop_time
    
    def run(self):
        #함수 런
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
            self.wait(3000)
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
        self.line_.drawLine(50, 460, 450, 460)
        # ----------------------------------구분선
        self.line_.end()

    def initUI(self):
        global connected_status
        global s2_port_name
        connected_status = False
        s2_port_name = 'COM4'

        self.text_title = QLabel("ALPES LASERS for KIST",self)
        self.text_title.setAlignment(Qt.AlignCenter)
        self.text_title.move(100,20)
        self.font_title = self.text_title.font()
        self.font_title.setPointSize(20)
        self.font_title.setBold(True)
        self.text_title.setFont(self.font_title)

        # 실행 버튼
        self.btn = QPushButton('설정 업데이트', self)
        self.btn.resize(100,20)
        self.btn.move(220, 420)
        self.btn.clicked.connect(self.update_setting)

        # 포트입력 및 연결 테스트 버튼
        self.btn_conn = QPushButton('Not Connected', self)
        self.btn_conn.resize(120,22)
        self.btn_conn.move(350, 99)
        self.btn_conn.clicked.connect(self.open_connection) #QCoreApplication.instance().quit

        self.text_port = QLabel("Port",self)
        self.text_port.setAlignment(Qt.AlignCenter)
        self.text_port.move(50, 103)

        self.line_edit = QLineEdit(self)
        self.line_edit.move(200, 100)
        self.line_edit.setText(s2_port_name)



        #period, ns
        self.text_period = QLabel("Period, ns", self)
        self.text_period.setAlignment(Qt.AlignCenter)
        self.text_period.move(50, 133)

        self.edit_period = QLineEdit(self)
        self.edit_period.move(200, 130)
        self.edit_period.setValidator(QIntValidator())
        self.edit_period.setText('50000')

        #pulse_width
        self.text_pulse_width = QLabel("Pulse_width, ns", self)
        self.text_pulse_width.setAlignment(Qt.AlignCenter)
        self.text_pulse_width.move(50, 163)
        self.edit_pulse_width = QLineEdit(self)
        self.edit_pulse_width.move(200, 160)
        self.edit_pulse_width.setValidator(QIntValidator())
        self.edit_pulse_width.setText('500')

        #output_voltage_set
        self.text_voltage_set = QLabel("Output_voltage_set", self)
        self.text_voltage_set.setAlignment(Qt.AlignCenter)
        self.text_voltage_set.move(50, 193)
        self.edit_voltage_set = QLineEdit(self)
        self.edit_voltage_set.move(200, 190)
        self.edit_voltage_set.setValidator(QDoubleValidator())
        self.edit_voltage_set.setText('0')

        #output_current_limit
        self.text_output_current_limit = QLabel("Output_current_limit", self)
        self.text_output_current_limit.setAlignment(Qt.AlignCenter)
        self.text_output_current_limit.move(50, 223)
        self.edit_output_current_limit = QLineEdit(self)
        self.edit_output_current_limit.move(200, 220)
        self.edit_output_current_limit.setValidator(QDoubleValidator())
        self.edit_output_current_limit.setText('1')

        #s2_pulsing_mode comboBox
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

        #voltage_set_min
        self.text_voltage_set_min = QLabel("Voltage_Set_Min", self)
        self.text_voltage_set_min.setAlignment(Qt.AlignCenter)
        self.text_voltage_set_min.move(50, 283)
        self.edit_voltage_set_min = QLineEdit(self)
        self.edit_voltage_set_min.move(200, 280)
        self.edit_voltage_set_min.setText('0')
        self.edit_voltage_set_min.setEnabled(False)

        #voltage_set_max
        self.text_voltage_set_max = QLabel("Voltage_Set_Max", self)
        self.text_voltage_set_max.setAlignment(Qt.AlignCenter)
        self.text_voltage_set_max.move(50, 313)
        self.edit_voltage_set_max = QLineEdit(self)
        self.edit_voltage_set_max.move(200, 310)
        self.edit_voltage_set_max.setText('0')
        self.edit_voltage_set_max.setEnabled(False)

        #voltage_interval
        self.text_voltage_interval = QLabel("Voltage_Interval", self)
        self.text_voltage_interval.setAlignment(Qt.AlignCenter)
        self.text_voltage_interval.move(50, 343)
        self.edit_voltage_interval = QLineEdit(self)
        self.edit_voltage_interval.move(200, 340)
        self.edit_voltage_interval.setText('0')
        self.edit_voltage_interval.setEnabled(False)

        #measurement_interval
        self.text_measurement_interval = QLabel("Measurement_Interval, ms (1000ms = 1s)", self)
        self.text_measurement_interval.setAlignment(Qt.AlignCenter)
        self.text_measurement_interval.move(50, 373)
        self.edit_measurement_interval = QLineEdit(self)
        self.edit_measurement_interval.move(300, 370)
        self.edit_measurement_interval.setText('1000')
        self.edit_measurement_interval.setEnabled(False)

        # 측정 결과 UI
        # -----------------------------------------
        self.text_result = QLabel("Result",self)
        self.text_result.setAlignment(Qt.AlignCenter)
        self.text_result.move(220,470)
        self.font_result = self.text_title.font()
        self.font_result.setPointSize(12)
        self.font_result.setBold(True)
        self.text_result.setFont(self.font_result)
        # -----------------------------------------

        # input_voltage_measured
        self.text_input_voltage_measured = QLabel("input_voltage", self)
        self.text_input_voltage_measured.setAlignment(Qt.AlignCenter)
        self.text_input_voltage_measured.move(50, 500)
        self.edit_input_voltage_measured = QLabel(self)
        self.edit_input_voltage_measured.move(250, 500)
        self.edit_input_voltage_measured.setText('0')

        # output_voltage_measured
        self.text_output_voltage_measured = QLabel("output_voltage", self)
        self.text_output_voltage_measured.setAlignment(Qt.AlignCenter)
        self.text_output_voltage_measured.move(50, 530)
        self.edit_output_voltage_measured = QLabel(self)
        self.edit_output_voltage_measured.move(250, 530)
        self.edit_output_voltage_measured.setText('0')

        # output_current_measured
        self.text_output_current_measured = QLabel("output_current", self)
        self.text_output_current_measured.setAlignment(Qt.AlignCenter)
        self.text_output_current_measured.move(50, 560)
        self.edit_output_current_measured = QLabel(self)
        self.edit_output_current_measured.move(250, 560)
        self.edit_output_current_measured.setText('0')

        # output_current_measured_out_of_pulse
        self.text_output_current_measured_out_of_pulse = QLabel("output_current_out_of_pulse", self)
        self.text_output_current_measured_out_of_pulse.setAlignment(Qt.AlignCenter)
        self.text_output_current_measured_out_of_pulse.move(50, 590)
        self.edit_output_current_measured_out_of_pulse = QLabel(self)
        self.edit_output_current_measured_out_of_pulse.move(250, 590)
        self.edit_output_current_measured_out_of_pulse.setText('0')



        self.setWindowTitle('ALPES LASERS for KIST')
        self.setGeometry(710,200,500,700)
        self.show()


    def start_refresh(self):
        global refresher

        refresher = ValueUpdater(self,loop_time=0.5)
        refresher.callback.connect(self.thread_callback)
        refresher.start()

    # def stop_refresh(self):
    #     global refresher
    #     refresher.quit()
    #     refresher.wait(3000)

    def thread_callback(self, index):
        global s2

        # 'output_current_measured', 'MCU_temperature', 'laser_temperature',
        # 'output_current_measured_out_of_pulse', 'status', 'pulse_clock_frequency', 'API_version',
        input_voltage = s2.input_voltage_measured()
        output_voltage = s2.measured_voltage()
        output_current = s2.measured_current()
        output_current_pulse = s2._info.output_current_measured_out_of_pulse

        self.edit_input_voltage_measured.setText(str(input_voltage))
        self.edit_output_voltage_measured.setText(str(output_voltage))
        self.edit_output_current_measured.setText(str(output_current))
        self.edit_output_current_measured_out_of_pulse.setText(str(output_current_pulse))


    def open_connection(self):
        global connected_status
        global th
        global s2

        if connected_status == False:
            try:
                #초기화
                # th = S2SerialHandler(str(self.line_edit.text().encode('utf-8')))
                th = S2SerialHandler(self.line_edit.text())
                #열려라 포트
                th.open()
                # 초기값 초기화
                s2 = alpes.S2(th)
                s2.set_up()
                s2.settings.pulsing_mode = 0 # 무조건 OFF 초기화
                self.combo_box_pulsing.setCurrentText('S2_PULSING_OFF')
                s2.settings.pulse_period = self.edit_period.text()
                s2.settings.pulse_width = self.edit_pulse_width.text()
                s2.settings.output_voltage_set = self.edit_voltage_set.text()
                s2.settings.output_current_limit = self.edit_output_current_limit.text()
                #초기 설정값 적용
                s2.apply_current_settings()
                s2.reload_info()
                #측정값 업데이트 시작
                self.start_refresh()
                #UI 업데이트
                self.btn_conn.setText("Connected")
                connected_status = True
            except Exception as e:
                QMessageBox.about(self, '연결 실패', '포트를 확인해야합니다 : '+self.line_edit.text() + ',' + str(e))
                connected_status = False
                return
        elif connected_status == True:
            try:
                #닫혀라 참깨 포트
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
        
        #setting값 설정
        s2.settings.pulse_period = int(self.edit_period.text())
        s2.settings.pulse_width = int(self.edit_pulse_width.text())
        s2.settings.output_voltage_set = float(self.edit_voltage_set.text())
        s2.settings.output_current_limit = float(self.edit_output_current_limit.text())
        s2.apply_current_settings()

        # print(s2.settings)
        s2.reload_info()
        # print(s2.info)


        '''
        test_port_name = self.line_edit.text()
        s2port = serial_open(test_port_name.encode('utf-8'))
        print(test_port_name.encode('utf-8'))

        if s2port == NULL:
            QMessageBox.about(self, '연결 테스트 실패', 'port connect fail, Name is :' + str(test_port_name.encode('utf-8')))
            return

        #1. 포트 설정
        s2_serial_setup(s2port, S2_BAUD)
        s2s = S2_settings()
        s2_query_settings(s2port, s2s)

        #2. voltage set 설정
        s2s.output_voltage_set = float(str(self.edit_voltage_set.text()))
        
        #3. pulsing mode 설정
        #        S2_PULSING_OFF, S2_PULSING_INTERNAL, S2_PULSING_EXTERNAL, S2_PULSING_BURST, S2_PULSING_BURST_EXTERNAL
        if self.combo_box_pulsing.currentText() == 'S2_PULSING_OFF':
            s2s.pulsing_mode = S2_PULSING_OFF
        elif self.combo_box_pulsing.currentText() == 'S2_PULSING_INTERNAL':
            s2s.pulsing_mode = S2_PULSING_INTERNAL
        elif self.combo_box_pulsing.currentText() == 'S2_PULSING_EXTERNAL':
            s2s.pulsing_mode = S2_PULSING_EXTERNAL
        elif self.combo_box_pulsing.currentText() == 'S2_PULSING_BURST':
            s2s.pulsing_mode = S2_PULSING_BURST
        elif self.combo_box_pulsing.currentText() == 'S2_PULSING_BURST_EXTERNAL':
            s2s.pulsing_mode = S2_PULSING_BURST_EXTERNAL

        s2_set_settings(s2port, s2s, False)
        s2i = S2_info()
        s2_query_info(s2port, s2i)

        try:
            # 4. input_voltage_measured
            self.edit_input_voltage_measured.setText(str(s2i.intput_voltage_measured))
        except Exception as e:
            self.edit_input_voltage_measured.setText('N/A')

        try:
            # 5. output_voltage_measured
            self.edit_output_voltage_measured.setText(str(s2i.output_voltage_measured))
        except Exception as e:
            self.edit_output_voltage_measured.setText('N/A')

        try:
            # 6. output_current_measured
            self.edit_output_current_measured.setText(str(s2i.output_current_measured))
        except Exception as e:
            self.edit_output_current_measured.setText('N/A')

        try:
            # 7. output_current_measured_out_of_pulse
            self.edit_output_current_measured_out_of_pulse.setText(str(s2i.output_current_measured_out_of_pulse))
        except Exception as e:
            self.edit_output_current_measured_out_of_pulse.setText('N/A')

        serial_close(s2port)
        QMessageBox.about(self, '측정 완료', 'OK')

        # for i in range(10):
        #     s2_set_settings(s2port, s2s, False)
        #     s2_query_info(s2port, s2i)
        #     info((s2i.output_voltage_measured, s2i.output_current_measured))
        #     QMessageBox.about(self, '연결 테스트 중', 'voltage_measuerd :' +str(s2i.output_voltage_measured)+ ' | output_current_measured :' +str(s2i.output_voltage_measured))

        serial_close(s2port)


        # s2_serial_setup(s2port, S2_BAUD)
        #
        # s2s = S2_settings()
        # s2_query_settings(s2port, s2s)
        # s2s.output_voltage_set = 2.5
        # s2s.pulsing_mode = S2_PULSING_INTERNAL
        # s2_set_settings(s2port, s2s, False)
        #
        # s2i = S2_info()
        #
        # for i in range(10):
        #     s2_set_settings(s2port, s2s, False)
        #
        #     s2_query_info(s2port, s2i)
        #     info((s2i.output_voltage_measured, s2i.output_current_measured))
        #     QMessageBox.about(self, '연결 테스트 중', 'voltage_measuerd :' +str(s2i.output_voltage_measured)+ ' | output_current_measured :' +str(s2i.output_voltage_measured))
        #
        # serial_close(s2port)
        # QMessageBox.about(self, '연결 테스트 완료', '통신 종료')
        '''



if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        ex = MyApp()
        sys.exit(app.exec_())
    except Exception as e:
        print(e)
