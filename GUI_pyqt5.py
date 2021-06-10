#====================================================================================#
# ------------------------------ FHiRE GUI code ------------------------------------
# ----------(GAM: Filterwheel, Guide Camera, Camera focuser, ADC focusers) ---------
# --------------------------- Version: 05/17/2021 ----------------------------------
#====================================================================================#
#====================================================================================#
# -------------------------------- Imports: ----------------------------------------
#====================================================================================#
from PyQt5 import QtCore, QtWidgets, uic
from PyQt5.QtCore import QThread, pyqtSignal, Qt

import fhireGUI11  # imports PyQt design
import client  # imports basic indiclient loop

import devicewindow  # imports 

import ADCtesting as adc
import VacuumControl as vacuum
import ZWOguiding_camera as zwo

import sys
import os
import io
import time
import subprocess
import numpy as np 
import threading

# Imports GPIO stuff for focuser.
import easydriver as ed  

# Imports driver for stage. ***Disable when stage is disconnected. ***
import LTS300_1 as stage  

# Autoguiding.
from pexpect import pxssh 
#from pyraf import iraf 
from Centroid_DS9 import imexcentroid
from ReadRegions import read_region 

# xpaset os commands to communicate with DS9. http://ds9.si.edu/doc/ref/xpa.html
#====================================================================================#
#====================================================================================#
#Run IndiServer
indiserver = subprocess.Popen(["x-terminal-emulator", "-e",
			       "indiserver -v indi_asi_ccd indi_qhycfw2_wheel"])

#os.system('ds9 -geometry 636x360+447+87 &')  # set up ds9 window

# Terminal output to textBox
class EmittingStream(QtCore.QObject):
	textWritten = QtCore.pyqtSignal(str) 
	def write(self, text):
		self.textWritten.emit(str(text))

#====================================================================================#
# --------------------------- STEPPER MOTOR FUNCTIONS (FOCUSER) ----- Finished ------
#====================================================================================#
cw = False
ccw = True

stepper = ed.easydriver(12, 0.004, 32, 18, 11, 22, 0, 0, 0, 'stepper')  # focus

class FocusMotor(QtCore.QObject):
	sig_forward = pyqtSignal('PyQt_PyObject')
	sig_reverse = pyqtSignal('PyQt_PyObject')

	def __init__(self):
		super(FocusMotor, self).__init__()
		self.moving_forward = False
		self.moving_reverse = False

	def move_forward(self):
		stepper.set_direction(cw)
		self.moving_forward = True
		add = 0
		while(self.moving_forward == True):
			stepper.step()
			add += 1
			# Don't actually need to pass add, or update it. 
			# *Really? Check this.*
			self.sig_forward.emit(add)

	def move_reverse(self):
		stepper.set_direction(ccw)
		self.moving_reverse = True
		add = 0
		while(self.moving_reverse == True):
			stepper.step()
			add += 1
			self.sig_reverse.emit(add)

	def stop(self):
		self.moving_forward = False
		self.moving_reverse = False

