from PyQt5 import QtGui,QtCore,QtWidgets,uic
from PyQt5.QtCore import QThread,pyqtSignal
import time

import zwocamerawindow #imports PyQt ZWO camera settings window

class ZWOCameraWindow(QtWidgets.QMainWindow, zwocamerawindow.Ui_ZWOcamera):
	def __init__(self,main):
		self.main = main
		super(ZWOCameraWindow,self).__init__(main)
		self.setupUi(self)

		self.pb_cooler.setCheckable(True)
		self.pb_cooler.setStyleSheet("background-color: #c9d1d1")
		self.pb_cooler.setText("OFF")
		self.pb_cooler.setStyleSheet("QPushButton:checked {background-color: #95fef9}")

		self.sb_binningx.setRange(0,100)
		self.sb_binningy.setRange(0,100)
		self.sb_gain.setRange(0,500)
		self.sb_offset.setRange(0,1000)
		self.sb_bandwidth.setRange(0,500)

		self.pb_cooler.pressed.connect(self.cool)
		self.sb_binningx.valueChanged.connect(self.main.threadclass.update_xbin)
		self.sb_binningy.valueChanged.connect(self.main.threadclass.update_ybin)
		self.sb_gain.valueChanged.connect(self.main.threadclass.update_gain)
		self.sb_offset.valueChanged.connect(self.main.threadclass.update_offset)
		self.sb_bandwidth.valueChanged.connect(self.main.threadclass.update_band)

		self.rb_light.toggled.connect(self.frametype)
		self.rb_dark.toggled.connect(self.frametype)
		self.rb_flat.toggled.connect(self.frametype)
		self.rb_bias.toggled.connect(self.frametype)

		self.rb_8bit.toggled.connect(self.bit)
		self.rb_16bit.toggled.connect(self.bit)

		self.ln_framex.returnPressed.connect(lambda:self.main.threadclass.update_xframe(int(self.ln_framex.text())))
		self.ln_framey.returnPressed.connect(lambda:self.main.threadclass.update_yframe(int(self.ln_framey.text())))
		self.ln_leftmost.returnPressed.connect(lambda:self.main.threadclass.update_xposition(int(self.ln_leftmost.text())))
		self.ln_topmost.returnPressed.connect(lambda:self.main.threadclass.update_yposition(int(self.ln_topmost.text())))

		self.pb_setTemp.pressed.connect(lambda:self.main.threadclass.change_temp(float(self.ln_zwoTemp.text())))

#-------------------------------------------------------------------------------#
#Add option to return press line edits? Updates placeholder text.
	def cool(self):
		if self.pb_cooler.isChecked():
			self.pb_cooler.setText("OFF")
			self.main.threadclass.cooler_toggle(False) #hopefully this works.
			print("ZWO cooler turned OFF")
		else:
			self.pb_cooler.setText("ON")
			self.main.threadclass.cooler_toggle(True)
			print("ZWO cooler turned ON")

	def bit(self):
		if self.rb_8bit.isChecked():
			self.main.threadclass.bit(8)
		elif self.rb_16bit.isChecked():
			self.main.threadclass.bit(16)

	def frametype(self):
		if self.rb_light.isChecked():
			self.main.threadclass.frametype_light()
		elif self.rb_dark.isChecked():
			self.main.threadclass.frametype_dark()
		elif self.rb_flat.isChecked():
			self.main.threadclass.frametype_flat()
		elif self.rb_bias.isChecked():
			self.main.threadclass.frametype_bias()

	def updateTemp(self,data):
		self.lbl_currentTemp_2.setText("%s C" %data[0])
		self.lbl_currentPower.setText("%s %%" %data[1])
		if data[2] == True and not self.pb_cooler.isChecked(): 
			print("Cooler on")
			self.pb_cooler.toggle()
			self.pb_cooler.setText("ON")
		elif data[2] == False and self.pb_cooler.isChecked(): 
			print("Cooler off")
			self.pb_cooler.toggle()
			self.pb_cooler.setText("OFF")
	def updateConfig(self,data):
		self.sb_binningx.setValue(data[0])
		self.sb_binningy.setValue(data[1])
		self.sb_gain.setValue(data[2])
		self.sb_offset.setValue(data[3])
		self.sb_bandwidth.setValue(data[4])

		self.ln_leftmost.setPlaceholderText(str(data[5]))
		self.ln_topmost.setPlaceholderText(str(data[6]))
		self.ln_framex.setPlaceholderText(str(data[7]))
		self.ln_framey.setPlaceholderText(str(data[8]))
	def updateConfig2(self,data):
		typ = {0:self.rb_light,1:self.rb_bias,2:self.rb_dark,3:self.rb_flat}
		typ[data[1]].setChecked(True)
		#Set bit
		if data[2] == 8: self.rb_8bit.setChecked(True)
		elif data[2] == 16: self.rb_16bit.setChecked(True)
		else: print("ERROR: Unknown bit")

#==============================================================================#

class TempThread(QtCore.QThread):
	signal = pyqtSignal('PyQt_PyObject')
	def __init__(self,client):
		self.client = client
		super(TempThread,self).__init__(client)
	def run(self):
		time.sleep(10)
		while 1:
			temp = self.client.get_temp()
			cpower = self.client.get_cooler_power()
			ctoggle = self.client.cooler_status()
			self.signal.emit([temp,cpower,ctoggle])
			time.sleep(5)

class ConfigThread(QtCore.QThread):
	signal = pyqtSignal('PyQt_PyObject')
	def __init__(self,client):
		self.client = client
		super(ConfigThread,self).__init__(client)
	def run(self):
		time.sleep(10)
		while 1:
			xbin = self.client.binning_dcamera[0].value
			ybin = self.client.binning_dcamera[1].value

			gain = self.client.controls_dcamera[0].value
			offset = self.client.controls_dcamera[1].value
			band = self.client.controls_dcamera[2].value
	
			xposition = self.client.frame_dcamera[0].value
			yposition = self.client.frame_dcamera[1].value
			xframe = self.client.frame_dcamera[2].value
			yframe = self.client.frame_dcamera[3].value

			self.signal.emit([xbin,ybin,gain,offset,band,
				xposition,yposition,xframe,yframe])

			time.sleep(0.5)
