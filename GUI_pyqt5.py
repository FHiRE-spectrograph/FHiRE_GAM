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

#os.system("x-terminal-emulator -e 'indiserver -v indi_qhycfw2_wheel indi_asi_ccd'") #Run IndiServer

#os.system('ds9 -geometry 636x360+447+87 &') #set up ds9 window

#Terminal output to textBox
class EmittingStream(QtCore.QObject):
	textWritten = QtCore.pyqtSignal(str) 
	def write(self,text):
		self.textWritten.emit(str(text))

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

class motor_loop2(QtCore.QObject):
	sig1 = pyqtSignal('PyQt_PyObject')
	sig2 = pyqtSignal('PyQt_PyObject')
	def __init__(self):
		super(motor_loop2, self).__init__()
		self.moving_forward = False
		self.moving_reverse = False

	def move_forward(self):
		stepper2.set_direction(cw)
		self.moving_forward = True
		i = add = 0
		while (self.moving_forward == True):
			stepper2.step()
			add += 1
			self.sig1.emit(add)
			QtGui.QApplication.processEvents()

	def move_reverse(self):
		stepper2.set_direction(ccw)
		self.moving_reverse = True
		i = add = 0
		while (self.moving_reverse == True):
			stepper2.step()
			add += 1
			self.sig2.emit(add)
			QtGui.QApplication.processEvents()

	def stop(self):
		self.moving_forward = False
		self.moving_reverse = False

class motor_loop3(QtCore.QObject):
	sig1 = pyqtSignal('PyQt_PyObject')
	sig2 = pyqtSignal('PyQt_PyObject')
	def __init__(self):
		super(motor_loop3, self).__init__()
		self.moving_forward = False
		self.moving_reverse = False

	def move_forward(self):
		stepper3.set_direction(cw)
		self.moving_forward = True
		i = add = 0
		while (self.moving_forward == True):
			stepper3.step()
			add += 1
			self.sig1.emit(add)
			QtGui.QApplication.processEvents()

	def move_reverse(self):
		stepper3.set_direction(ccw)
		self.moving_reverse = True
		i = add = 0
		while (self.moving_reverse == True):
			stepper3.step()
			add += 1
			self.sig2.emit(add)
			QtGui.QApplication.processEvents()

	def stop(self):
		self.moving_forward = False
		self.moving_reverse = False
#===============================================================================================#
#===============================================================================================#

#===============================================================================================#
# ------------------------------------ Main GUI Class ------------------------------------------
#===============================================================================================#
#GUI class -- inherits qt designer's .ui file's class
class MainUiClass(QtGui.QMainWindow, fhireGUI11.Ui_MainWindow):
	def __init__(self,parent=None):
		super(MainUiClass,self).__init__(parent)
		self.setupUi(self) #this sets up inheritance for fhireGUI2 variables

		self.exp = 0
		#self.num_exp = 0
		self.current_exp = 0

		self.num_exp = self.num_exp_spn.value()

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

		#self.tempthread = TempThread(self.threadclass) #Temperature update thread
		#self.tempthread.start()

		self.filterthread_startup = FilterThread_Startup(self.threadclass) #Filter indicator thread
		self.filterthread_startup.start()

		self.refractorthread = Refractor()
		self.refractorthread.start()

		#self.configthread = ConfigThread(self.threadclass) #Config thread
		#self.configthread.start()

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

		#self.simulThread2 = thread2()
		#self.motor_loop2 = motor_loop2()
		#self.motor_loop2.moveToThread(self.simulThread2)

		#self.simulThread3 = thread3()
		#self.motor_loop3 = motor_loop3()
		#self.motor_loop3.moveToThread(self.simulThread3)

#==========================
# Terminal processes ======
#==========================
		#Terminal thread ***Inconsistent***
		#self.term = termThread()
		#self.EmittingStream = EmittingStream()
		#self.EmittingStream.moveToThread(self.term)

		#Install the custom output and error streams:
		#** comment out stderr when troubleshooting/adding new code (if the GUI has an error preventing it from starting up, the error will not show while the stderr stream is being funneled into the GUI) **
		#sys.stdout = EmittingStream(textWritten=self.normalOutputWritten)
		#sys.stderr = EmittingStream(textWritten=self.normalOutputWritten)

#=======================================================
# Connections to emitted signals from other threads ====
#=======================================================
# Default values -------------------------------------
		#Default config spinbuttons:
		#self.configthread.sig1.connect(self.setBand)
		#self.configthread.sig2.connect(self.setXBin)
		#self.configthread.sig3.connect(self.setYBin)
		#self.configthread.sig4.connect(self.setOffset)
		#self.configthread.sig5.connect(self.setGain)

		#Default frame sizes:
		#self.configthread.sig6.connect(self.setXPosition)
		#self.configthread.sig7.connect(self.setYPosition)
		#self.configthread.sig8.connect(self.setXFrame)
		#self.configthread.sig9.connect(self.setYFrame)

		#self.threadclass.sig1.connect(self.setCooler) #Default cooler radiobutton
		#self.threadclass.sig2.connect(self.setFrameType) #Default frame type radiobutton
		self.threadclass.sig3.connect(self.setSlot) #Default filter slot
		#self.threadclass.sig4.connect(self.setBit) #Default bit/pix type

# Updating values -------------------------------------
		#Update focus counts:
		#self.motor_loop1.sig1.connect(self.cfocus_count_add)	
		#self.motor_loop1.sig2.connect(self.cfocus_count_sub)	
		#self.motor_loop2.sig1.connect(self.afocus1_count_add)	
		#self.motor_loop2.sig2.connect(self.afocus1_count_sub)	
		#self.motor_loop3.sig1.connect(self.afocus2_count_add)	
		#self.motor_loop3.sig2.connect(self.afocus2_count_sub)		

		#Update temperature label
		#self.tempthread.sig1.connect(self.setTemp)

		#Update cooler power
		#self.tempthread.sig2.connect(self.setCPower)

		#Update filter indicator
		self.filterthread_startup.signal.connect(self.setFilterInd)

		#self.connect(self.watchStageThread,QtCore.SIGNAL('STAGE'),self.stage_indicator) #Update stage indicator

		#self.fluxgraph.connect(self.threadclass, QtCore.SIGNAL('newFluxPoint'),self.add_point) #Update flux graph
	
