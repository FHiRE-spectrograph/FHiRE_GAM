#==============================================================================================#
# ------------------------------ FHiRE GUI code -----------------------------------------------
# ----------(GAM: Filterwheel, Guide Camera, Camera focuser, ADC focusers) --------------------
# --------------------------- Version: 10/01/2020 ---------------------------------------------
#==============================================================================================#
#=======================================================================================#
# -------------------------------- Imports: --------------------------------------------
#=======================================================================================#
from PyQt5 import QtGui,QtCore,QtWidgets,uic
from PyQt5.QtCore import QThread,pyqtSignal

import fhireGUI11 #imports PyQt design
import filterclient #imports basic indiclient loop
import vacuumwindow #imports PyQt vacuum window
import adcwindow #imports PyQt ADC testing window
import zwocamerawindow #imports PyQt ZWO camera settings window

import sys,os,io,time,threading,PyIndi,time,datetime,struct,subprocess,signal
import astropy.io.fits as pyfits
from subprocess import Popen,call,PIPE
import numpy as np 
import pyqtgraph as pg

import easydriver as ed #imports GPIO stuff for focuser
#from LTS300 import stage #imports driver for stage ***Disable when stage is disconnected ***

# Autoguiding:
from pexpect import pxssh 
from pyraf import iraf 
from Centroid_DS9 import imexcentroid
from ReadRegions import read_region 
#=======================================================================================#
#=======================================================================================#

# Set configuration for graphics background:
pg.setConfigOption('background', 'w') 
pg.setConfigOption('foreground', 'k') 

# set configs for iraf:
iraf.prcacheOff() 
iraf.set(clobber="yes") 

#Run IndiServer
#indiserver = subprocess.Popen(["x-terminal-emulator","-e","indiserver -v indi_qhycfw2_wheel indi_asi_ccd"])

#os.system('ds9 -geometry 636x360+447+87 &') #set up ds9 window

#Terminal output to textBox
class EmittingStream(QtCore.QObject):
	textWritten = QtCore.pyqtSignal(str) 
	def write(self,text):
		self.textWritten.emit(str(text))

class VacuumWindow(QtGui.QMainWindow, vacuumwindow.Ui_VacuumWindow):
	def __init__(self, parent=None):
		super(VacuumWindow,self).__init__(parent)
		self.setupUi(self)

class ZWOCameraWindow(QtGui.QMainWindow, zwocamerawindow.Ui_ZWOcamera):
	def __init__(self, parent=None):
		super(ZWOCameraWindow,self).__init__(parent)
		self.setupUi(self)

class ADCTestingWindow(QtGui.QMainWindow, adcwindow.Ui_ADC):
	def __init__(self, parent=None):
		super(ADCTestingWindow,self).__init__(parent)
		self.setupUi(self)

#=======================================================================================#
# --------------------------- STEPPER MOTOR FUNCTIONS ----- Finished -------------------
#=======================================================================================#
cw = False
ccw = True

stepper = ed.easydriver(12, 0.004, 32, 18, 11, 22, 33, 35, 0, 'stepper')
stepper2 = ed.easydriver(13, 0.004, 32, 18, 11, 22, 37, 36, 0, 'stepper2')
stepper3 = ed.easydriver(16, 0.004, 32, 18, 11, 22, 38, 40, 0, 'stepper3')

class motor_loop1(QtCore.QObject):
	sig1 = pyqtSignal('PyQt_PyObject')
	sig2 = pyqtSignal('PyQt_PyObject')
	def __init__(self):
		super(motor_loop1, self).__init__()
		self.moving_forward = False
		self.moving_reverse = False

	def move_forward(self):
		stepper.set_direction(cw)
		self.moving_forward = True
		i = add = 0
		while (self.moving_forward == True):
			stepper.step()
			add += 1
			#don't actually need to pass add, or update it. *Really? Check this*
			self.sig1.emit(add)
			QtGui.QApplication.processEvents()

	def move_reverse(self):
		stepper.set_direction(ccw)
		self.moving_reverse = True
		i = add = 0
		while (self.moving_reverse == True):
			stepper.step()
			add += 1
			self.sig2.emit(add)
			QtGui.QApplication.processEvents()

	def stop(self):
		self.moving_forward = False
		self.moving_reverse = False

#===============================================================================================#
# ------------------------------------ Main GUI Class ------------------------------------------
#===============================================================================================#
#GUI class -- inherits qt designer's .ui file's class
class MainUiClass(QtGui.QMainWindow, fhireGUI11.Ui_MainWindow):
	def __init__(self,parent=None):
		super(MainUiClass,self).__init__(parent)
		self.setupUi(self) #this sets up inheritance for fhireGUI2 variables

		self.exp = 0
		self.current_exp = 0

		self.num_exp = self.num_exp_spn.value()
		self.offset_complete = False

		#self.setStyle(QtWidgets.QStyleFactory.create('GTK+'))

		self.vacuumwindow = VacuumWindow()
		self.adcwindow = ADCTestingWindow()
		self.camerawindow = ZWOCameraWindow()

		#Set up files:
		self.regionpath = '/home/fhire/Desktop/GUI/Reference/regions.reg'
		self.logfile = open('/home/fhire/Desktop/GUI/Reference/Log.txt', 'w') 
		self.photlog = open('/home/fhire/Desktop/GUI/Reference/photlog.txt', 'w') 
		self.coordsfile = None 