#=====================================================================================#
# ------------------------------------ Main GUI Class -------------------------------
#=====================================================================================#
# GUI class -- inherits qt designer's .ui file's class.
class MainUiClass(QtWidgets.QMainWindow, fhireGUI11.Ui_MainWindow):
	def __init__(self, parent=None):
		super(MainUiClass, self).__init__(parent)
		# Set up inheritance for fhireGUI2 variables.
		self.setupUi(self)  

		self.exp_time = 0
		self.current_exp = 0

		self.num_exp = self.num_exp_spn.value()
		self.offset_complete = False

		# Set up files.
		self.regionpath = '/home/fhire/Desktop/GUI/Reference/regions.reg'
		self.logfile = open('/home/fhire/Desktop/GUI/Reference/Log.txt', 'w') 
		self.photlog = open('/home/fhire/Desktop/GUI/Reference/photlog.txt', 'w') 
		self.coordsfile = None 

		self.stage_connected = None
		self.stage_position = None

		# Load in saved configurations.
		self.connect_file = '/home/fhire/Desktop/FHiRE_GAM/GAMconnections.dat'
		self.settings_file = '/home/fhire/Desktop/FHiRE_GAM/GAMinfo.dat'

		self.connections = np.genfromtxt(
				self.connect_file, 
				dtype='str', 
				skip_header=1,
				delimiter='>',
				usecols=(0,1))
		self.settings = np.genfromtxt(
				self.settings_file, 
				dtype='str', 
				skip_header=1,
				delimiter='>',
				usecols=(0,1))

		# Remove trailing tabs '\t' from strings.
		for x in range(len(self.connections)):
			for y in range(len(self.connections[x])):
				self.connections[x][y] = self.connections[x][y].strip()

		for x in range(len(self.settings)):
			for y in range(len(self.settings[x])):
				self.settings[x][y] = self.settings[x][y].strip()

		print("connections: %s" %self.connections)
		print("settings: %s" %self.settings)

		# Get the index of a specific text. Might not need actually.
		# Hard code the index of each text instead?
		#testing, what = np.where(self.settings=="5Bit")	

		# Set filter names based on GAMinfo.dat.
		for x in range(7):
			self.filter_cmb.setItemText(x, self.settings[x][1])

#=====================================
# Connect MainUiClass to threads =====
#=====================================
		self.devicewindow = DeviceWindow(self)
		self.devicewindow.setup()

		# INDI client thread.
		self.client_thread = QtCore.QThread() 
		self.indi = client.IndiConnection(self.regionpath)  
		self.camerawindow = zwo.ZWOCameraWindow(self)
		self.indi.moveToThread(self.client_thread)
		self.client_thread.started.connect(self.indi.run)
		self.indi.sig_config_start.connect(self.camerawindow.updateConfig2)
		# Default filter slot.
		self.indi.sig_filter_start.connect(self.setSlot)  
		# Abort exposure.
		self.indi.sig_abort.connect(self.timeDec)  
		# Image path + last exposed image.
		self.indi.sig_path.connect(self.setPath)  
		# Start exposure updates (ie: remaining time and # exposures taken).
		self.indi.sig_exp.connect(self.timeStart)  
		self.indi.sig_mycen.connect(self.mycen)
		self.indi.sig_temp.connect(self.camerawindow.updateTemp)
		self.indi.sig_config.connect(self.camerawindow.updateConfig)
		self.indi.sig_filter.connect(self.setFilterInd)
		self.client_thread.start()

		# ADC thread
		#self.adc_thread = QtCore.QThread()
		#self.adc_motor = adc.ADCThread()
		#self.adc_motor.moveToThread(self.adc_thread)
		#self.adc_thread.started.connect(self.adc_motor.run)
		#self.adcwindow = adc.ADCTestingWindow(self)
		#self.adc_motor.sig1.connect(self.adcwindow.adc_top)
		#self.adc_motor.sig2.connect(self.adcwindow.adc_bot)
		#self.adc_thread.start()

		# Vacuum thread
		#self.vacuum_thread = QtCore.QThread()
		#self.vacuum_control = vacuum.Vacuum()
		self.vacuumwindow = vacuum.VacuumWindow(self)
		#self.vacuum_control.moveToThread(self.vacuum_thread)
		#self.vacuum_thread.started.connect(self.vacuum_control.run)
		#self.vacuum_thread.start()

		# Refractor camera thread
		#self.refractor_thread = QtCore.QThread()
		#self.refractor = Refractor()
		#self.refractor.moveToThread(self.refractor_thread)
		#self.refractor_thread.started.connect(self.refractor.run)
		#self.refractor_thread.start()

		# Claudius (terminal) thread
		#self.claudius_thread = QtCore.QThread()
		#self.claudius = Claudius() 
		#self.claudius.moveToThread(self.claudius_thread)
		#self.claudius_thread.started.connect(self.claudius.run)
		#self.claudius.signal.connect(self.setClaudiuslnk)
		#self.claudius_thread.start()

		# Focuser threads
		#self.focus_thread = QtCore.QThread()
		#self.focus_motor = FocusMotor()
		#self.focus_motor.moveToThread(self.focus_thread)
		#self.focus_motor.sig1.connect(self.cfocus_count_add)	
		#self.focus_motor.sig2.connect(self.cfocus_count_sub)	

		# Terminal thread 
		self.terminal_thread = QtCore.QThread()
		self.emitting_stream = EmittingStream()
		self.emitting_stream.moveToThread(self.terminal_thread)

		#
		# Install the custom output and error streams:
		# ** comment out stderr when troubleshooting/adding new code 
		# (if the GUI has an error preventing it from starting up, the 
		# error will not show while the stderr stream is being funneled 
		# into the GUI) **
		#
		#sys.stdout = emitting_stream(textWritten=self.normalOutputWritten)
		#sys.stderr = emitting_stream(textWritten=self.normalOutputWritten)