# Etc signals -------------------------------------------
		self.threadclass.sig5.connect(self.time_dec) #Abort exposure

		self.threadclass.sig6.connect(self.set_path) #Image path + last exposed image
	
		self.threadclass.sig7.connect(self.time_start) #Start exposure updates (ie: remaining time and # exposures taken)
		
		#Claudius link
		#self.claudiusthread.signal.connect(self.setClaudiuslnk)


#=================================================
# Define widgets + connect to functionalities ====
#=================================================
# Line edits ------------------------------------
		#Default line edit - focus:
		#self.cfocus_lineEdit.setText(str(1))
		#self.afocus1_lineEdit.setText(str(1))
		#self.afocus2_lineEdit.setText(str(1))

		#Line edits - set Directory/Prefix:
		self.dir_inp.returnPressed.connect(self.setDirectory)
		self.prefix_inp.returnPressed.connect(self.setPrefix)

		#Line edits - frame size:
		#self.leftmost_lineEdit.returnPressed.connect(lambda:self.threadclass.update_xposition(int(self.leftmost_lineEdit.text())))
		#self.leftmost_lineEdit.returnPressed.connect(self.clear_xposition)

		#self.tpmost_lineEdit.returnPressed.connect(lambda:self.threadclass.update_yposition(int(self.tpmost_lineEdit.text())))
		#self.tpmost_lineEdit.returnPressed.connect(self.clear_yposition)

		#self.xframe_size.returnPressed.connect(lambda:self.threadclass.update_xframe(int(self.xframe_size.text())))
		#self.xframe_size.returnPressed.connect(self.clear_xframe)

		#self.yframe_size.returnPressed.connect(lambda:self.threadclass.update_yframe(int(self.yframe_size.text())))
		#self.yframe_size.returnPressed.connect(self.clear_yframe)

		self.claudius_command_lineEdit.returnPressed.connect(self.send_command) #Line edit - send command to Claudius

# Buttons ------------------------------------
		'''
		#Buttons - focus (stepper motors):
		self.cfocus_btn_add.pressed.connect(self.simulThread1.start)
		self.cfocus_btn_add.pressed.connect(self.motor_loop1.move_forward)
		self.cfocus_btn_add.released.connect(self.motor_loop1.stop)

		self.afocus1_btn_add.pressed.connect(self.simulThread2.start)
		self.afocus1_btn_add.pressed.connect(self.motor_loop2.move_forward)
		self.afocus1_btn_add.released.connect(self.motor_loop2.stop)

		self.afocus2_btn_add.pressed.connect(self.simulThread3.start)
		self.afocus2_btn_add.pressed.connect(self.motor_loop3.move_forward)
		self.afocus2_btn_add.released.connect(self.motor_loop3.stop)

		self.cfocus_btn_sub.pressed.connect(self.simulThread1.start)
		self.cfocus_btn_sub.pressed.connect(self.motor_loop1.move_reverse)
		self.cfocus_btn_sub.released.connect(self.motor_loop1.stop)

		self.afocus1_btn_sub.pressed.connect(self.simulThread2.start)
		self.afocus1_btn_sub.pressed.connect(self.motor_loop2.move_reverse)
		self.afocus1_btn_sub.released.connect(self.motor_loop2.stop)

		self.afocus2_btn_sub.pressed.connect(self.simulThread3.start)
		self.afocus2_btn_sub.pressed.connect(self.motor_loop3.move_reverse)
		self.afocus2_btn_sub.released.connect(self.motor_loop3.stop)
		'''

		self.autosave_btn.setCheckable(True)
		self.autosave_btn.setStyleSheet("background-color: #c9d1d1")
		self.autosave_btn.setStyleSheet("QPushButton:checked {background-color: #95fef9}") #blue/ON
		self.autosave_btn.setText("OFF")
		self.autosave_btn.pressed.connect(lambda:self.autosaving())
		self.autosave = False

		self.autoguiding_btn.setCheckable(True)
		self.autoguiding_btn.setStyleSheet("background-color: #c9d1d1")
		self.autoguiding_btn.setStyleSheet("QPushButton:checked {background-color: #95fef9}") #blue/ON
		self.autoguiding_btn.setText("OFF")
		self.autoguiding_btn.pressed.connect(lambda:self.autoguiding())
		self.autoguide = False

		self.opends9_btn.pressed.connect(self.reopen_ds9)

		#Buttons - 'set' focus: 
		#self.cfocus_setbtn.pressed.connect(self.cmove)
		#self.afocus1_setbtn.pressed.connect(self.amove1)
		#self.afocus2_setbtn.pressed.connect(self.amove2)

		#Button - auto save:
		#self.saving_on_rdb.toggled.connect(lambda:self.autosaving(True))
		#self.saving_off_rdb.toggled.connect(lambda:self.autosaving(False))

		#Button - temperature:
		#self.temp_setbtn.pressed.connect(lambda: self.threadclass.change_temp(float(self.temp_lineEdit.text())))
		#self.temp_setbtn.pressed.connect(self.temp_notif)
		#self.temp_lineEdit.returnPressed.connect(lambda: self.threadclass.change_temp(float(self.temp_lineEdit.text())))
		#self.temp_lineEdit.returnPressed.connect(self.temp_notif)

		#Buttons - stage:
		#self.home_btn.pressed.connect(self.moveLoop.home)
		#self.home_btn.pressed.connect(lambda:self.stage_indicator(0))
	
		#self.mirror_btn.pressed.connect(self.moveLoop.move_mirror)
		#self.mirror_btn.pressed.connect(lambda:self.stage_indicator(0))

		#self.splitter_btn.pressed.connect(self.moveLoop.move_splitter)
		#self.splitter_btn.pressed.connect(lambda:self.stage_indicator(0))

		self.exp_btn.pressed.connect(lambda:self.threadclass.thread(float(self.exp),
			self.num_exp_spn.value(),
			str(self.file_path),
			str(self.file_name),self.autosave)) #Button - take exposure

		self.exp_btn.pressed.connect(self.update_i) #Update the value of i for exposure updates

		self.exp_btn2.pressed.connect(self.threadclass.abort_exposure) #Abort exposure 		

		#self.printcen_btn.pressed.connect(self.mycen) #Button - Centroid

		self.filter_btn.pressed.connect(lambda: self.threadclass.change_filter(self.filter_cmb.currentIndex())) #Button - filter

	
		#self.exp_btn_2.pressed.connect(lambda: self.refractorthread.take_exposure(float(self.exp_inp_2.text()),str(self.file_path),str(self.file_name)))
		self.exp_btn_2.pressed.connect(self.refractor_exposure)

		#self.exp_btn_2.pressed.connect(self.update_i)
		
		#self.newds9_btn.pressed.connect(self.reopen_ds9) #Button - 'Reopen DS9'

