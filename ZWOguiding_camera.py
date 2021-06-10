from PyQt5 import QtGui,QtCore,QtWidgets,uic
from PyQt5.QtCore import QThread,pyqtSignal
import time

import zwocamerawindow  # imports PyQt ZWO camera settings window

class ZWOCameraWindow(QtWidgets.QMainWindow, zwocamerawindow.Ui_ZWOcamera):
	def __init__(self, main):
		self.main = main
		super(ZWOCameraWindow, self).__init__(main)
		self.setupUi(self)

		self.pb_cooler.setCheckable(True)
		self.pb_cooler.setStyleSheet("background-color: #c9d1d1")
		self.pb_cooler.setText("OFF")
		self.pb_cooler.setStyleSheet("QPushButton:unchecked{outline: none}")
		self.pb_cooler.setStyleSheet("QPushButton:checked{ \
					      background-color: #b1eb34; \
					      outline: none}")

		self.sb_binningx.setRange(0,100)
		self.sb_binningy.setRange(0,100)
		self.sb_gain.setRange(0,500)
		self.sb_offset.setRange(0,1000)
		self.sb_bandwidth.setRange(0,500)

		self.pb_cooler.pressed.connect(self.cool)
		self.sb_binningx.valueChanged.connect(self.main.indi.update_xbin)
		self.sb_binningy.valueChanged.connect(self.main.indi.update_ybin)
		self.sb_gain.valueChanged.connect(self.main.indi.update_gain)
		self.sb_offset.valueChanged.connect(self.main.indi.update_offset)
		self.sb_bandwidth.valueChanged.connect(self.main.indi.update_band)

		self.rb_light.toggled.connect(self.frametype)
		self.rb_dark.toggled.connect(self.frametype)
		self.rb_flat.toggled.connect(self.frametype)
		self.rb_bias.toggled.connect(self.frametype)

		self.rb_8bit.toggled.connect(self.bit)
		self.rb_16bit.toggled.connect(self.bit)

		self.ln_framex.returnPressed.connect(lambda: 
			self.main.indi.update_xframe(int(self.ln_framex.text())))
		self.ln_framey.returnPressed.connect(lambda: 
			self.main.indi.update_yframe(int(self.ln_framey.text())))
		self.ln_leftmost.returnPressed.connect(lambda: 
			self.main.indi.update_xposition(int(self.ln_leftmost.text())))
		self.ln_topmost.returnPressed.connect(lambda: 
			self.main.indi.update_yposition(int(self.ln_topmost.text())))

		self.pb_setTemp.pressed.connect(self.set_temp)

		self.preset1_btn.pressed.connect(lambda: self.zwo_preset(1))
		self.preset2_btn.pressed.connect(lambda: self.zwo_preset(2))
		self.preset3_btn.pressed.connect(lambda: self.zwo_preset(3))
		self.preset4_btn.pressed.connect(lambda: self.zwo_preset(4))
		self.preset5_btn.pressed.connect(lambda: self.zwo_preset(5))

#-------------------------------------------------------------------------------#
	# Load zwo settings from GAMinfo.dat. Currently, the option to save
	# the current zwo settings to a preset is not coded. 
	def zwo_preset(self, preset):
		#
		# 11 settings programmed. Binning-x, binning-y, gain, offset,
		# bandwidth, bit, frametype, framesize-x, framesize-y, 
		# framesize-top, and framesize-left in that order.  
		#
		preset -= 1 
		preset_dict = [7, 18, 29, 40, 51]
		index = preset_dict[preset]
		s = []
		for x in range(11):
			s.append(int(self.main.settings[x + index][1]))
		
		# Check that bit and frametype values are valid.
		if s[5] not in [8, 16]:
			print("ERROR: Invalid bit designation: %s" %s[5])
			return

		if s[6] not in [0, 1, 2, 3]:
			print("ERROR: Invalid frametype designation: %s" %s[6])
			return

		# Update xbin, ybin, gain, offset, bandwidth, left, top, x, y
		self.updateConfig([s[0], s[1],  s[2], s[3], 
				    s[4], s[10], s[9], s[7], s[8]])
		# Update cooler=None, frametype, and bit
		self.updateConfig2([None, s[6], s[5]])

	def set_temp(self):
		self.main.indi.change_temp(self.ln_zwoTemp.text())
		if self.ln_zwoTemp.text() == '':
			self.lbl_setTemp_2.setText("---------")
		else:
			self.lbl_setTemp_2.setText(self.ln_zwoTemp.text()+" C")	

	def cool(self):
		if self.pb_cooler.isChecked():
			self.pb_cooler.setText("OFF")
			self.main.indi.cooler_toggle(False)
			self.ln_zwoTemp.clear()
			self.lbl_setTemp_2.setText("---------")
		else:
			self.pb_cooler.setText("ON")
			self.main.indi.cooler_toggle(True)
			self.ln_zwoTemp.clear()
			

	def bit(self):
		if self.rb_8bit.isChecked():
			self.main.indi.bit(8)
		elif self.rb_16bit.isChecked():
			self.main.indi.bit(16)

	def frametype(self):
		if self.rb_light.isChecked():
			self.main.indi.frametype_light()
		elif self.rb_dark.isChecked():
			self.main.indi.frametype_dark()
		elif self.rb_flat.isChecked():
			self.main.indi.frametype_flat()
		elif self.rb_bias.isChecked():
			self.main.indi.frametype_bias()

	def updateTemp(self, data):
		self.lbl_currentTemp_2.setText("%s C" %data[0])
		self.lbl_currentPower.setText("%s %%" %data[1])
		if data[2] == True and not self.pb_cooler.isChecked(): 
			self.pb_cooler.toggle()
			self.pb_cooler.setText("ON")
		elif data[2] == False and self.pb_cooler.isChecked(): 
			self.pb_cooler.toggle()
			self.pb_cooler.setText("OFF")

	# Update widgets with current configuration readings.
	def updateConfig(self, data):
		self.sb_binningx.setValue(data[0])
		self.sb_binningy.setValue(data[1])
		self.sb_gain.setValue(data[2])
		self.sb_offset.setValue(data[3])
		self.sb_bandwidth.setValue(data[4])

		self.ln_leftmost.setPlaceholderText(str(data[5]))
		self.ln_topmost.setPlaceholderText(str(data[6]))
		self.ln_framex.setPlaceholderText(str(data[7]))
		self.ln_framey.setPlaceholderText(str(data[8]))

	def updateConfig2(self, data):
		typ = {0:self.rb_light, 1:self.rb_bias, 
		       2:self.rb_dark,  3:self.rb_flat}
		typ[data[1]].setChecked(True)
		# Set bit.
		if data[2] == 8: self.rb_8bit.setChecked(True)
		elif data[2] == 16: self.rb_16bit.setChecked(True)
		else: print("ERROR: Unknown bit")