#=================================================
# Define widgets + connect to functionalities ====
#=================================================
		# Set refractor and spectrograph indicators to grey (not 
		# connected). *Make this more responsive.*	
		self.ref_ind.setStyleSheet("background-color: lightgrey; \
					     border: grey;")
		self.spect_ind.setStyleSheet("background-color: lightgrey; \
					      border: grey;")

		# Change filter. 
		self.filter_btn.pressed.connect(
				lambda: self.indi.change_filter(
					self.filter_cmb.currentIndex())) 
		self.filter_btn.setStyleSheet("background-color: #95fef9; \
					       outline: none;")

		# Open other windows.
		self.vacuum_btn.pressed.connect(lambda: self.vacuumwindow.show())
		self.guidingCam_btn.pressed.connect(lambda: self.camerawindow.show())
		self.device_btn.pressed.connect(lambda: self.devicewindow.show())
		self.ADC_btn.pressed.connect(lambda: self.adcwindow.show())
		self.opends9_btn.pressed.connect(self.reopenDS9)

		self.vacuum_btn.setStyleSheet("background-color: #95fef9; \
						   outline: none;")
		self.guidingCam_btn.setStyleSheet("background-color: #95fef9; \
						   outline: none;")
		self.ADC_btn.setStyleSheet("background-color: #95fef9; \
					    outline: none;")
		self.opends9_btn.setStyleSheet("background-color: #95fef9; \
						outline: none;")

		#self.TCS_btn_2.setStyleSheet("outline: none;")
		self.TCS_btn.setStyleSheet("outline: none;")
		self.brightness_btn.setStyleSheet("outline: none;")
		self.guiding_btn.setStyleSheet("outline: none;")

		# Send command to Claudius.
		self.claudius_command_lineEdit.returnPressed.connect(
				lambda: self.sendCommand(False))

		# Toggle autosaving w/ ZWO camera and autoguiding. Green/ON.
		self.autosave_btn.setCheckable(True)
		self.autosave_btn.setStyleSheet("QPushButton:unchecked{outline: none}")
		self.autosave_btn.setStyleSheet("QPushButton:checked{ \
						background-color: #b1eb34; \
						outline: none;}")

		self.autosave_btn.setText("OFF")
		self.autosave_btn.pressed.connect(lambda:self.autosaving())
		self.autosave = False
		self.autosave_btn.setToolTip("Set images to begin incrementing.")

		self.autoguiding_btn.setCheckable(True)
		self.autoguiding_btn.setStyleSheet("background-color: #c9d1d1; \
						   outline: none")
		self.autoguiding_btn.setStyleSheet("QPushButton:checked{ \
						   background-color: #b1eb34; \
						   outline: none;}") 

		self.autoguiding_btn.setText("OFF")
		self.autoguiding_btn.pressed.connect(lambda: self.autoguiding())
		self.autoguide = False
		self.autoguiding_btn.setToolTip("Set telescope to re-adjust after "
						"each exposure.\nMake sure you've "
						"sucessfully offset the target onto "
						"the fiber before beginning to "
						"autoguide.")

		# Take exposure w/ ZWO camera.
		self.exp_btn.setStyleSheet("background-color: #95fef9; \
					    outline: none;")  # blue
		self.abort_btn.setStyleSheet("background-color: #ff5c2a; \
					     outline: none;")  # red

		self.exp_btn.pressed.connect(self.take_exposure)
		# Abort exposure. 
		self.abort_btn.pressed.connect(lambda: self.indi.abort_exposure())  
		# Update number of exposures for ZWO camera.
		self.num_exp_spn.valueChanged.connect(self.updateNum) 

		# Default exposure values for ZWO camera.
		self.num_exp_spn.setValue(1)
		self.exp_prog.setValue(0)
		self.remaining_lbl2.setText("0.0s")
		self.exp_inp.setPlaceholderText("0")
		#self.exp_inp.returnPressed.connect(self.clearExp)
		self.currentexp_lbl2.setText("0/0")
		self.ref_exp_inp.setPlaceholderText("0")

		# Line edits - set Directory/Prefix.
		self.dir_inp.returnPressed.connect(self.setDirectory)
		self.prefix_inp.returnPressed.connect(self.setPrefix)

		# Default file_path + file_name for ZWO camera.
		self.file_path = "/home/fhire/Desktop"
		self.dir_inp.setPlaceholderText(self.file_path)
		self.file_name = "GAMimage"
		self.prefix_inp.setPlaceholderText(self.file_name.split(".fit")[0]
						   +"XXX.fit")

		self.offset_btn.pressed.connect(lambda: self.mycen(True))
		self.offset_btn.setStyleSheet("background-color: #95fef9; \
					       outline: none")
		self.offset_btn.setToolTip("Move telescope to place target on fiber.")

		# Take exposure w/ refractor camera.
		self.ref_exp_btn.setStyleSheet("background-color: #95fef9; \
					      outline: none;")
		self.ref_exp_btn.pressed.connect(self.refractorExposure)
		self.ref_exp_btn.pressed.connect(lambda: self.getExp('refractor camera'))
		self.ref_exp_btn.setToolTip("Refractor images saved to ~/Desktop")

		# Set default for stage indicator to not connected.
		self.stage_ind.setStyleSheet("background-color: lightgrey; \
					      border: grey;")

	# Options to disconnect/connect devices.
	def connect_ZWO(self):
		pass
	def connect_QHY(self):
		pass
	def connect_stage(self):
		if self.stage_connected == False:
			self.stage_connected = True
			# Stage move/watch thread.
			self.stage_thread = QtCore.QThread()
			self.stage_control = stage.Stage()
			self.stage_control.moveToThread(self.stage_thread)
			self.stage_thread.started.connect(self.stage_control.run)	
			self.stage_control.signal_status.connect(self.stageIndicator)
			self.stage_thread.start()

			# Radio buttons - stage.
			self.home_rb.toggled.connect(self.stage_control.moveHome)
			self.mirror_rb.toggled.connect(self.stage_control.moveMirror)
			self.splitter_rb.toggled.connect(self.stage_control.moveSplitter)
			self.mirror_rb.setChecked(True)

			print("Stage is now connected.")
		else:
			print("Stage is already connected.")

	def toggle_stage(self):
		if self.devicewindow.stage_btn.isChecked():
			self.devicewindow.stage_btn.setText("Enabled")
			temp_thread = threading.Thread(target=self.connect_stage)
		else:
			self.devicewindow.stage_btn.setText("Disabled")
			temp_thread = threading.Thread(target=self.disconnect_stage)

		temp_thread.setDaemon(True)
		temp_thread.start()

	def disconnect_stage(self):
		if self.stage_connected == True:
			self.stage_connected = False
			
			self.mirror_rb.setChecked(True)
			while self.stage_control.mirror_str not in self.stage_position:
				time.sleep(0.5)
			time.sleep(3)

			self.home_rb.toggled.connect(self.not_connected)
			self.mirror_rb.toggled.connect(self.not_connected)
			self.splitter_rb.toggled.connect(self.not_connected)

			self.stage_control.stop(False)
			self.stage_thread.quit()
			self.stage_control.deleteLater()
			self.stage_thread.deleteLater()

			print("Stage is now disconnected.")
			self.stage_ind.setStyleSheet("background-color: lightgrey; \
						      border: grey;")
		else:
			print("Stage is already disconnected.")

	def connect_ADC(self):
		pass
	def connect_refractor(self):
		pass

	def not_connected(self):
		print("Not connected.")

	def zwo_preset(self, preset):
		# First index of preset settings in self.settings.
		preset_dict = [7, 18, 29, 40, 51]
		