# Radio Buttons ------------------------------------
		#Radiobuttons - frame type toggle:
		#self.frameType_rdb_light.toggled.connect(self.threadclass.frametype_light)
		#self.frameType_rdb_dark.toggled.connect(self.threadclass.frametype_dark)
		#self.frameType_rdb_bias.toggled.connect(self.threadclass.frametype_bias)
		#self.frameType_rdb_flat.toggled.connect(self.threadclass.frametype_flat)

		#Radiobuttons - Bit/pixel toggle:
		#self.eight_rdb.toggled.connect(self.threadclass.bit_eight)
		#self.sixteen_rdb.toggled.connect(self.threadclass.bit_sixteen)	

		#Radiobuttons - cooler toggle:
		#self.cooler_rdb_on.toggled.connect(self.threadclass.cooler_on)
		#self.cooler_rdb_off.toggled.connect(self.threadclass.cooler_off)

		#Default autoguiding + saving guider images: 
		#self.auto_off_rdb.setChecked(True)
		#self.saving_off_rdb.setChecked(True)

# Spin Boxes ------------------------------------
		#Spinbox ranges:
		#self.band_spn.setRange(0,500)
		#self.xbin_spinbtn.setRange(0,100)
		#self.ybin_spinbtn.setRange(0,100)
		#self.offset_spn.setRange(0,1000)
		#self.gain_spn.setRange(0,500)

 		#Spinboxes - etc CCD config:
		#self.band_spn.valueChanged.connect(self.threadclass.update_band) 
		#self.xbin_spinbtn.valueChanged.connect(self.threadclass.update_xbin)
		#self.ybin_spinbtn.valueChanged.connect(self.threadclass.update_ybin)	
		#self.offset_spn.valueChanged.connect(self.threadclass.update_offset)
		#self.gain_spn.valueChanged.connect(self.threadclass.update_gain)
		#(Add an option to input amount? -- ie pressedReturn)

		self.num_exp_spn.valueChanged.connect(self.update_num) #Spinbox - Update number of exposures

		#self.filter_cmb.currentIndexChanged.connect(self.filter_names) #Update filter combobox

# Etc widgets & Defaults ------------------------------------
		#Default - stage indicator:
		#self.stage_ind.setText("BUSY")
		self.stage_ind.setStyleSheet("background-color: orange;\n""border: orange;")
		
		#Default exposure values:
		self.num_exp_spn.setValue(1)
		self.exp_prog.setValue(0)
		self.remaining_lbl2.setText("0.0s")
		self.exp_inp.setPlaceholderText("0")
		self.exp_inp.returnPressed.connect(self.clear_exp)
		self.exp_inp.textEdited.connect(lambda: self.get_exp('guiding camera'))
		self.currentexp_lbl2.setText("0/0")

		self.exp_inp_2.textEdited.connect(lambda: self.get_exp('refractor camera'))
		self.exp_inp_2.setPlaceholderText("0")

		#Button & List - select/open image in ds9:
		#self.ds9_list.itemClicked.connect(self.set_ds9)
		#self.ds9_btn.pressed.connect(self.open_ds9)

		#Default file_path + file_name:
		self.file_path = "/home/fhire/Desktop"
		self.dir_inp.setPlaceholderText(self.file_path)
		self.file_name = "GAMimage"
		self.prefix_inp.setPlaceholderText(self.file_name.split(".fit")[0]+"XXX.fit")

# Graphs ---------------*** IN THE WORKS ***----------------------- 
		'''
		# Set up Flux Graphics
		# set up Graph attributes
		self.fluxgraph.showAxis('top', show=True)
		self.fluxgraph.showAxis('right', show=True)
		self.fluxgraph.setLabel('left', text='Average Flux')
		self.fluxgraph.setLabel('bottom', text='Time (s)')

		# set up flux graphic variables:
		self.imgnum = 1
		self.xpoints = []
		self.ypoints = []
		self.avgline = None
		self.overall_start_time = time.time()
		self.yavg = None

		self.templist = []
		#self.tempgraph.plot(self,pen=(225,0,0))
		#curve=self.tempgraph
		'''