#=====================================
# Connect MainUiClass to threads =====
#=====================================
		self.threadclass = ThreadClass(self) #Client thread
		self.threadclass.start()

		self.filterthread_startup = FilterThread_Startup(self.threadclass) #Filter indicator thread
		self.filterthread_startup.start()

		self.refractorthread = Refractor()
		self.refractorthread.start()

		#Stage move/watch threads: -- [Stage not available]
		#self.moveStageThread = stage_thread()
		#self.moveLoop = stage()
		#self.moveLoop.moveToThread(self.moveStageThread)
		#self.moveStageThread.start() #Could you start it each time you need it?
		#self.watchStageThread = watchStageThread()
		#self.watchStageThread.start()

		#self.claudiusthread = Claudius() #Claudius (terminal) thread
		#self.claudiusthread.start()

		#Focus threads:
		#self.simulThread1 = thread1()
		#self.motor_loop1 = motor_loop1()
		#self.motor_loop1.moveToThread(self.simulThread1) # **** Not consistent ****

#==========================
# Terminal processes ======
#==========================
		#Terminal thread ***Inconsistent***
		self.term = termThread()
		self.EmittingStream = EmittingStream()
		self.EmittingStream.moveToThread(self.term)

		#Install the custom output and error streams:
		#** comment out stderr when troubleshooting/adding new code (if the GUI has an error preventing it from starting up, the error will not show while the stderr stream is being funneled into the GUI) **
		#sys.stdout = EmittingStream(textWritten=self.normalOutputWritten)
		#sys.stderr = EmittingStream(textWritten=self.normalOutputWritten)

#=======================================================
# Connections to emitted signals from other threads ====
#=======================================================
# Default values -------------------------------------
		self.threadclass.sig3.connect(self.setSlot) #Default filter slot

# Updating values -------------------------------------
		#Update focus counts:
		#self.motor_loop1.sig1.connect(self.cfocus_count_add)	
		#self.motor_loop1.sig2.connect(self.cfocus_count_sub)		

		#Update filter indicator
		self.filterthread_startup.signal.connect(self.setFilterInd)

		#self.watchStageThread.connect(self.stage_indicator) #Update stage indicator

# Etc signals -------------------------------------------
		self.threadclass.sig5.connect(self.time_dec) #Abort exposure

		self.threadclass.sig6.connect(self.set_path) #Image path + last exposed image
	
		self.threadclass.sig7.connect(self.time_start) #Start exposure updates (ie: remaining time and # exposures taken)
		self.threadclass.sig8.connect(self.mycen)
		
		#Claudius link
		#self.claudiusthread.signal.connect(self.setClaudiuslnk)

#=================================================
# Define widgets + connect to functionalities ====
#=================================================
		#Line edits - set Directory/Prefix:
		self.dir_inp.returnPressed.connect(self.setDirectory)
		self.prefix_inp.returnPressed.connect(self.setPrefix)

		self.claudius_command_lineEdit.returnPressed.connect(lambda: self.send_command(False)) #Line edit - send command to Claudius

		self.autosave_btn.setCheckable(True)
		self.autosave_btn.setStyleSheet("background-color: #c9d1d1")
		self.autosave_btn.setStyleSheet("QPushButton:checked {background-color: #95fef9}") #blue/ON
		self.autosave_btn.setText("OFF")
		self.autosave_btn.pressed.connect(lambda:self.autosaving())
		self.autosave = False
		self.autosave_btn.setToolTip("Set images to begin incrementing.")

		self.autoguiding_btn.setCheckable(True)
		self.autoguiding_btn.setStyleSheet("background-color: #c9d1d1")
		self.autoguiding_btn.setStyleSheet("QPushButton:checked {background-color: #95fef9}") #blue/ON
		self.autoguiding_btn.setText("OFF")
		self.autoguiding_btn.pressed.connect(lambda:self.autoguiding())
		self.autoguide = False
		self.autoguiding_btn.setToolTip("Set telescope to re-adjust after each exposure.\nMake sure you've sucessfully offset the target onto the fiber before beginning to autoguide.")

		self.opends9_btn.pressed.connect(self.reopen_ds9)

		#Radio buttons - stage:
		#self.home_rb.toggled.connect(self.moveLoop.home)
		#self.home_rb.toggled.connect(lambda: self.stage_indicator(0))
		#self.mirror_rb.toggled.connect(self.moveLoop.move_mirror)
		#self.mirror_rb.toggled.connect(lambda: self.stage_indicator(0))
		#self.splitter_rb.toggled.connect(self.moveLoop.move_splitter)
		#self.splitter_rb.toggled.connect(lambda: self.stage_indicator(0))

		self.vacuum_btn.pressed.connect(lambda: self.vacuumwindow.show())
		self.guidingCam_btn.pressed.connect(lambda: self.camerawindow.show())
		self.ADC_btn.pressed.connect(lambda: self.adcwindow.show())

		self.exp_btn.pressed.connect(lambda:self.threadclass.thread(float(self.exp_inp.text()),
			self.num_exp_spn.value(),
			str(self.file_path),
			str(self.file_name))) #Button - take exposure

		self.exp_btn.pressed.connect(self.update_i) #Update the value of i for exposure updates
		self.exp_btn.pressed.connect(lambda: self.get_exp('guiding camera'))

		self.exp_btn2.pressed.connect(self.threadclass.abort_exposure) #Abort exposure 		

		self.filter_btn.pressed.connect(lambda: self.threadclass.change_filter(self.filter_cmb.currentIndex())) #Button - filter

		self.exp_btn_2.pressed.connect(self.refractor_exposure)
		self.exp_btn_2.pressed.connect(lambda: self.get_exp('refractor camera'))
		self.exp_btn_2.setToolTip("Refractor images saved to ~/Desktop")

		self.num_exp_spn.valueChanged.connect(self.update_num) #Spinbox - Update number of exposures

		#self.filter_cmb.currentIndexChanged.connect(self.filter_names) #Update filter combobox

		#Default - stage indicator:
		self.stage_ind.setStyleSheet("background-color: orange;\n""border: orange;")
		
		#Default exposure values:
		self.num_exp_spn.setValue(1)
		self.exp_prog.setValue(0)
		self.remaining_lbl2.setText("0.0s")
		self.exp_inp.setPlaceholderText("0")
		self.exp_inp.returnPressed.connect(self.clear_exp)
		self.currentexp_lbl2.setText("0/0")

		self.exp_inp_2.setPlaceholderText("0")

		#Default file_path + file_name:
		self.file_path = "/home/fhire/Desktop"
		self.dir_inp.setPlaceholderText(self.file_path)
		self.file_name = "GAMimage"
		self.prefix_inp.setPlaceholderText(self.file_name.split(".fit")[0]+"XXX.fit")

		self.offset_btn.pressed.connect(lambda: self.mycen(True))
		self.offset_btn.setToolTip("Move telescope to place target on fiber.")