#==================================
# Methods to update widgets =======
#==================================	
	def take_exposure(self):
		# Set current exposure number to 0.
		self.update_i()
		# Set self.exp_time to current line edit text.
		self.getExp('guiding camera')

		# Send values to client.py to take exposure within INDI client.
		self.indi.thread(
			self.exp_time,
			self.num_exp_spn.value(),
			str(self.file_path),
			str(self.file_name),
			self.autosave,
			self.autoguide)

	# Set default filter position.
	def setSlot(self, slot):
		self.filter_cmb.setCurrentIndex(slot)

	def setFilterInd(self, busy):
		if(busy == True):
			self.filter_ind.setStyleSheet("background-color: orange;\n"
						      "border: orange;")
		elif(busy == False):
			self.filter_ind.setStyleSheet("background-color: "
						      "rgb(0, 255, 0)")

	def setClaudiuslnk(self, lnk):
		self.claudiuslnk = lnk

	# Send command to Claudius via subprocess. -- (Doesn't work -- try pxssh) 
	# **I think it does work, but double check.**
	def sendCommand(self, guiding):
		if guiding == False:
			command = str(self.claudius_command_lineEdit.text())
			self.claudius_command_lineEdit.clear()
		elif guiding == True:
			command = self.move_offset

		print("<span style=\"color:#0000ff;\"><b>observer@claudius: "
		      "</b>"+command+"</span>")
		
		self.claudiuslnk.sendline(command) 
		self.claudiuslnk.prompt()

		print("<span style=\"color:#0000ff;\">"+self.claudiuslnk.before
		      +"</span>") 

	def autosaving(self):
		if self.autosave_btn.isChecked():
			self.autosave_btn.setText("OFF")
			self.autosave = False
			print("Autosaving turned OFF")
		else:
			self.autosave_btn.setText("ON")
			self.autosave = True
			print("Autosaving turned ON")

	def autoguiding(self):
		if self.autoguiding_btn.isChecked():
			self.autoguiding_btn.setText("OFF")
			self.autoguide = False
			print("Autoguiding turned OFF")
		else:
			self.autoguiding_btn.setText("ON")
			self.autoguide = True
			print("Autoguiding turned ON")
	
	# Centroiding method for autoguiding.
	def mycen(self, offset):
		#imgpath=self.complete_path
		# Temporary path for testing.
		imgpath='/home/fhire/Desktop/GUI/GAMimage71.fit'  
		print(imgpath) 

		# Position of the optical fiber.
		os.system("xpaset -p ds9 regions command "
			  "'{point 1065 360 # point=x 20 color=red}'")
		
		# Save current ds9 regions to reg file and then read and 
		# compute centroid.
		os.system('xpaset -p ds9 regions save '+self.regionpath)
		[xcenter, ycenter] = imexcentroid(imgpath, self.regionpath)
		
		# Compute the offset and display.
		xdiff = xcenter - 1065
		ydiff = ycenter - 360

		if xdiff < 0:
			xoffset = "nn " + str(abs(int(.057 * xdiff)))
		elif xdiff >= 0:
			xoffset = "ss " + str(int(.057 * xdiff))
		if ydiff < 0:
			yoffset = "ee " + str(abs(int(.057 * ydiff)))
		elif ydiff >= 0:
			yoffset = "ww " + str(int(.057 * ydiff))	
		
		print("(%s, %s)" %(xcenter, ycenter))
		print(xoffset + " " + yoffset)

		self.move_offset = (xoffset + ";" + yoffset)
		self.sendCommand(True)

		# Offset target to fiber location to begin autoguiding.
		if offset == True:
			# Move regionbox with target.
			# **Should this be automatic like this?**
			wfile = open(self.regionpath, 'r')
			lines = wfile.readlines()
			for item in lines:
				if item.split('(')[0] == 'box':
					boxline = item.split('(')[1].split(')')[0]
					dim = boxline.split(',')
					for i in range(len(dim)):
						dim[i] = int(float(dim[i]))
					dim[0] -= xdiff
					dim[1] -= ydiff

			new = "box(%.7s,%.7s,%.7s,%.7s,%s)\n" %(
					dim[0],dim[1],dim[2],dim[3],dim[4])

			lines = [new if "box" in x else x for x in lines]

			wfile = open(self.regionpath, 'w')
			wfile.writelines(lines)
			wfile.close()				

			self.offset_complete = True

	# Updates i for exposure updates.
	def update_i(self):
		self.current_exp = 0

	# Update number of exposures variable j.
	def updateNum(self):
		self.num_exp = self.num_exp_spn.value()

	# Update remaining time, progress bar and exposure count.
	def timeStart(self, start):
		if start == True:
			self.current_exp += 1
			self.time_left = float(self.exp_time)
			self.percent_elapsed = 0
			self.qtimer = QtCore.QTimer(self)
			self.qtimer.timeout.connect(self.timeDec)
			self.qtimer.start(1000)  # 1000 msec intervals
			print("Exposure (%s) started" %self.current_exp)
		
	def timeDec(self, abort=False):
		try:
			self.time_left -= 1
		except:
			print("No exposure in progress to abort.")
			return
		self.percent_elapsed += 100 / float(self.exp_time)
		if self.time_left <= 0:
			self.qtimer.stop()
			self.exp_prog.setValue(0)
			self.remaining_lbl2.setText("0.0 s")
		elif abort == True:
			self.qtimer.stop()
			self.exp_prog.setValue(0)
			self.remaining_lbl2.setText("0.0 s")
		else:
			self.updateTxt()
	
	def updateTxt(self):
		self.num_exp = self.num_exp_spn.value()
		self.remaining_lbl2.setText(str(self.time_left)+"s")
		self.exp_prog.setValue(self.percent_elapsed)
		self.currentexp_lbl2.setText("%s/%s" %(self.current_exp, self.num_exp))

	# Non returnPressed alternative to setting exposure time.
	def getExp(self, camera):
		if camera == "guiding camera":
			self.exp_time = self.exp_inp.text()
		elif camera == "refractor camera":
			self.exp_time = self.exp_inp_2.text()
		else:
			self.exp_time = 0

	# Change format of complete path to only the image for the ds9 list:
	def setPath(self, path):
		self.complete_path = str(path)
		self.img_name = self.complete_path.split("/")[-1]
		self.last_exposed_2.setText(self.complete_path)

	def setPrefix(self):
		self.file_name
		self.file_name = self.prefix_inp.text()
		self.prefix_inp.clear()
		print("Image prefix set to: %sXXX.fit" %self.file_name)
		self.prefix_inp.setPlaceholderText(self.file_name+"XXX.fit")
		return self.file_name

	# (Add a check to make sure the directory exists. If not, prompt 
	# user to create new one.)
	def setDirectory(self):
		self.file_path
		self.file_path = self.dir_inp.text()
		self.dir_inp.clear()
		if os.path.exists(self.file_path):
			print("Directory set to: %s" %self.file_path)
			self.dir_inp.setPlaceholderText(self.file_path)
			return self.file_path

		if not os.path.exists(self.file_path):
			print("Path doesn't exist.")

	# Reopen a ds9 window if accidentally closed.
	def reopenDS9(self):
		os.system('ds9 -geometry 636x360+447+87 &')

	def refractorExposure(self):
		self.refractorthread.signal.emit([
					float(self.exp_inp_2.text()),
					str(self.file_path),
					str(self.file_name)])

	# Display modes for stage indicator.
	def stageIndicator(self, position):
		self.stage_position = position
		print("position: %s" %position)
		if position == 'busy':  # busy
			ind = "background-color: orange;\n""border: orange;"
		#
		# Stage moves home before moving anywhere else, so there's
		# a moment when moving to the mirror or beam splitter
		# where the indicator turns red. There's not actually
		# an error to be concerned about, it's result of how
		# I've set up the indicator below. Could be fixed.
		#
		elif self.stage_control.home_str in position:  # home
			if not self.home_rb.isChecked():
				ind = "background-color: rgb(255, 92, 42);\n" \
				      "border: rgb(255,92,42);"
			else:
				ind = "background-color: rgb(0, 255, 0);\n" \
				      "border: rgb(0,255,0);"
		elif self.stage_control.mirror_str in position:  # mirror
			if not self.mirror_rb.isChecked():
				ind = "background-color: rgb(255, 92, 42);\n" \
				      "border: rgb(255,92,42);"
			else:
				ind = "background-color: rgb(0, 255, 0);\n" \
				      "border: rgb(0,255,0);"
		elif self.stage_control.splitter_str in position:  # splitter
			if not self.splitter_rb.isChecked():
				ind = "background-color: rgb(255, 92, 42);\n" \
				      "border: rgb(255,92,42);"
			else:
				ind = "background-color: rgb(0, 255, 0);\n" \
				      "border: rgb(0,255,0);"
		else:  # unknown
			ind = "background-color: rgb(255, 92, 42);\n" \
			      "border: rgb(255,92,42);"

		self.stage_ind.setStyleSheet(ind)
		
	# Focus counter methods.
	def cfocus_count_add(self):
		count = int(self.cfocus_count.text())
		count += 1
		self.cfocus_count.setText(str(count))

	def cfocus_count_sub(self):
		count = int(self.cfocus_count.text())
		count -= 1
		self.cfocus_count.setText(str(count))

	# Set amount of steps -- focus stepper motors.
	def cmove(self):
		i = 0
		num = int(self.cfocus_lineEdit.text())
		if(num < 0):
			stepper.set_direction(ccw)
			while (i > num):
				stepper.step()
				i -= 1
				self.cfocus_count_sub()
		if(num > 0):
			stepper.set_direction(cw)
			while (i < num):
				stepper.step()
				i += 1
				self.cfocus_count_add()	

	# Restores sys.stdout and sys.stderr.
	def __del__(self):
		sys.stdout = sys.__stdout__
		sys.stderr = sys.__stderr__

	# Write to textBox terminal_edit.
	def normalOutputWritten(self, text):
		self.terminal_edit.append(text)

	# Events when window is closed -- replace with a shutdown button?
	def closeEvent(self, event):
		#QtWidgets.QMessageBox.setStyleSheet(self, "QLabel{color: white}")
		reply = QtWidgets.QMessageBox.question(self,
					'Window Close',
					'Are you sure you want to close the window?',
					QtWidgets.QMessageBox.Yes|
						QtWidgets.QMessageBox.No, 
					QtWidgets.QMessageBox.No)

		if reply == QtWidgets.QMessageBox.Yes:
			# **Moving the stage to mirror holds the GUI too long. 
			if self.stage_connected == True:
				#self.disconnect_stage()
				#temp_thread = threading.Thread(target=self.disconnect_stage)
				self.stage_control.stop(True)
				self.stage_thread.quit()
				self.stage_control.deleteLater()
				self.stage_thread.deleteLater()

			self.logfile.close()  
			self.photlog.close()  

			# Break "run" methods before script ends.
			self.indi.stop()
			#self.adc_motor.stop()

			# Setup threads to be deleted when script ends.
			self.client_thread.quit()
			self.indi.deleteLater()
			self.client_thread.deleteLater()

			#self.adc_thread.quit()
			#self.adc_motor.deleteLater()
			#self.adc_thread.deleteLater()
		
			#time.sleep(1)
			#print(indiserver.poll())
			#indiserver.terminate() #Doesn't work :|

			#self.claudiuslnk.logout() 
			#proc.send_signal(signal.SIGINT)

			event.accept()
			#time.sleep(5)
			print('Window Closed')
			#time.sleep(10)
		else:
			event.ignore()