#==================================
# Methods to update widgets =======
#==================================
	def refractor_exposure(self):
		self.refractorthread.signal.emit([float(self.exp_inp_2.text()),str(self.file_path),str(self.file_name)])
	
	def autosaving(self):
		if self.autosave_btn.isChecked():
			#print("Checked?")
			self.autosave_btn.setText("OFF")
			self.autosave = False
		else:
			#print("UnChecked?")
			self.autosave_btn.setText("ON")
			self.autosave = True

	def autoguiding(self):
		if self.autoguiding_btn.isChecked():
			self.autoguiding_btn.setText("OFF")
			self.autoguide = False
		else:
			self.autoguiding_btn.setText("ON")
			self.autoguide = True
	

	def setClaudiuslnk(self,lnk):
		self.claudiuslnk = lnk
	
	#Display modes for stage indicator:
	def stage_indicator(self,position):
		if position == 0:
			#self.stage_ind.setText("BUSY")
			self.stage_ind.setStyleSheet("background-color: orange;\n""border: orange;")
		if position == 1:
			self.stage_ind.setText("HOME")
			self.stage_ind.setStyleSheet("background-color: rgb(0, 255, 0);\n""border: rgb(0,255,0);")
		if position == 2:
			self.stage_ind.setText("MIRROR")
			self.stage_ind.setStyleSheet("background-color: rgb(0, 255, 0);\n""border: rgb(0,255,0);")
		if position == 3:
			self.stage_ind.setText("SPLITTER")
			self.stage_ind.setStyleSheet("background-color: rgb(0, 255, 0);\n""border: rgb(0,255,0);")
		if position == 4:
			self.stage_ind.setText("UNKNOWN")
			self.stage_ind.setStyleSheet("background-color: rgb(255, 92, 42);\n""border: rgb(255,92,42);")

	#Get complete path from Threadclass's exposing method -- updates after every exposure:
	def get_path(self):
		print(self.complete_path)

	#Change format of complete path to only the image for the ds9 list:
	def set_path(self,path):
		self.complete_path = str(path)
		self.img_name = self.complete_path.split("/")[-1]
		#self.ds9_list.addItem(self.img_name)
		self.last_exposed_2.setText(self.complete_path)

	#Selecting image from list saves that full image path into the variable ds9_path:
	#def set_ds9(self):
	#	self.ds9_path = str(self.complete_path).split(str(self.img_name))[0]+str(self.ds9_list.currentItem().text())

	#Open the image selected from the list in ds9 & overlay saved region box:
	def open_ds9(self):
		os.system('xpaset -p ds9 fits ' + str(self.ds9_path)+' zscale')
		os.system('xpaset -p ds9 regions load '+self.main.regionpath) 

	#Reopen a ds9 window if accidentally closed: ** Need to check if it works **
	def reopen_ds9(self):
		os.system('ds9 -geometry 636x360+447+87 &')

	#Print filter names when set:
	def filter_names(self):
		filter_dict = {1:"ND 1.8", 2:"Empty", 3:"ND 3.0", 4:"Empty", 5:"V Filter", 6:"Empty",
				7:"R Filter", 8:"Empty"}
		print(filter_dict[self.filter_cmb.currentIndex])
		'''
		if self.filter_cmb.currentIndex==1:
			print("ND 1.8")
		if self.filter_cmb.currentIndex==2:
			print("Empty")
		if self.filter_cmb.currentIndex==3:
			print("ND 3.0")
		if self.filter_cmb.currentIndex==4:
			print("Empty")
		if self.filter_cmb.currentIndex==5:
			print("V Filter")
		if self.filter_cmb.currentIndex==6:
			print("Empty")
		if self.filter_cmb.currentIndex==7:
			print("R Filter")
		if self.filter_cmb.currentIndex==8:
			print("Empty")
		'''

	#Centroiding method:
	def mycen(self):
		#imgpath=self.complete_path
		imgpath='/home/fhire/Desktop/GUI/GAMimage71.fit' #temp path for testing
		print(imgpath)

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

		self.centroid_lbl.setText("("+str(xcenter)+","+str(ycenter)+")")
		self.move_lbl_2.setText(xoffset+" "+yoffset)

	#Print set temperature when set:
	def temp_notif(self):
		print("Temperature set to "+str(self.temp_lineEdit.text())+" C")

	#Updates i for exposure updates:
	def update_i(self):
		self.current_exp = 0

	#Update number of exposures variable j:
	def update_num(self):
		self.num_exp = self.num_exp_spn.value()