#==================================
# Methods to update widgets =======
#==================================
	def vacuumwindow(self):
		self.w = VacuumWindow()
		self.w.show()
		#self.hide()

	def refractor_exposure(self):
		self.refractorthread.signal.emit([float(self.exp_inp_2.text()),str(self.file_path),str(self.file_name)])
	
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
	
	def setClaudiuslnk(self,lnk):
		self.claudiuslnk = lnk
	
	#Display modes for stage indicator:
	def stage_indicator(self,position):
		if position == 0: #busy
			self.stage_ind.setStyleSheet("background-color: orange;\n""border: orange;")
		if position == 1: #home
			self.home_rb.setChecked(True)
			self.stage_ind.setStyleSheet("background-color: rgb(0, 255, 0);\n""border: rgb(0,255,0);")
		if position == 2: #mirror
			self.mirror_rb.setChecked(True)
			self.stage_ind.setStyleSheet("background-color: rgb(0, 255, 0);\n""border: rgb(0,255,0);")
		if position == 3: #splitter
			self.splitter_rb.setChecked(True)
			self.stage_ind.setStyleSheet("background-color: rgb(0, 255, 0);\n""border: rgb(0,255,0);")
		if position == 4: #unknown
			self.stage_ind.setStyleSheet("background-color: rgb(255, 92, 42);\n""border: rgb(255,92,42);")

	#Get complete path from Threadclass's exposing method -- updates after every exposure:
	def get_path(self):
		print(self.complete_path)

	#Change format of complete path to only the image for the ds9 list:
	def set_path(self,path):
		self.complete_path = str(path)
		self.img_name = self.complete_path.split("/")[-1]
		self.last_exposed_2.setText(self.complete_path)

	#Reopen a ds9 window if accidentally closed
	def reopen_ds9(self):
		os.system('ds9 -geometry 636x360+447+87 &')

	#Print filter names when set:
	def filter_names(self):
		filter_dict = {1:"ND 1.8", 2:"Empty", 3:"ND 3.0", 4:"Empty", 5:"V Filter", 6:"Empty",
				7:"R Filter", 8:"Empty"}
		print(filter_dict[self.filter_cmb.currentIndex])

	#Centroiding method - autoguiding:
	def mycen(self,offset):
		#imgpath=self.complete_path
		imgpath='/home/fhire/Desktop/GUI/GAMimage71.fit' #temp path for testing
		print(imgpath) 

		#position of the optical fiber
		os.system("xpaset -p ds9 regions command '{point 1065 360 # point=x 20 color=red}'")
		
		# save current ds9 regions to reg file and then read and compute centroid
		os.system('xpaset -p ds9 regions save '+self.regionpath)
		[xcenter, ycenter] = imexcentroid(imgpath, self.regionpath)
		
		# compute the offset and display
		xdiff = (xcenter)-1065
		ydiff = (ycenter)-360

		if xdiff < 0:
			xoffset = "nn "+str(abs(int(.057*xdiff)))
		elif xdiff >= 0:
			xoffset = "ss "+str(int(.057*xdiff))
		if ydiff < 0:
			yoffset = "ee "+str(abs(int(.057*ydiff)))
		elif ydiff >= 0:
			yoffset = "ww "+str(int(.057*ydiff))	
		
		print("("+str(xcenter)+","+str(ycenter)+")")
		print(xoffset+" "+yoffset)

		self.move_offset = (xoffset+";"+yoffset)
		self.send_command(True)

		#Offset target to fiber location to begin autoguiding
		if offset == True:
			#move regionbox with target **Should this be automatic like this?**
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

			new = "box(%.7s,%.7s,%.7s,%.7s,%s)\n" %(dim[0],dim[1],dim[2],dim[3],dim[4])
			lines = [new if "box" in x else x for x in lines]

			wfile = open(self.regionpath, 'w')
			wfile.writelines(lines)
			wfile.close()				

			self.offset_complete = True

	#Updates i for exposure updates:
	def update_i(self):
		self.current_exp = 0

	#Update number of exposures variable j:
	def update_num(self):
		self.num_exp = self.num_exp_spn.value()

	#Events when window is closed -- replace with a shutdown button?
	def closeEvent(self,event):
		reply = QtWidgets.QMessageBox.question(self,'Window Close','Are you sure you want to close the window?',
			QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
		if reply == QtWidgets.QMessageBox.Yes:
			self.logfile.close() #new
			self.photlog.close() #new
			self.threadclass.stop()
			self.filterthread_startup.stop()
			#self.moveStageThread.stop()
			self.refractorthread.stop()	
		
			#print(indiserver.poll())
			#indiserver.terminate() #Doesn't work :|

			#self.claudiuslnk.logout() 
		#	proc.send_signal(signal.SIGINT)
			event.accept()
			print('Window Closed')
		else:
			event.ignore()

	#Send command to Claudius via subprocess -- (Doesn't work -- try pxssh) **I think it does work, but double check**
	def send_command(self,guiding):
		if guiding == False:
			command = str(self.claudius_command_lineEdit.text())
			self.claudius_command_lineEdit.clear()
		elif guiding == True:
			command = self.move_offset

		print("<span style=\"color:#0000ff;\"><b>observer@claudius: </b>"+command+"</span>")
		
		self.claudiuslnk.sendline(command) 
		self.claudiuslnk.prompt()
		print("<span style=\"color:#0000ff;\">"+self.claudiuslnk.before+"</span>") 	

	# (Add a check to make sure the directory exists. If not, prompt user to create new one (Doesn't work).)
	def setDirectory(self):
		self.file_path
		self.file_path = self.dir_inp.text()
		self.dir_inp.clear()
		if os.path.exists(self.file_path):
			print("Directory set to: "+self.file_path)
			self.dir_inp.setPlaceholderText(self.file_path)
			return self.file_path
		if not os.path.exists(self.file_path):
			print("Path doesn't exist")
			#create_path=raw_input("Path ("+file_path+") does not exist. Create new path? Y/N")
			#if create_path==["Y","y","YES","yes"]:
			#	print("Directory created")
			#	return file_path
			#	self.dir_inp.setPlaceholderText(file_path)	

#------------------------------------------------------------------------------------#

	#Update remaining time, progress bar and exposure count:
	def time_start(self,start):
		if start == True:
			self.current_exp += 1
			self.time_left = float(self.exp)
			self.percent_elapsed = 0
			self.qtimer = QtCore.QTimer(self)
			self.qtimer.timeout.connect(self.time_dec)
			self.qtimer.start(1000) #1000 msec intervals
			print("Exposure ("+str(self.current_exp)+ ") started")
		else:
			pass
		
	def time_dec(self,abort=False):
		self.time_left -= 1
		print(str(self.time_left))
		self.percent_elapsed += 100/float(self.exp)
		if self.time_left <= 0:
			self.qtimer.stop()
			print("STOP")
			self.exp_prog.setValue(0)
			self.remaining_lbl2.setText("0.0 s")
		elif abort == True:
			self.qtimer.stop()
			self.exp_prog.setValue(0)
			self.remaining_lbl2.setText("0.0 s")
		else:
			self.update_txt()
	
	def update_txt(self):
		self.num_exp = self.num_exp_spn.value()
		self.remaining_lbl2.setText(str(self.time_left)+"s")
		self.exp_prog.setValue(self.percent_elapsed)
		self.currentexp_lbl2.setText(str(self.current_exp)+"/"+str(self.num_exp))

	#Make exposure time input more responsive -- clears text and changes placeholder:
	def clear_exp(self):
		self.exp2 = self.exp_inp.text()
		print("Set exposure time to: "+self.exp2+" seconds")
		self.exp_inp.clear()
		self.exp_inp.setPlaceholderText(self.exp2)

	#Non returnPressed alternative to setting exposure time:
	def get_exp(self, camera):
		if camera == 'guiding camera':
			self.exp = self.exp_inp.text()
		elif camera == 'refractor camera':
			self.exp = self.exp_inp_2.text()
		else:
			self.exp = 0
		
	#Set amount of steps -- focus stepper motors:
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
				
	def setPrefix(self):
		self.file_name
		self.file_name = self.prefix_inp.text()
		self.prefix_inp.clear()
		print("Image prefix set to: "+self.file_name+"XXX.fit")
		self.prefix_inp.setPlaceholderText(self.file_name+"XXX.fit")
		return self.file_name

	#Restores sys.stdout and sys.stderr:
	def __del__(self):
		sys.stdout = sys.__stdout__
		sys.stderr = sys.__stderr__

	#Write to textBox terminal_edit:
	def normalOutputWritten(self,text):
		self.terminal_edit.append(text)
		
	#Focus counter methods:
	def cfocus_count_add(self):
		count = int(self.cfocus_count.text())
		count += 1
		self.cfocus_count.setText(str(count))

	def cfocus_count_sub(self):
		count = int(self.cfocus_count.text())
		count -= 1
		self.cfocus_count.setText(str(count))

	#Set default filter position:
	def setSlot(self,slot):
		self.filter_cmb.setCurrentIndex(slot)

	def setFilterInd(self,busy):
		if(busy == True):
			self.filter_ind.setStyleSheet("background-color: orange;\n""border: orange;")
		elif(busy == False):
			self.filter_ind.setStyleSheet("background-color: rgb(0, 255, 0)")

#===============================================================================================#
#===============================================================================================#

#===============================================================================================#
# ------------------------------------ Client Thread ------------------------------------------
#===============================================================================================#
class ThreadClass(QtCore.QThread): 
	sig = [pyqtSignal(int) for i in range(7)]	
	sig1,sig2,sig3,sig4,sig5,sig7,sig8 = sig[0:]	
	sig6 = pyqtSignal(str)	
	def __init__(self,main):
		self.main = main
		super(ThreadClass,self).__init__(main)
		self.wheel = "QHYCFW2"
		self.dwheel = self.connect_dwheel = self.slot_dwheel = None

		self.camera = "ZWO CCD ASI174MM-Cool"
		self.dcamera = self.connect_dcamera = None
		self.cpower_dcamera = self.cool_dcamera = self.temp_dcamera = None
		self.binning_dcamera = self.frame_dcamera = self.frametype_dcamera = None
		self.controls_dcamera = self.bit_dcamera = None
		self.expose_dcamera = self.abort_dcamera = self.blob_dcamera = None

		#Starts an exposure progress thread
		self.p = threading.Thread(target=self.time_start)
		self.p.setDaemon(True)
		self.p.start()
#==================================================
# Connect to server, devices, indi properties =====
#==================================================

#(Do you want the extra notifications? Print statements can be uncommented. Vis versa)
	def run(self):
		#Connect to server
		start = time.time()
		time.sleep(1)
		self.indiclient = filterclient.IndiClient()
		self.indiclient.setServer("localhost",7624) 
		print("Connecting...")
		self.indiclient.connectServer() 

		#Connect to filterwheel
		time.sleep(0.5)
		self.dwheel = self.indiclient.getDevice(self.wheel)

		time.sleep(0.5)
		self.connect_dwheel = self.dwheel.getSwitch("CONNECTION")

		time.sleep(0.5)
		while not(self.dwheel.isConnected()): 
			self.connect_dwheel[0].s = filterclient.PyIndi.ISS_ON 
			self.connect_dwheel[1].s = filterclient.PyIndi.ISS_OFF
			self.indiclient.sendNewSwitch(self.connect_dwheel) 
			print("Connecting QHY CFW2-S (Filterwheel)")
			time.sleep(1)

		time.sleep(1)
		if(self.dwheel.isConnected()):
			print("Connected: QHY CFW2-S (Filterwheel)")
		if not(self.dwheel.isConnected()):
			print("Disconnected: QHY CFW2-S (Filterwheel)")

		#Connect FILTER_SLOT - filter wheel's current slot number
		self.slot_dwheel = self.dwheel.getNumber("FILTER_SLOT")
		if not(self.slot_dwheel):	
			print("property setup ERROR: FILTER_SLOT")

		#Connect to camera
		time.sleep(0.5)
		self.dcamera = self.indiclient.getDevice(self.camera)

		time.sleep(0.5)
		self.connect_dcamera = self.dcamera.getSwitch("CONNECTION")

		time.sleep(1)
		if not(self.dcamera.isConnected()): 
			self.connect_dcamera[0].s = filterclient.PyIndi.ISS_ON
			self.connect_dcamera[1].s = filterclient.PyIndi.ISS_OFF
			self.indiclient.sendNewSwitch(self.connect_dcamera) 
			print("Connecting (Guide Camera)")

		time.sleep(1)
		if(self.dcamera.isConnected()):
			print("Connected: ZWO CCD (Guide Camera)")
		if not(self.dcamera.isConnected()):
			print("Disconnected: ZWO CCD (Guide Camera)")

		#Connect CCD_COOLER - toggle cooler
		self.cool_dcamera = self.dcamera.getSwitch("CCD_COOLER")
		if not(self.cool_dcamera):	
			print("property setup ERROR: CCD_COOLER")

		#Connect CCD_CONTROLS - ?
		self.controls_dcamera = self.dcamera.getNumber("CCD_CONTROLS")
		if not(self.controls_dcamera):	
			print("property setup ERROR: CCD_CONTROLS")

		#Connect CCD_BINNING - horizontal/vertical binning
		self.binning_dcamera = self.dcamera.getNumber("CCD_BINNING")
		if not(self.binning_dcamera):
			print("property setup ERROR: CCD_BINNING")

		#Connect CCD_FRAME_TYPE - light,bias,dark,flat
		self.frametype_dcamera = self.dcamera.getSwitch("CCD_FRAME_TYPE")
		if not(self.frametype_dcamera):
			print("property setup ERROR: CCD_FRAME_TYPE")

		#Connect CCD_FRAME - frame dimensions
		self.frame_dcamera = self.dcamera.getNumber("CCD_FRAME")
		if not(self.frame_dcamera):
			print("property setup ERROR: CCD_FRAME")

		#Connect CCD_TEMPERATURE - chip temp. in Celsius
		self.temp_dcamera = self.dcamera.getNumber("CCD_TEMPERATURE")
		if not(self.temp_dcamera):	
			print("property setup ERROR: CCD_TEMPERATURE")

		#Connect CCD_EXPOSURE - seconds of exposure
		self.expose_dcamera = self.dcamera.getNumber("CCD_EXPOSURE")#def getNumber(self, name) in BaseDevice
		if not(self.expose_dcamera):	
			print("property setup ERROR: CCD_EXPOSURE")	

		#Connect CCD1 - binary fits data encoded in base64
		#Inform indi server to receive the "CCD1" blob from this device
		self.indiclient.setBLOBMode(PyIndi.B_ALSO,self.camera,"CCD1")
		time.sleep(0.5)
		self.blob_dcamera = self.dcamera.getBLOB("CCD1")
		if not(self.blob_dcamera):
			print("property setup ERROR: CCD1 -- BLOB")

		#Connect CCD_COOLER_POWER - percentage cooler power utilized
		self.cpower_dcamera = self.dcamera.getNumber("CCD_COOLER_POWER")
		if not(self.cpower_dcamera):
			print("property setup ERROR: CCD_COOLER_POWER")

		#Connect CCD_ABORT_EXPOSURE - abort CCD exposure
		self.abort_dcamera = self.dcamera.getSwitch("CCD_ABORT_EXPOSURE")	
		if not(self.abort_dcamera):
			print("property setup ERROR: CCD_ABORT_EXPOSURE")

		#Connect CCD_VIDEO_FORMAT - ?
		#**How come the bit settings are tied to the CCD video property?**
		self.bit_dcamera = self.dcamera.getSwitch("CCD_VIDEO_FORMAT")
		if not(self.bit_dcamera):
			print("property setup ERROR: CCD_VIDEO_FORMAT")
		
		#set up thread for creating the blob
		filterclient.blobEvent = threading.Event() 
		filterclient.blobEvent.clear()

		self.event = threading.Event()
		self.event.clear()

		time.sleep(1)
		end=time.time()
		print ("*** Connection process complete ***"+"\nTime elapsed: "+str('%.2f'%(end-start))+" seconds")

#========================================================
# Receive default properties and send to MainUiClass ====
#========================================================
		
		#Set cooler radiobutton default -- send current value to MainUiClass
		if(self.cool_dcamera[0].s == filterclient.PyIndi.ISS_ON):
			cool = 0
		if(self.cool_dcamera[1].s == filterclient.PyIndi.ISS_ON):
			cool = 1
		#cool = 0 if self.cool_dcamera[0].s == filterclient.PyIndi.ISS_ON else 1
		self.sig1.emit(cool)

		#Set frame type radiobutton default -- send current value to MainUiClass	
		frametype = {self.frametype_dcamera[0].s:0, self.frametype_dcamera[1].s:1, 
				self.frametype_dcamera[2].s:2, self.frametype_dcamera[3].s:3}
		for x in frametype:
			if x == filterclient.PyIndi.ISS_ON:
				typ = frametype[x]
		self.sig2.emit(typ)
	
		#Set default filter slot default value -- send current value to MainUiClass
		slot = self.slot_dwheel[0].value-1
		self.sig3.emit(slot)	

		#Set default bit value -- send current value to MainUiClass
		if(self.bit_dcamera[0].s == filterclient.PyIndi.ISS_ON):
			bit = 0
		if(self.bit_dcamera[1].s == filterclient.PyIndi.ISS_ON):
			bit = 1
		self.sig4.emit(bit)				

		while True:
			time.sleep(1) 

#==========================
# Functionalities =========
#==========================

	#Abort exposure 
	def abort_exposure(self):
		self.abort_dcamera[0].s = filterclient.PyIndi.ISS_ON
		self.indiclient.sendNewSwitch(self.abort_dcamera)
		print("Exposure aborted")
		abort = True
		self.sig5.emit(abort)

	#Retrievable method by TempThread -- Get current temperature
	def get_temp(self):
		temp = self.temp_dcamera[0].value
		return temp

	#Retrievable method by TempThread -- Get current cooler power
	def get_cooler_power(self):
		cpower = self.cpower_dcamera[0].value
		return cpower

	#Retrievable method by FilterThread -- Get status of filterwheel
	def filter_busy(self):
		busy = False
		if(self.slot_dwheel.s == filterclient.PyIndi.IPS_BUSY):
			busy = True
		if(self.slot_dwheel.s == filterclient.PyIndi.IPS_OK):
			busy = False
		return busy

	#Change filter slot 
	def change_filter(self,slot):
		self.slot_dwheel[0].value = 1 #Why do you send the wheel home each time?
		self.indiclient.sendNewNumber(self.slot_dwheel)
		self.slot_dwheel[0].value = slot+1
		self.indiclient.sendNewNumber(self.slot_dwheel)

	#Turn cooler on
	def cooler_on(self):
		self.cool_dcamera[0].s = filterclient.PyIndi.ISS_ON
		self.cool_dcamera[1].s = filterclient.PyIndi.ISS_OFF
		self.indiclient.sendNewSwitch(self.cool_dcamera)

	#Turn cooler off
	def cooler_off(self):
		self.cool_dcamera[0].s = filterclient.PyIndi.ISS_OFF
		self.cool_dcamera[1].s = filterclient.PyIndi.ISS_ON
		self.indiclient.sendNewSwitch(self.cool_dcamera)

	#Change bandwidth
	def update_band(self,band):
		self.controls_dcamera[2].value = band
		self.indiclient.sendNewNumber(self.controls_dcamera)

	#Change x binning
	def update_xbin(self,xbin):
		#print("New bin:"+str(xbin))
		self.binning_dcamera[0].value = xbin
		self.indiclient.sendNewNumber(self.controls_dcamera)

	#Change y binning
	def update_ybin(self,ybin):
		self.binning_dcamera[1].value = ybin
		self.indiclient.sendNewNumber(self.controls_dcamera)

	#Change offset
	def update_offset(self,offset):
		self.controls_dcamera[1].value = offset
		self.indiclient.sendNewNumber(self.controls_dcamera)

	#Change gain
	def update_gain(self,gain):
		self.controls_dcamera[0].value = gain
		self.indiclient.sendNewNumber(self.controls_dcamera)

	#Set bit/pixel
	def bit_eight(self):
		self.bit_dcamera[0].s = filterclient.PyIndi.ISS_ON
		self.bit_dcamera[1].s = filterclient.PyIndi.ISS_OFF
		
	def bit_sixteen(self):
		self.bit_dcamera[0].s = filterclient.PyIndi.ISS_OFF
		self.bit_dcamera[1].s = filterclient.PyIndi.ISS_ON

	#Set frametype --- (could have also passed a value)
	def frametype_light(self):
		self.frametype_dcamera[0].s = filterclient.PyIndi.ISS_ON
		self.frametype_dcamera[1].s = filterclient.PyIndi.ISS_OFF
		self.frametype_dcamera[2].s = filterclient.PyIndi.ISS_OFF
		self.frametype_dcamera[3].s = filterclient.PyIndi.ISS_OFF
		self.indiclient.sendNewSwitch(self.frametype_dcamera)

	def frametype_bias(self):
		self.frametype_dcamera[0].s = filterclient.PyIndi.ISS_OFF
		self.frametype_dcamera[1].s = filterclient.PyIndi.ISS_ON
		self.frametype_dcamera[2].s = filterclient.PyIndi.ISS_OFF
		self.frametype_dcamera[3].s = filterclient.PyIndi.ISS_OFF
		self.indiclient.sendNewSwitch(self.frametype_dcamera)


	def frametype_dark(self):
		self.frametype_dcamera[0].s = filterclient.PyIndi.ISS_OFF
		self.frametype_dcamera[1].s = filterclient.PyIndi.ISS_OFF
		self.frametype_dcamera[2].s = filterclient.PyIndi.ISS_ON
		self.frametype_dcamera[3].s = filterclient.PyIndi.ISS_OFF
		self.indiclient.sendNewSwitch(self.frametype_dcamera)


	def frametype_flat(self):
		self.frametype_dcamera[0].s = filterclient.PyIndi.ISS_OFF
		self.frametype_dcamera[1].s = filterclient.PyIndi.ISS_OFF
		self.frametype_dcamera[2].s = filterclient.PyIndi.ISS_OFF
		self.frametype_dcamera[3].s = filterclient.PyIndi.ISS_ON
		self.indiclient.sendNewSwitch(self.frametype_dcamera)
	
	#Set frame size - *Send array rather than create a function for each variable*
	def update_xposition(self,xposition):
		self.frame_dcamera[0].value = xposition
		self.indiclient.sendNewNumber(self.frame_dcamera)

	def update_yposition(self,yposition):
		self.frame_dcamera[2].value = yposition
		self.indiclient.sendNewNumber(self.frame_dcamera)

	def update_xframe(self,xframe):
		self.frame_dcamera[2].value = xframe
		self.indiclient.sendNewNumber(self.frame_dcamera)

	def update_yframe(self,yframe):
		self.frame_dcamera[3].value = yframe
		self.indiclient.sendNewNumber(self.frame_dcamera)

	#Change temperature
	def change_temp(self,temp):
		if(self.cool_dcamera[0].s == filterclient.PyIndi.ISS_OFF):
			self.cool_dcamera[0].s = filterclient.PyIndi.ISS_ON
			self.indiclient.sendNewSwitch(self.cool_dcamera)
			self.sig1.emit(cool = 0)
		self.temp_dcamera[0].value = temp
		self.indiclient.sendNewNumber(self.temp_dcamera)

	#Take exposure 
	def take_exposure(self):
		start = time.time()
		print("Beginning exposure")
	
		while(self.num_exp > 0):
			self.expose_dcamera[0].value = float(self.exp)
			self.event.set()
			self.indiclient.sendNewNumber(self.expose_dcamera)
			filterclient.blobEvent.wait()
			filterclient.blobEvent.clear()
			
			for blob in self.blob_dcamera:
				fits = blob.getblobdata()
				blobfile = io.BytesIO(fits)

				#Set image prefix and directory path
				self.complete_path = self.file_path+"/"+self.file_name+"1.fit"

				#Increment the images
				if self.main.autosave == True:
					if os.path.exists(self.complete_path): 
						expand = 1
						while True:
							expand += 1
							new_file_name = self.complete_path.split('1.fit')[0]+str(expand)+".fit"
							if os.path.exists(new_file_name):
								continue
							else:
								self.complete_path = new_file_name
								break
				elif self.main.autosave == False:
					self.complete_path = '/home/fhire/Desktop/GAMimage_temp.fit'

				with open(self.complete_path, "wb") as f:
					f.write(blobfile.getvalue())

				#Save the regions in case changed, Open new image in ds9 and overlay the saved region box **Does it replace the old image?** #Load moved region box if just completed an offset
				if self.main.offset_complete == False:
					os.system('xpaset -p ds9 regions save '+self.main.regionpath)
				os.system('xpaset -p ds9 fits '+str(self.complete_path)+' -zscale')
				os.system('xpaset -p ds9 zoom to fit')
				os.system('xpaset -p ds9 regions load '+self.main.regionpath)
				self.main.offset_complete = False

			print("Image Saved: %s" %self.complete_path)
			self.num_exp -= 1
			self.sig6.emit(self.complete_path)
			end = time.time()
			print("Total time elapsed: %.2f" %(end-start))
			QtGui.QApplication.processEvents()

			if self.main.autoguide == True:
				print("Sending to centroid")
				self.sig8.emit(False)

		print("End of exposure")
		time.sleep(1)

	#Separate exposure thread
	def thread(self,exp,num_exp,file_path,file_name):
		self.num_exp=num_exp
		self.file_path=file_path
		self.file_name=file_name
		self.exp=exp

		self.t=threading.Thread(target=self.take_exposure)
		self.t.setDaemon(True)
		print(self.t, self.t.is_alive())
		self.t.start()

	#Retrievable method by FilterThread -- status of exposure
	def exp_busy(self):
		if(self.expose_dcamera.s == filterclient.PyIndi.IPS_BUSY):
			busy = True
		elif(self.expose_dcamera.s == filterclient.PyIndi.IPS_OK):
			busy = False
		return busy

	#Update remaining time, progress bar and exposure count **Set to only update when exposing**
	def time_start(self):
		time.sleep(10)
		print("Ready to begin taking exposures")
		while 1:
			self.event.wait()
			time.sleep(0.5)
			self.event.clear()
			start = True
			self.sig7.emit(start)

	def stop(self):
		self.terminate()

#=========================================================================================#
#=========================================================================================#

#=========================================================================================#
# ---------------------------------- Other Threads ---------------------------------------
#=========================================================================================#

#For use only once at startup -- updates filter indicator and exposure countdowns
class FilterThread_Startup(QtCore.QThread):
	signal = pyqtSignal('PyQt_PyObject')
	def __init__(self,client):
		self.client = client
		super(FilterThread_Startup,self).__init__(client)
	def run(self):
		time.sleep(10)
		while 1:
			busy = self.client.filter_busy()
			self.signal.emit(busy)
			time.sleep(0.5)
	def stop(self):
		self.terminate()

class Claudius(QtCore.QThread):
	signal = pyqtSignal('PyQt_PyObject')

	def __init__(self,parent=None):
		super(Claudius,self).__init__(parent)
	def run(self):
		time.sleep(1)
		start = time.time()
		lnk = pxssh.pxssh()
		hostname = '10.212.212.160'
		username = 'lia'
		password = 'Summer2k18'
		lnk.login(hostname,username,password)
		self.signal.emit(lnk)
		end = time.time()
		print('Claudius connected. Time elapsed: '+str('%.2f'%(end-start))+" seconds")

	def stop(self):
		self.terminate()

class Refractor(QtCore.QThread):
	signal = pyqtSignal('PyQt_PyObject')

	def __init__(self,parent=None):
		super(Refractor,self).__init__(parent)
	def run(self):
		time.sleep(5)
		start = time.time()
		self.lnk = pxssh.pxssh()
		hostname = '10.212.212.46'
		username = 'fhire'
		password = 'WIROfhire17'
		self.lnk.login(hostname,username,password)
		end = time.time()
		print('Refractor RPi connected. Time elapsed: '+str('%.2f'%(end-start))+" seconds")

		self.signal.connect(self.take_exposure)

	def take_exposure(self,data):
		exp = data[0]; #fpath = data[1]; fname = data[2]
		fpath = '/home/fhire/Desktop/'
		fname = 'RefractorImage_temp'
		ms = exp*1000000 #time in microSec
		sleep = exp + 2

		self.lnk.sendline('raspistill -ISO 900 -ss %s -br 80 -co 100 -o %s.jpg' %(ms,fname))
		print("Taking image")
		time.sleep(sleep)
		print("Image taken")
		self.lnk.sendline('scp %s.jpg fhire@10.212.212.80:%s' %(fname,fpath))
		i = self.lnk.expect('fhire@10.212.212.80\'s password:')
		if i == 0:
			print("Receiving image")
			self.lnk.sendline('WIROfhire17')
			time.sleep(3)
			print("Refractor image received")
		elif i == 1:
			print("Got the key or connect timeout")
			pass

	def stop(self):
		self.lnk.close()
		self.terminate()
		

#(Maybe you should define all threads like this? Might be cleaner.)


#Define focus threads and execute
class thread1(QtCore.QThread):
	def run(self):
		self.exec_()

'''
class thread2(QtCore.QThread):
        def run(self):
                self.exec_()


class thread3(QtCore.QThread):
        def run(self):
                self.exec_()
'''

#Terminal output to textBox -- thread
class termThread(QtCore.QThread):
	def run(self):
		self.exec_()


#Stage thread that runs the movements
class stage_thread(QtCore.QThread):  
	def run(self):
		self.exec_()  


#Stage thread that watches/checks status
class watchStageThread(QtCore.QThread):
	signal = pyqtSignal('PyQt_PyObject')

	def __init__(self,parent=None):
		super(watchStageThread,self).__init__(parent)
		self.stage = stage()
	def run(self):
		#reads bytes from the stage to check position and updates the GUI     
		base_package = struct.Struct('<HHBB')
		base_package_length = base_package.size
		while 1:
			out = ''
			move_out = ''
			if base_package_length == 6:
				out += self.stage.ser.read(6)
				if out == '\x44\x04\x01\x00\x01\x50':
					print("HOME")
					position = 1 #Home			
					self.signal.emit(position)
					QtGui.QApplication.processEvents()		
                    
				elif out == '\x64\x04\x0e\x00\x81\x50':
					move_out += self.stage.ser.read(14)
					if '\x00\xC0\xF3\x00' in move_out:
						print("MIRROR")
						position = 2 #Mirror
						self.signal.emit(position)
						QtGui.QApplication.processEvents()
					elif '\x00\x40\xDB\x02' in move_out:
						print("SPLITTER")
						position = 3 #Splitter
						self.signal.emit(position)
						QtGui.QApplication.processEvents()
					else:
						print("[ERROR] Unknown position -- please send home")			
						position = 4 #Unknown
						self.signal.emit(position)
						QtGui.QApplication.processEvents()
						break
				else:
					print("[ERROR] Unknown position -- please send home")
					position = 4 #Unknown
					self.signal.emit(position)
					QtGui.QApplication.processEvents()
			time.sleep(0.5)

	def stop(self):
		self.terminate()

#=========================================================================================#
#=========================================================================================#

#Start/Run GUI window
if __name__ == '__main__':
	app = QtGui.QApplication(sys.argv)
	GUI = MainUiClass()
	GUI.show()
	app.exec_()

		