#=====================================================================================#
#=====================================================================================#

class DeviceWindow(QtWidgets.QMainWindow, devicewindow.Ui_devices):
	# Widget definitions.
	def __init__(self, main):
		self.main = main

		super(DeviceWindow, self).__init__(main)
		self.setupUi(self)

		self.stage_btn.setCheckable(True)
		self.stage_btn.setStyleSheet("QPushButton:unchecked{outline: none}")
		self.stage_btn.setStyleSheet("QPushButton:checked{ \
						background-color: #b1eb34; \
						outline: none;}")

		self.stage_btn.setText("Disabled")
		self.main.stage_connected = False

		self.stage_btn.toggled.connect(self.main.toggle_stage)

	def setup(self):
		# Setup stage as connected/disconnected depending on
		# GAMconnections.dat status. 
		if self.main.connections[2][1] == '1':
			if self.stage_btn.isChecked() == False:
				self.stage_btn.toggle()
		elif self.main.connections[2][1] == '0':
			if self.stage_btn.isChecked() == True:
				self.stage_btn.toggle()


#=====================================================================================#
# ---------------------------------- Other Threads ----------------------------------
#=====================================================================================#

class Claudius(QtCore.QObject):
	signal = pyqtSignal('PyQt_PyObject')

	def __init__(self, parent=None):
		super(Claudius, self).__init__(parent)
	def run(self):
		time.sleep(1)
		start = time.time()
		lnk = pxssh.pxssh()
		hostname = '10.212.212.160'
		username = 'lia'
		password = 'Summer2k18'
		lnk.login(hostname, username, password)
		self.signal.emit(lnk)
		end = time.time()
		print("Claudius connected. Time elapsed: %.2f seconds" %(end - start))