#-----------------------** IN THE WORKS **------------------------------------------#
	#Events when window is closed -- replace with a shutdown button?
	def closeEvent(self,event):
		reply = QtWidgets.QMessageBox.question(self,'Window Close','Are you sure you want to close the window?',
			QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
		if reply == QtWidgets.QMessageBox.Yes:
			self.logfile.close() #new
			self.photlog.close() #new
			self.threadclass.stop()
			#self.tempthread.stop()
			self.filterthread_startup.stop()
			#self.configthread.stop()
			#self.moveStageThread.stop()
			self.refractorthread.stop()	

			#self.claudiuslnk.logout() #new
		#	self.threadclass.cooler_off
			#self.cooler_rdb_off_3.setChecked(True)
		#	proc.send_signal(signal.SIGINT)
			event.accept()
			print('Window Closed')
		else:
			event.ignore()




	#Send command to Claudius via subprocess -- (Doesn't work -- try pxssh) **I think it does work, but double check**
	def send_command(self):
		command = str(self.claudius_command_lineEdit.text())
		self.claudius_command_lineEdit.clear()
		print("<b>observer@claudius: </b>"+command)
		#new
		"""command_claudius=("ssh observer@claudius "+ command)
		command_final=command_claudius.split(" ")
		print command_final
		self.logfile.write(command_final+'\n')
		call(command_final)"""
		
		self.claudiuslnk.sendline(command) 
		self.claudiuslnk.prompt()
		print(self.claudiuslnk.before) 
 
		"""out, err=Popen(command,stdout=PIPE).communicate()
		print (out)
		self.logfile.write(out)
		self.logfile.write('\n')"""	

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

	'''
	#Add a point to intensity graphic -- new --- needs to be own thread?
	def add_point(self,f):
		# plot the latest point
		self.fluxgraph.plot([int(time.time()-self.overall_start_time)],[f],symbol='o',symbolBrush='b', symbolPen='k',symbolSize=7)
		self.xpoints.append(int(time.time()-self.overall_start_time))
		self.ypoints.append(f)
		# for the first 10 points, calculate an average and project into the future
		if self.avgline != None:		
			self.avgline.clear()
		if self.imgnum < 11:
			# only update the average if it's one of first 10 points
			self.yavg = np.mean(self.ypoints)
		self.avgline = self.fluxgraph.plot([self.xpoints[0], self.xpoints[-1]+(0.5*self.xpoints[-1])],[self.yavg, self.yavg],pen=pg.mkPen('r', width=2,  style=QtCore.Qt.DashLine))

		self.imgnum += 1
			
		# check if there's a significant change in average
		if self.imgnum > 21:
			recent_avg = np.mean(self.ypoints[-10:-1])
			if np.abs(recent_avg-self.yavg) >= 0.33*self.yavg:
				raise ValueError("Significant change in average flux; check for cloud cover or other interference")
	'''
#------------------------------------------------------------------------------------#

	#Make frame size input more responsive -- clears text and changes placeholder:
	def clear_xposition(self):
		self.leftmost_lineEdit.setPlaceholderText(self.leftmost_lineEdit.text())
		self.leftmost_lineEdit.clear()

	def clear_yposition(self):
		self.tpmost_lineEdit.setPlaceholderText(self.tpmost_lineEdit.text())
		self.tpmost_lineEdit.clear()

	def clear_xframe(self):
		self.xframe_size.setPlaceholderText(self.xframe_size.text())
		self.xframe_size.clear()

	def clear_yframe(self):
		self.yframe_size.setPlaceholderText(self.yframe_size.text())
		self.yframe_size.clear()

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
		self.exp = self.exp_inp.text()
		print("Set exposure time to: "+self.exp+" seconds")
		self.exp_inp.clear()
		self.exp_inp.setPlaceholderText(self.exp)

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
	def amove1(self):
		i = 0
		num = int(self.afocus1_lineEdit.text())
		if(num < 0):
			stepper2.set_direction(ccw)
			while (i > num):
				stepper2.step()
				i -= 1
				self.afocus1_count_sub()
		if(num > 0):
			stepper2.set_direction(cw)
			while (i < num):
				stepper2.step()
				i += 1
				self.afocus1_count_add()	

	def amove2(self):
		i = 0
		num = int(self.afocus2_lineEdit.text())
		if(num < 0):
			stepper3.set_direction(ccw)
			while (i > num):
				stepper3.step()
				i -= 1
				self.afocus2_count_sub()
		if(num > 0):
			stepper3.set_direction(cw)
			while (i < num):
				stepper3.step()
				i += 1
				self.afocus2_count_add()	

				
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

	#Set default frame size values:
	def setXPosition(self,xposition):
		self.leftmost_lineEdit.setPlaceholderText(str(xposition))
		
	def setYPosition(self,yposition):
		self.tpmost_lineEdit.setPlaceholderText(str(yposition))

	def setXFrame(self,xframe):
		self.xframe_size.setPlaceholderText(str(xframe))
		
	def setYFrame(self,yframe):
		self.yframe_size.setPlaceholderText(str(yframe))
		
	#Focus counter methods:
	def cfocus_count_add(self):
		count = int(self.cfocus_count.text())
		count += 1
		self.cfocus_count.setText(str(count))

	def cfocus_count_sub(self):
		count = int(self.cfocus_count.text())
		count -= 1
		self.cfocus_count.setText(str(count))

	def afocus1_count_add(self):
		count = int(self.afocus1_count.text())
		count += 1
		self.afocus1_count.setText(str(count))

	def afocus1_count_sub(self):
		count = int(self.afocus1_count.text())
		count -= 1
		self.afocus1_count.setText(str(count))

	def afocus2_count_add(self): 
		count = int(self.afcous2_count.text()) #**forgot to fix this object name**
		count += 1
		self.afcous2_count.setText(str(count)) 
	
	def afocus2_count_sub(self):
		count = int(self.afcous2_count.text())
		count -= 1
		self.afcous2_count.setText(str(count))

	#Set default filter position:
	def setSlot(self,slot):
		self.filter_cmb.setCurrentIndex(slot)

	#Set default checked frame type radiobutton:
	def setFrameType(self,typ):
		if typ == 0:
			self.frameType_rdb_light.setChecked(True)
		elif typ == 1:
			self.frameType_rdb_bias.setChecked(True)
		elif typ == 2:
			self.frameType_rdb_dark.setChecked(True)
		elif typ == 3:
			self.frameType_rdb_flat.setChecked(True)

	#Set default checked bit/pix radiobutton:
	def setBit(self,bit):
		if bit == 0:
			self.eight_rdb.setChecked(True)
		elif bit == 1:
			self.sixteen_rdb.setChecked(True)

	#Set default checked cooler radiobutton:
	def setCooler(self,cool):
		if cool == 0:
			self.cooler_rdb_on.setChecked(True)
		elif cool == 1:
			self.cooler_rdb_off.setChecked(True)

	#Set spinbutton default values:
	def setBand(self,band):
		self.band_spn.setValue(band)
	def setXBin(self,xbin):
		self.xbin_spinbtn.setValue(xbin)
	def setYBin(self,ybin):
		self.ybin_spinbtn.setValue(ybin)
	def setOffset(self,offset):
		self.offset_spn.setValue(offset)
	def setGain(self,gain):
		self.gain_spn.setValue(gain)

	#Update temperature and graph: -- **graph is lagging now**
	def setTemp(self,temp):
		self.ctemp_lbl2.setText(str(temp)+" C")
		self.templist.append(temp)
		self.tempgraph.plot(self.templist,pen=(255,0,0))

	#Update cooler power:
	def setCPower(self,cpower):
		self.cpower_lbl2.setText(str(cpower)+" %")

	#Update filter indicator: -- **(add one for errors?)**
	def setFilterInd(self,busy):
		if(busy == True):
			#self.filter_ind.setText("BUSY") 
			self.filter_ind.setStyleSheet("background-color: orange;\n""border: orange;")
		elif(busy == False):
			#time.sleep(1)
			#self.filter_ind.setText("OKAY")
			self.filter_ind.setStyleSheet("background-color: rgb(0, 255, 0)")

#===============================================================================================#
#===============================================================================================#

#===============================================================================================#
# ------------------------------------ Client Thread ------------------------------------------
#===============================================================================================#
class ThreadClass(QtCore.QThread): 
	sig = [pyqtSignal(int) for i in range(7)]	
	sig1,sig2,sig3,sig4,sig5,sig6,sig7 = sig[0:]		
	def __init__(self,main):
		self.main = main
		super(ThreadClass,self).__init__(main)
		#Define global variables ** Do you need to define them as None here anyways? **
		self.wheel = "QHYCFW2"
		self.dwheel = self.connect_dwheel = self.slot_dwheel = None

		self.camera = "ZWO CCD ASI174MM-Cool"
		self.dcamera = self.connect_dcamera = None
		self.cpower_dcamera = self.cool_dcamera = self.temp_dcamera = None
		self.binning_dcamera = self.frame_dcamera = self.frametype_dcamera = None
		self.controls_dcamera = self.bit_dcamera = None
		self.expose_dcamera = self.abort_dcamera = self.blob_dcamera = None
	
		#self.complete_path=None
		#self.j=None

		#Starts an exposure progress thread
		self.p = threading.Thread(target=self.time_start)
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
		while not(self.dwheel):
			self.dwheel = self.indiclient.getDevice(self.wheel)

		time.sleep(0.5)
		self.connect_dwheel = self.dwheel.getSwitch("CONNECTION")
		while not(self.connect_dwheel):
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
		while not(self.slot_dwheel):
			self.slot_dwheel = self.dwheel.getNumber("FILTER_SLOT")
		if(self.slot_dwheel):	
			print("property setup: FILTER_SLOT")

		#Connect to camera
		time.sleep(0.5)
		self.dcamera = self.indiclient.getDevice(self.camera)
		while not(self.dcamera):
			self.dcamera = self.indiclient.getDevice(self.camera)

		time.sleep(0.5)
		self.connect_dcamera = self.dcamera.getSwitch("CONNECTION")
		while not(self.connect_dcamera):
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
		while not(self.cool_dcamera):
			self.cool_dcamera = self.dcamera.getSwitch("CCD_COOLER")
		if(self.cool_dcamera):	
			print("property setup: CCD_COOLER")

		#Connect CCD_CONTROLS - ?
		self.controls_dcamera = self.dcamera.getNumber("CCD_CONTROLS")
		while not(self.controls_dcamera):
			self.controls_dcamera = self.dcamera.getNumber("CCD_CONTROLS")
		if(self.controls_dcamera):	
			print("property setup: CCD_CONTROLS")

		#Connect CCD_BINNING - horizontal/vertical binning
		self.binning_dcamera = self.dcamera.getNumber("CCD_BINNING")
		while not(self.binning_dcamera):
			self.binning_dcamera = self.dcamera.getNumber("CCD_BINNING")
		if(self.binning_dcamera):
			print("property setup: CCD_BINNING")

		#Connect CCD_FRAME_TYPE - light,bias,dark,flat
		self.frametype_dcamera = self.dcamera.getSwitch("CCD_FRAME_TYPE")
		while not(self.frametype_dcamera):
			self.frametype_dcamera = self.dcamera.getSwitch("CCD_FRAME_TYPE")
		if(self.frametype_dcamera):
			print("property setup: CCD_FRAME_TYPE")

		#Connect CCD_FRAME - frame dimensions
		self.frame_dcamera = self.dcamera.getNumber("CCD_FRAME")
		while not(self.frame_dcamera):
			self.frame_dcamera = self.dcamera.getNumber("CCD_FRAME")
		if(self.frame_dcamera):
			print("property setup: CCD_FRAME")

		#Connect CCD_TEMPERATURE - chip temp. in Celsius
		self.temp_dcamera = self.dcamera.getNumber("CCD_TEMPERATURE")
		while not(self.temp_dcamera):
			self.temp_dcamera = self.dcamera.getNumber("CCD_TEMPERATURE")
		if(self.temp_dcamera):	
			print("property setup: CCD_TEMPERATURE")

		#Connect CCD_EXPOSURE - seconds of exposure
		self.expose_dcamera = self.dcamera.getNumber("CCD_EXPOSURE")
		while not(self.expose_dcamera):
			self.expose_dcamera = self.dcamera.getNumber("CCD_EXPOSURE") #def getNumber(self, name) in BaseDevice
		if(self.expose_dcamera):	
			print("property setup: CCD_EXPOSURE")	

		#Connect CCD1 - binary fits data encoded in base64
		#Inform indi server to receive the "CCD1" blob from this device
		self.indiclient.setBLOBMode(PyIndi.B_ALSO,self.camera,"CCD1")
		time.sleep(0.5)
		self.blob_dcamera = self.dcamera.getBLOB("CCD1")
		while not(self.blob_dcamera):
			self.blob_dcamera = self.dcamera.getBLOB("CCD1")
		if(self.blob_dcamera):
			print("property setup: CCD1 -- BLOB")

		#Connect CCD_COOLER_POWER - percentage cooler power utilized
		self.cpower_dcamera = self.dcamera.getNumber("CCD_COOLER_POWER")
		while not(self.cpower_dcamera):
			self.cpower_dcamera = self.dcamera.getNumber("CCD_COOLER_POWER")
		if(self.cpower_dcamera):
			print("property setup: CCD_COOLER_POWER")

		#Connect CCD_ABORT_EXPOSURE - abort CCD exposure
		self.abort_dcamera = self.dcamera.getSwitch("CCD_ABORT_EXPOSURE")
		#while not(self.abort_dcamera):
		#	self.abort_dcamera = self.dcamera.getSwitch("CCD_ABORT_EXPOSURE")	
		if(self.abort_dcamera):
			print("property setup: CCD_ABORT_EXPOSURE")

		#Connect CCD_VIDEO_FORMAT - ?
		#**How come the bit settings are tied to the CCD video property?**
		self.bit_dcamera = self.dcamera.getSwitch("CCD_VIDEO_FORMAT")
		#while not(self.bit_dcamera):
		#	self.bit_dcamera = self.dcamera.getSwitch("CCD_VIDEO_FORMAT")
		if(self.bit_dcamera):
			print("property setup: CCD_VIDEO_FORMAT")
		
		#set up thread for creating the blob
		filterclient.blobEvent = threading.Event() 
		filterclient.blobEvent.clear()

		#self.event=threading.Event()
		#self.event.clear()

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
		
		#if(self.frametype_dcamera[0].s == filterclient.PyIndi.ISS_ON):#Returns an error? --sometimes
		#	typ=0
		#if(self.frametype_dcamera[1].s == filterclient.PyIndi.ISS_ON):
		#	typ=1
		#if(self.frametype_dcamera[2].s == filterclient.PyIndi.ISS_ON):
		#	typ=2
		#if(self.frametype_dcamera[3].s == filterclient.PyIndi.ISS_ON):
		#	typ=3
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
		#print("Indi (before): "+ str(self.slot_dwheel[0].value))
		#print(slot)
		self.slot_dwheel[0].value = slot+1
		#print("Ours: "+ str(slot+1))
		self.indiclient.sendNewNumber(self.slot_dwheel)
		#print("Indi: "+ str(self.slot_dwheel[0].value))

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

	'''
	# Get the photometry / average flux of an image -- new
	def get_phot(self, imgpath):
		iraf.noao()
		s = iraf.digiphot(Stdout=1)
		s = iraf.apphot(Stdout=1)

		s = iraf.phot(imgpath, coords="/home/fhire/Desktop/GUI/Reference/coords.txt", output="/home/fhire/Desktop/GUI/Reference/phot.txt", interactive="NO", graphics="no", verify="no", Stdout=1)

		txdump = iraf.txdump("/home/fhire/Desktop/GUI/Reference/phot.txt", "I*,XCEN,YCEN,FLUX,MAG", "yes", Stdout=1)

		#update the photlog file
		self.main.photlog.write(' '.join(txdump)+'\n')
		
		return txdump[0].split()[7]
	'''


	#Take exposure 
	def take_exposure(self):
		start = time.time()
		print("Beginning exposure: autosave")
		while(self.num_exp > 0):
			self.expose_dcamera[0].value = float(self.exp)
			#self.event.set()
			self.indiclient.sendNewNumber(self.expose_dcamera)
			filterclient.blobEvent.wait()
			filterclient.blobEvent.clear()
			for blob in self.blob_dcamera:
				fits = blob.getblobdata()
				blobfile = io.BytesIO(fits)
				#Set image prefix and directory path
				self.complete_path = self.file_path+"/"+self.file_name+"1.fit"
				#Increment the images
				if os.path.exists(self.complete_path): 
					expand = 1
					while True:
						expand += 1
						new_file_name = self.complete_path.split('1.fit')[0]+str(expand)+".fit"
						if os.path.exists(new_file_name):
							continue
						else:
							self.complete_path = new_file_name
				with open(self.complete_path, "wb") as f:
					f.write(blobfile.getvalue())

				#Save the regions in case changed, Open new image in ds9 and overlay the saved region box
				#os.system('xpaset -p ds9 regions save '+self.main.regionpath)
				#os.system('xpaset -p ds9 fits '+str(self.complete_path)+' -zscale')
				#os.system('xpaset -p ds9 regions load '+self.main.regionpath) #new
				print("Image Saved: %s" %self.complete_path)
			self.num_exp -= 1


				#------------------------------------------------------------------
				#Add the current exposure to the intensity graphic -- new
				#------------------------------------------------------------------

				#update coords.txt
				# if there is a guidebox drawn, get the centroid of that as starting coords.  If not, just use the center of the image.
				#if read_region(self.main.regionpath) != None:
				#	print("There's a region!")
				#	[xcenter2, ycenter2] = imexcentroid(self.complete_path, self.main.regionpath)
					
				#else:
					#compute the center of the frame just taken
				#	print("No region! "+str(read_region(self.main.regionpath)))
				#	hdulist1 = pyfits.open(self.complete_path)
				#	scidata1 = hdulist1[0].data
				#	[xcenter2, ycenter2] = [int(scidata1.shape[0]/2),int(scidata1.shape[1]/2)]
				#print(xcenter2,ycenter2)
				# close and reopen coordinate file so it overwrites (is there a better way to do this?)
				#self.main.coordsfile = open('/home/fhire/Desktop/GUI/Reference/coords.txt', 'w')
				#self.main.coordsfile.write(str(xcenter2)+' '+str(ycenter2))
				#self.main.coordsfile.close()

				#f = int(float(self.get_phot(self.complete_path)))
				#self.sig7.emit(QtCore.SIGNAL('newFluxPoint'),f) ##** isn't defined in main thread**	#-----------------------------------------------------------------------------------

			self.num_exp -= 1
			self.sig6.emit(self.complete_path)
			end = time.time()
			print("Total time elapsed: %.2f" %(end-start))
			QtGui.QApplication.processEvents()
		time.sleep(1)
		#self.t.terminate()

	#*There's got to be a better way to overwrite images in the main exposure method*
	def take_exposure_delete(self):
		start = time.time()
		print("Beginning exposure")
		while(self.num_exp > 0):
			self.expose_dcamera[0].value=float(self.exp)
			#self.event.set()
			self.indiclient.sendNewNumber(self.expose_dcamera)
			filterclient.blobEvent.wait()
			filterclient.blobEvent.clear()
			for blob in self.blob_dcamera:
				fits=blob.getblobdata()
				blobfile = io.BytesIO(fits)
				#Set image prefix and directory path
				self.complete_path = self.file_path+"/"+self.file_name+"_temp.fit"
				print(self.complete_path)
				#Increment the images
				#if os.path.exists(self.complete_path):
				#	os.remove(self.complete_path) 
				#	expand = 1
				#	while True:
				#		expand += 1
				#		new_file_name = self.complete_path.split('1.fit')[0]+str(expand)+".fit"
				#		print(new_file_name)
				#		if os.path.exists(new_file_name):
				#			continue
				#		else:
				#			self.complete_path = new_file_name
				with open(self.complete_path, "wb") as f:
					f.write(blobfile.getvalue())
			self.num_exp -= 1

				#update coords.txt
				# if there is a guidebox drawn, get the centroid of that as starting coords.  If not, just use the center of the image.
				#if read_region(self.main.regionpath) != None:
				#	print("There's a region!")
				#	[xcenter2, ycenter2] = imexcentroid(self.complete_path, self.main.regionpath)
					
				#else:
					#compute the center of the frame just taken
				#	print("No region! "+str(read_region(self.main.regionpath)))
				#	hdulist1 = pyfits.open(self.complete_path)
				#	scidata1 = hdulist1[0].data
				#	[xcenter2, ycenter2] = [int(scidata1.shape[0]/2),int(scidata1.shape[1]/2)]
				#print(xcenter2,ycenter2)
				# close and reopen coordinate file so it overwrites (is there a better way to do this?)
				#self.main.coordsfile = open('/home/fhire/Desktop/GUI/Reference/coords.txt', 'w')
				#self.main.coordsfile.write(str(xcenter2)+' '+str(ycenter2))
				#self.main.coordsfile.close()

				#f = int(float(self.get_phot(self.complete_path)))
				#self.emit(QtCore.SIGNAL('newFluxPoint'),f) ##*** Isn't picked up in the main thread ***
				#self.t.terminate()

	#Separate exposure thread
	def thread(self,exp,num_exp,file_path,file_name,saving):
		self.num_exp=num_exp
		self.file_path=file_path
		self.file_name=file_name
		self.exp=exp

		if saving==True:
			self.t=threading.Thread(target=self.take_exposure)
			print(self.t, self.t.is_alive())
			self.t.start()
		if saving==False:
			self.t=threading.Thread(target=self.take_exposure_delete)
			print(self.t, self.t.is_alive())
			self.t.start()


	#Make complete_path available for MainUiClass -- (Doesn't work)
	def path(self):
		return self.complete_path

	#Retrievable method by FilterThread -- status of exposure
	def exp_busy(self):
		#busy = False
		if(self.expose_dcamera.s == filterclient.PyIndi.IPS_BUSY):
			busy = True
		elif(self.expose_dcamera.s == filterclient.PyIndi.IPS_OK):
			busy = False
		return busy

	#Update remaining time, progress bar and exposure count **Set to only update when exposing**
	def time_start(self):
		time.sleep(8)
		while 1:
			#self.event.wait()
			time.sleep(0.5)
			#self.event.clear()
			#start=True
			start = True
			self.sig7.emit(start)

	def stop(self):
		#self.p.terminate()
		self.terminate()

#=========================================================================================#
#=========================================================================================#

#=========================================================================================#
# ---------------------------------- Other Threads ---------------------------------------
#=========================================================================================#

#Continuously update temperature and emit it to MainUiClass
class TempThread(QtCore.QThread):
	sig1 = pyqtSignal('PyQt_PyObject')
	sig2 = pyqtSignal('PyQt_PyObject')
	def __init__(self,client):
		self.client = client
		super(TempThread,self).__init__(client)
	def run(self):
		time.sleep(10) #*You could set this up better. Maybe with a signal at end of loading?*
		while 1:
			temp = self.client.get_temp()
			self.sig1.emit(temp)
			cpower = self.client.get_cooler_power()
			self.sig2.emit(cpower)
			time.sleep(2)

	def stop(self):
		self.terminate()

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

class ConfigThread(QtCore.QThread):
	sig=[pyqtSignal(int) for i in range(9)]	
	sig1,sig2,sig3,sig4,sig5,sig6,sig7,sig8,sig9=sig[0:]
	def __init__(self,client):
		self.client = client
		super(ConfigThread,self).__init__(client)
	def run(self):
		time.sleep(10)
		while 1:
			#Set spinbutton default values -- send current value to MainUiClass
			band = self.client.controls_dcamera[2].value
			self.sig1.emit(band)
			xbin = self.client.binning_dcamera[0].value
			self.sig2.emit(xbin)
			ybin = self.client.binning_dcamera[1].value
			self.sig3.emit(ybin)
			offset = self.client.controls_dcamera[1].value
			self.sig4.emit(offset)
			gain = self.client.controls_dcamera[0].value
			self.sig5.emit(gain)
	
			#Set default frame size placeholder text -- send current value to MainUiClass
			xposition = self.client.frame_dcamera[0].value
			self.sig6.emit(xposition)
			yposition = self.client.frame_dcamera[1].value
			self.sig7.emit(yposition)
			xframe = self.client.frame_dcamera[2].value
			self.sig8.emit(xframe)
			yframe = self.client.frame_dcamera[3].value
			self.sig9.emit(yframe)
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
		time.sleep(1)
		start = time.time()
		self.lnk = pxssh.pxssh()
		hostname = '10.212.212.46'
		username = 'fhire'
		password = 'WIROfhire17'
		self.lnk.login(hostname,username,password)
		#self.signal.emit(lnk)
		end = time.time()
		print('Refractor RPi connected. Time elapsed: '+str('%.2f'%(end-start))+" seconds")

		self.signal.connect(self.take_exposure)

	def take_exposure(self,data):
		exp = data[0]; fpath = data[1]; fname = data[2]
		ms = exp*1000000 #time in microSec
		#fname = 'refractor.jpg'
		#print(fname)
		#print(fpath)
		sleep = exp + 2
		#fname = 'refractor.jpg'

		self.lnk.sendline('raspistill -ISO 900 -ss %s -br 80 -co 100 -o %s.jpg' %(ms,fname))
		print("Taking image")
		time.sleep(sleep)
		print("Image taken")
		self.lnk.sendline('scp %s.jpg fhire@10.212.212.80:%s' %(fname,fpath))
		#print("fhire@10.212.212.80\'s password:")
		i = self.lnk.expect('fhire@10.212.212.80\'s password:')
		if i == 0:
			print("Receiving image")
			#print("Sending password")
			self.lnk.sendline('WIROfhire17')
			time.sleep(3)
			#print("Password sent")
			print("Refractor image received")
		elif i == 1:
			print("Got the key or connect timeout")
			pass

	def stop(self):
		self.lnk.close()
		self.terminate()
		

#(Maybe you should define all threads like this? Might be cleaner.)

'''
#Define focus threads and execute
class thread1(QtCore.QThread):
	def run(self):
		self.exec_()


class thread2(QtCore.QThread):
        def run(self):
                self.exec_()


class thread3(QtCore.QThread):
        def run(self):
                self.exec_()

#Terminal output to textBox -- thread
class termThread(QtCore.QThread):
	def run(self):
		self.exec_()


#Stage thread that runs the movements
class stage_thread(QtCore.QThread):  
	def run(self):
		self.exec_()  
'''

#Stage thread that watches/checks status
class watchStageThread(QtCore.QThread):
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
					self.emit(QtCore.SIGNAL('STAGE'),position)
					QtGui.QApplication.processEvents()		
                    
				elif out == '\x64\x04\x0e\x00\x81\x50':
					move_out += self.stage.ser.read(14)
					if '\x00\xC0\xF3\x00' in move_out:
						print("MIRROR")
						position = 2 #Mirror
						self.emit(QtCore.SIGNAL('STAGE'),position)
						QtGui.QApplication.processEvents()
					elif '\x00\x40\xDB\x02' in move_out:
						print("SPLITTER")
						position = 3 #Splitter
						self.emit(QtCore.SIGNAL('STAGE'),position)
						QtGui.QApplication.processEvents()
					else:
						print("[ERROR] Unknown position -- please send home")			
						position = 4 #Unknown
						self.emit(QtCore.SIGNAL('STAGE'),position)
						QtGui.QApplication.processEvents()
						break
				else:
					print("[ERROR] Unknown position -- please send home")
					position = 4 #Unknown
					self.emit(QtCore.SIGNAL('STAGE'),position)
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

		