class Refractor(QtCore.QObject):
	signal = pyqtSignal('PyQt_PyObject')

	def __init__(self, parent=None):
		super(Refractor, self).__init__(parent)
	def run(self):
		time.sleep(5)
		start = time.time()
		self.lnk = pxssh.pxssh()
		hostname = '10.212.212.46'
		username = 'fhire'
		password = 'WIROfhire17'
		self.lnk.login(hostname, username, password)
		end = time.time()
		print("Refractor RPi connected. Time "
		      "elapsed: %.2f seconds" %(end - start))

		self.signal.connect(self.take_exposure)

	def take_exposure(self, data):
		exp = data[0]; #fpath = data[1]; fname = data[2]
		fpath = "/home/fhire/Desktop/"
		fname = "RefractorImage_temp"
		ms = exp * 1000000  # time in microSec
		sleep = exp + 2

		self.lnk.sendline(self.lnk.sendline("raspistill -ISO 900 -ss %s "
					"-br 80 -co 100 -o %s.jpg" %(ms, fname)))
		print("Taking image")
		time.sleep(sleep)
		print("Image taken")
		self.lnk.sendline("scp %s.jpg fhire@10.212.212.80:%s" %(fname, fpath))
		i = self.lnk.expect("fhire@10.212.212.80\'s password:")
		if i == 0:
			print("Receiving image")
			self.lnk.sendline("WIROfhire17")
			time.sleep(3)
			print("Refractor image received")
		elif i == 1:
			print("Got the key or connect timeout")
			pass

	def stop(self):
		self.lnk.close()
		self.terminate()

#=========================================================================================#
#=========================================================================================#

# Start/Run GUI window.
if __name__ == '__main__':
	app = QtWidgets.QApplication(sys.argv)
	GUI = MainUiClass()
	GUI.show()
	app.exec_()

		
