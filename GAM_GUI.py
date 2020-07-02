#==============================================================================================#
# ------------------------------ FHiRE GUI code -----------------------------------------------
# ----------(GAM: Filterwheel, Guide Camera, Camera focuser, ADC focusers) --------------------
# --------------------------- Version: 04/26/2019 ---------------------------------------------
#==============================================================================================#
#Imports:
from PyQt4 import QtGui,QtCore
import sys,os,io,time,threading,PyIndi,time,datetime,struct,subprocess,signal,math
import astropy.io.fits as pyfits
#import subprocess methods
from subprocess import Popen,call,PIPE
#datetime for graphs
from datetime import datetime
#GPIO for ADC
import RPi.GPIO as gpio
#imports PyQt design
import fhireGUI11
#imports basic indiclient loop
import filterclient
#imports GPIO stuff for focuser
import easydriver as ed
#imports driver for stage
#from LTS300 import stage
#---------------------------------------------------------------------------------------#
from pexpect import pxssh #new
from pyraf import iraf #new
import numpy as np #new
from Centroid_DS9 import imexcentroid
from ReadRegions import read_region #new
#---------------------------------------------------------------------------------------#
import pyqtgraph as pg
#=======================================================================================#
# Set configuration for graphics background
pg.setConfigOption('background', 'w') #new -- what is this doing?
pg.setConfigOption('foreground', 'k') #new
#---------------------------------------------------------------------------------------#
# set configs for iraf
iraf.prcacheOff() #new
iraf.set(clobber="yes") #new
#---------------------------------------------------------------------------------------#
#Run IndiServer
#os.system("x-terminal-emulator -e 'indiserver -v indi_qhycfw2_wheel indi_asi_ccd'")
os.system("x-terminal-emulator -e 'indiserver -v indi_qhycfw2_wheel indi_asi_ccd'")

#set up ds9 window
#os.system('ds9 -geometry 636x360+447+87 &')
#=======================================================================================#
#---------------------------SHUTTER CODE------------------------------------------------
#=======================================================================================#
#**+Need to add the second shutter too**
gpio.setmode(gpio.BOARD)
gpio.setwarnings(False)

class shutter_switch(object):
	def __init__(self,pin_out=0,name="shutter_switch"):
		self.pin_out = pin_out
		self.name = name

		gpio.setmode(gpio.BOARD)
		gpio.setwarnings(False)

		if self.pin_out > 0:
			gpio.setup(self.pin_out, gpio.OUT)
			gpio.output(self.pin_out, False)

	def open_shutter(self):
		gpio.output(self.pin_out, True)

	def close_shutter(self):
		gpio.output(self.pin_out, False)


shutter = shutter_switch(29,"shutter_switch")

#=======================================================================================#
#---------------------------ADC CODE---------------------------------------------------
#=======================================================================================#
stepper2 = ed.easydriver(13, 0.04, 32, 18, 11, 22, 0, 36, 0, 'stepper2')
stepper3 = ed.easydriver(16, 0.04, 32, 18, 11, 22, 0, 40, 0, 'stepper3')

stepper2.set_direction(True)
stepper3.set_direction(True)

top_abs = 0
bot_abs = 0

class switch(object):
	def __init__(self, pin_out=0, pin_in=0, name='switch'):
		self.pin_out = pin_out
		self.pin_in = pin_in
		gpio.setmode(gpio.BOARD)
		gpio.setwarnings(False)
		if self.pin_out > 0:
			gpio.setup(self.pin_out, gpio.OUT)
			gpio.output(self.pin_out,False)
		if self.pin_in > 0:
			gpio.setup(self.pin_in, gpio.IN)
	def pin_start(self):
		gpio.output(self.pin_out,True)
	def pin_stop(self):
		gpio.output(self.pin_out,False)

top_switch = switch(33,37)
bottom_switch = switch(35,38)

#=======================================================================================#
# --------------------------- STEPPER MOTOR FUNCTIONS ----- Finished -------------------
#=======================================================================================#
cw = False
ccw = True
stepper = ed.easydriver(12, 0.004, 32, 18, 11, 22, 33, 35, 0, 'stepper')
class motor_loop1(QtCore.QObject):
	def __init__(self):
		super(motor_loop1, self).__init__()
		self.moving_forward = False
		self.moving_reverse = False
	def move_forward(self):
		stepper.set_direction(cw)
		self.moving_forward = True
		i=0
		add=0
		while (self.moving_forward == True):
			stepper.step()
			add+=1
			#don't actually need to pass add, or update it.
			self.emit(QtCore.SIGNAL('CCOUNT_FOR'),add) 
			QtGui.QApplication.processEvents()
        def move_reverse(self):
		stepper.set_direction(ccw)
                self.moving_reverse = True
		i=0
		add=0
                while (self.moving_reverse == True):
                        stepper.step()
			add+=1
			self.emit(QtCore.SIGNAL('CCOUNT_REV'),add)
                        QtGui.QApplication.processEvents()
	def stop(self):
		self.moving_forward = False
		self.moving_reverse = False
#===============================================================================================#
#Terminal output to textBox
class EmittingStream(QtCore.QObject):
	textWritten=QtCore.pyqtSignal(str) 
	def write(self,text):
		self.textWritten.emit(str(text))
#===============================================================================================#
# ------------------------------------ Main GUI Class ------------------------------------------
#===============================================================================================#
#GUI class -- inherits qt designer's .ui file's class
class MainUiClass(QtGui.QMainWindow, fhireGUI11.Ui_MainWindow):
	def __init__(self,parent=None):
		super(MainUiClass,self).__init__(parent)
		self.setupUi(self) #this sets up inheritance for fhireGUI2 variables

		MainUiClass.telra=1
		MainUiClass.teldec=1
		MainUiClass.telhum=1
		MainUiClass.teltemp=1
		MainUiClass.telutc=1
		MainUiClass.lam=1
		MainUiClass.telhad=1
		MainUiClass.z=1
		MainUiClass.nglass=1

		#global variables -- (replace with self?)
		global exp
		global j #number of exposures
		global i #current exposure
		j=self.num_exp_spn.value()

		self.autosaving=True
		self.guiding=False

		MainUiClass.altitude=2943 #[meters]
		MainUiClass.lon=math.radians(105.977)
		MainUiClass.lat=math.radians(41.097)
#-----------------------------------------------------------------------------------------------#
		#Set up files:
		self.regionpath = '/home/fhire/Desktop/GUI/Reference/regions.reg'
		self.photlog = open('/home/fhire/Desktop/GUI/Reference/photlog.txt', 'w') 
		self.coordsfile = None 
#-----------------------------------------------------------------------------------------------#
#===============================================================================================#
# ------------------------------ Connect MainUiClass to threads ---------------------------------
#===============================================================================================#
		#Client thread
		self.threadclass=ThreadClass(self)
		self.threadclass.start()

		#Temperature update thread
		self.tempthread=TempThread(self.threadclass)
		self.tempthread.start()

		#Filter indicator thread
		self.filterthread_startup=FilterThread_Startup(self.threadclass)
		self.filterthread_startup.start()

		#Update Telinfo file from Claudius 
		self.telthread=TelUpdate()
		self.telthread.start()

		#ADC thread
		#self.adcthread=ADCThread(self)
		#self.adcthread.start()
	
		#Config thread
		self.configthread=ConfigThread(self.threadclass)
		self.configthread.start()

		#Stage move/watch threads -- [Stage not available]
		#self.moveStageThread=stage_thread()
		#self.moveLoop=stage()
		#self.moveLoop.moveToThread(self.moveStageThread)
		#self.moveStageThread.start() #Could you start it each time you need it?
		#self.watchStageThread=watchStageThread()
		#self.watchStageThread.start()

		#Claudius (terminal) thread
		self.claudiusthread=Claudius()
		self.claudiusthread.start()

		#Focus threads
		self.simulThread1 = thread1()
		self.motor_loop1 = motor_loop1()
		self.motor_loop1.moveToThread(self.simulThread1)

#=============================================================================================#
# ----------------- Connections to emitted signals from other threads ------------------------
#=============================================================================================#
		#Default config spinbutton
		self.connect(self.configthread,QtCore.SIGNAL('BAND_VAL'),self.setBand)
		self.connect(self.configthread,QtCore.SIGNAL('XBIN_VAL'),self.setXBin)
		self.connect(self.configthread,QtCore.SIGNAL('YBIN_VAL'),self.setYBin)
		self.connect(self.configthread,QtCore.SIGNAL('OFFSET_VAL'),self.setOffset)
		self.connect(self.configthread,QtCore.SIGNAL('GAIN_VAL'),self.setGain)

		#Default frame type radiobutton
		self.connect(self.threadclass,QtCore.SIGNAL('FRAME_TYPE'),self.setFrameType)

		#Default cooler radiobutton
		self.connect(self.threadclass,QtCore.SIGNAL('COOLER'),self.setCooler)

		#Default filter slot
		self.connect(self.threadclass,QtCore.SIGNAL('SLOT'),self.setSlot)
	
		#Default frame sizes
		self.connect(self.configthread,QtCore.SIGNAL('XPOSITION'),self.setXPosition)
		self.connect(self.configthread,QtCore.SIGNAL('YPOSITION'),self.setYPosition)
		self.connect(self.configthread,QtCore.SIGNAL('XFRAME'),self.setXFrame)
		self.connect(self.configthread,QtCore.SIGNAL('YFRAME'),self.setYFrame)

		#Default bit/pix type
		self.connect(self.threadclass,QtCore.SIGNAL('BITPIX'),self.setBit)

		#Replacing with Telinfo UTC time
		#self.connect(self.utcthread,QtCore.SIGNAL('CURRENT_UTC'),self.updateUTC)

		#Update temperature label
		self.connect(self.tempthread,QtCore.SIGNAL('TEMP'),self.setTemp)

		#Update cooler power
		self.connect(self.tempthread,QtCore.SIGNAL('CPOWER'),self.setCPower)

		#Update filter indicator
		self.connect(self.filterthread_startup,QtCore.SIGNAL('FILT_BUSY'),self.setFilterInd)

		#Update focus counts
		self.connect(self.motor_loop1,QtCore.SIGNAL('CCOUNT_FOR'),self.cfocus_count_add) 
		self.connect(self.motor_loop1,QtCore.SIGNAL('CCOUNT_REV'),self.cfocus_count_sub)

		#Update stage indicator
		#self.connect(self.watchStageThread,QtCore.SIGNAL('STAGE'),self.stage_indicator)
		
		#Abort exposure
		self.connect(self.threadclass,QtCore.SIGNAL('ABORT'),self.time_dec)

		#Image path + last exposed image
		self.connect(self.threadclass,QtCore.SIGNAL('PATH'),self.set_path)

		self.connect(self.threadclass,QtCore.SIGNAL('GUIDE'),self.mycen2)
	
		#Start exposure updates (ie: remaining time and number exposures taken)
		self.connect(self.threadclass,QtCore.SIGNAL('TIMER'),self.time_start)

		#self.connect(self.adcthread,QtCore.SIGNAL('ADC_top'),self.adc_top)
		#self.connect(self.adcthread,QtCore.SIGNAL('ADC_bot'),self.adc_bot)

		#Claudius link
		self.connect(self.claudiusthread,QtCore.SIGNAL('LNK'),self.setClaudiuslnk)

		#Terminal thread
		self.term=termThread()
		self.EmittingStream=EmittingStream()
		self.EmittingStream.moveToThread(self.term)
#===============================================================================================#
		#Install the custom output and error streams--comment out stderr when troubleshooting/adding new code (if the GUI has an error preventing it from starting up, the error will not show while the stderr stream is being funneled into the GUI)
		sys.stdout=EmittingStream(textWritten=self.normalOutputWritten)
		#sys.stderr=EmittingStream(textWritten=self.normalOutputWritten)

#===============================================================================================#
# --------------------------- Define widgets + connect to functionalities -----------------------
#===============================================================================================#
	#Line edit - send command to Claudius
		self.claudius_command_lineEdit.returnPressed.connect(self.send_command)

		#Radiobuttons - cooler toggle
		self.cooler_rdb_on.toggled.connect(self.threadclass.cooler_on)
		self.cooler_rdb_off.toggled.connect(self.threadclass.cooler_off)
		#Spinboxes - etc CCD config
		self.band_spn.valueChanged.connect(self.threadclass.update_band) 
		self.xbin_spinbtn.valueChanged.connect(self.threadclass.update_xbin)
		self.ybin_spinbtn.valueChanged.connect(self.threadclass.update_ybin)	
		self.offset_spn.valueChanged.connect(self.threadclass.update_offset)
		self.gain_spn.valueChanged.connect(self.threadclass.update_gain)
		#(Add an option to input amount? -- ie pressedReturn)

		#Buttons - focus (stepper motors)
		self.cfocus_btn_add.pressed.connect(self.simulThread1.start)
		self.cfocus_btn_add.pressed.connect(self.motor_loop1.move_forward)
		self.cfocus_btn_add.released.connect(self.motor_loop1.stop)

		self.cfocus_btn_sub.pressed.connect(self.simulThread1.start)
		self.cfocus_btn_sub.pressed.connect(self.motor_loop1.move_reverse)
		self.cfocus_btn_sub.released.connect(self.motor_loop1.stop)

		#Radiobuttons - frame type toggle
		self.frameType_rdb_light.toggled.connect(self.threadclass.frametype_light)
		self.frameType_rdb_dark.toggled.connect(self.threadclass.frametype_dark)
		self.frameType_rdb_bias.toggled.connect(self.threadclass.frametype_bias)
		self.frameType_rdb_flat.toggled.connect(self.threadclass.frametype_flat)

		#Radiobuttons - Bit/pixel toggle
		self.eight_rdb.toggled.connect(self.threadclass.bit_eight)
		self.sixteen_rdb.toggled.connect(self.threadclass.bit_sixteen)	

		#Default - stage indicator
		self.stage_ind.setText("BUSY")
		self.stage_ind.setStyleSheet("background-color: orange;\n""border: orange;")

		#Default - filter indicator
		self.filter_ind.setText("BUSY")
		self.filter_ind.setStyleSheet("background-color: orange;\n""border: orange;")

		#Buttons - stage
		#self.home_btn.pressed.connect(self.moveLoop.home)
		#self.home_btn.pressed.connect(lambda:self.stage_indicator(0))
	
		#self.mirror_btn.pressed.connect(self.moveLoop.move_mirror)
		#self.mirror_btn.pressed.connect(lambda:self.stage_indicator(0))

		#self.splitter_btn.pressed.connect(self.moveLoop.move_splitter)
		#self.splitter_btn.pressed.connect(lambda:self.stage_indicator(0))

		#Line edits - frame size
		self.leftmost_lineEdit.returnPressed.connect(lambda:self.threadclass.update_xposition(int(self.leftmost_lineEdit.text())))
		self.leftmost_lineEdit.returnPressed.connect(self.clear_xposition)

		self.tpmost_lineEdit.returnPressed.connect(lambda:self.threadclass.update_yposition(int(self.tpmost_lineEdit.text())))
		self.tpmost_lineEdit.returnPressed.connect(self.clear_yposition)

		self.xframe_size.returnPressed.connect(lambda:self.threadclass.update_xframe(int(self.xframe_size.text())))
		self.xframe_size.returnPressed.connect(self.clear_xframe)

		self.yframe_size.returnPressed.connect(lambda:self.threadclass.update_yframe(int(self.yframe_size.text())))
		self.yframe_size.returnPressed.connect(self.clear_yframe)

		#Spinbutton ranges
		self.band_spn.setRange(0,500)
		self.xbin_spinbtn.setRange(0,100)
		self.ybin_spinbtn.setRange(0,100)
		self.offset_spn.setRange(0,1000)
		self.gain_spn.setRange(0,500)

		#Default line edit - focus
		self.cfocus_lineEdit.setText(str(1))

		#Default file_path + file_name
		self.file_path="/home/fhire/Desktop"
		self.dir_inp.setPlaceholderText(self.file_path)
		self.file_name="GAMimage"
		self.prefix_inp.setPlaceholderText(self.file_name.split(".fit")[0]+"XXX.fit")

		#Default exposure values
		self.num_exp_spn.setValue(1)
		self.exp_prog.setValue(0)
		self.remaining_lbl2.setText("0.0s")
		self.exp_inp.setPlaceholderText("0")
		self.exp_inp.returnPressed.connect(self.clear_exp)
		self.exp_inp.textEdited.connect(self.get_exp)
		self.currentexp_lbl2.setText("0/0")

		#Default autoguiding + saving guider images
		self.auto_off_rdb.setChecked(True)
		self.saving_on_rdb.setChecked(True)

		#Update number of exposures
		self.num_exp_spn.valueChanged.connect(self.update_num)

		#Button - take exposure
		self.exp_btn.pressed.connect(lambda:self.threadclass.thread(float(exp),
			self.num_exp_spn.value(),
			str(self.file_path),
			str(self.file_name),self.guiding)
			)

		#Update the value of i for exposure updates
		self.exp_btn.pressed.connect(self.update_i)

		#Abort exposure 
		self.exp_btn2.pressed.connect(self.threadclass.abort_exposure)

		#Update filter combobox
		self.filter_cmb.currentIndexChanged.connect(self.filter_names)

		#Button - filter
		self.filter_btn.pressed.connect(lambda: self.threadclass.change_filter(self.filter_cmb.currentIndex()))
		self.filter_btn.pressed.connect(lambda:self.lamb_change(self.filter_cmb.currentIndex()))

		#Button - auto save
		self.saving_on_rdb.toggled.connect(lambda:self.autosaving(True))
		self.saving_off_rdb.toggled.connect(lambda:self.autosaving(False))

		self.auto_on_rdb.toggled.connect(lambda:self.autoguiding(True))
		self.auto_off_rdb.toggled.connect(lambda:self.autoguiding(False))

		#Button - temperature 
		self.temp_setbtn.pressed.connect(lambda: self.threadclass.change_temp(float(self.temp_lineEdit.text())))
		self.temp_setbtn.pressed.connect(self.temp_notif)
		self.temp_lineEdit.returnPressed.connect(lambda: self.threadclass.change_temp(float(self.temp_lineEdit.text())))
		self.temp_lineEdit.returnPressed.connect(self.temp_notif)

		#Add functionality to line edits --> set Directory/Prefix 
		self.dir_inp.returnPressed.connect(self.setDirectory)
		self.prefix_inp.returnPressed.connect(self.setPrefix)

		#Add functionality to focus 'set' buttons 
		self.cfocus_setbtn.pressed.connect(self.cmove)

		#Add functionality to button --> Centroid
		self.printcen_btn.pressed.connect(self.mycen)

		self.move_btn.pressed.connect(self.send_command2)

		#Add functionality to button and list --> select/open image in ds9
		self.ds9_list.itemClicked.connect(self.set_ds9)
		self.ds9_btn.pressed.connect(self.open_ds9)

		#Add functionality to 'Reopen DS9' button
		self.newds9_btn.pressed.connect(self.reopen_ds9)

		#Temporarily made to test Shutter
		self.tempgraph_save_btn.pressed.connect(self.openShutter)
		self.fluxgraph_save_btn.pressed.connect(self.closeShutter)

#-----------------------------------------------------------------------------------#
		# Set up Flux Graphics
		# set up Graph attributes
		self.fluxgraph.showAxis('top', show=True)
		self.fluxgraph.showAxis('right', show=True)
		self.fluxgraph.setLabel('left', text='Average Flux')
		self.fluxgraph.setLabel('bottom', text='Time (s)')

		#self.fluxgraph.connect(self.threadclass, QtCore.SIGNAL('newFluxPoint'), 		self.add_point)

		# set up flux graphic variables
		self.imgnum = 1
		self.xpoints = []
		self.ypoints = []
		self.avgline = None
		self.overall_start_time = time.time()
		self.yavg = None


		self.templist=[]
		#self.tempgraph.plot(self,pen=(225,0,0))
		#curve=self.tempgraph

		#Send ADC home
		self.ADC_reset_btn.pressed.connect(self.ADC_home)
#-----------------------------------------------------------------------------------#


#===============================================================================================#
#
# ------------------------- Methods to update widgets -------------------------------------------
#
#===============================================================================================#
#------------------------------------------------------------------------------------#
	def openShutter(self):
		shutter.open_shutter()
		print("Shutter Open")
	def closeShutter(self):
		shutter.close_shutter()
		print("Shutter Closed")

	def updatePosition(self):
		#Outside temperature in celsius
		self.telinfo=open("/home/fhire/Desktop/Telinfo","r")
		MainUiClass.teltemp1=self.telinfo.read().split('\n')[66][23:28]
		MainUiClass.teltemp=float(MainUiClass.teltemp1.replace('\U00002013','-'))
		#Outside humidity --- in percentage ***NEEDS TO BE IN mmhg***
		self.telinfo=open("/home/fhire/Desktop/Telinfo","r")
		MainUiClass.telhum=float(self.telinfo.read().split('\n')[71][24:28])
		#Hour Angle in degress
		self.telinfo=open("/home/fhire/Desktop/Telinfo","r")	
		MainUiClass.telhad=float(self.telinfo.read().split('\n')[41][23:31])
		#RA in hour:minute:seconds
		self.telinfo=open("/home/fhire/Desktop/Telinfo","r")
		MainUiClass.telra=self.telinfo.read().split('\n')[26][23:34] 
		#Current UTC 	
		self.telinfo=open("/home/fhire/Desktop/Telinfo","r")
		MainUiClass.telutc=self.telinfo.read().split('\n')[16][23:28]
		#DEC in hour:minute:seconds
		self.telinfo=open("/home/fhire/Desktop/Telinfo","r")
		MainUiClass.teldec=self.telinfo.read().split('\n')[31][23:33]
		
		#Convert RA to degrees
		rahour=float(MainUiClass.telra.split(":")[0])
		raminute=float(MainUiClass.telra.split(":")[1])
		raseconds=float(MainUiClass.telra.split(":")[2])
		RaD=rahour+raminute/60+raseconds/3600
		MainUiClass.telra=RaD
		#Convert dec to degrees
		dechour=float(MainUiClass.teldec.split(":")[0])
		decminute=float(MainUiClass.teldec.split(":")[1])
		decseconds=float(MainUiClass.teldec.split(":")[2])
		MainUiClass.teldec=dechour+decminute/60+decseconds/3600
	
		print("RA: "+str(MainUiClass.telra)+"\nDEC: "+str(MainUiClass.teldec)+"\nUTC: "+str(MainUiClass.telutc)+"\nHUM: "+str(MainUiClass.telhum)+"\nTEMP: "+str(MainUiClass.teltemp)+" C"+"\nHA: "+str(MainUiClass.telhad))
	
		#Zenith calculation
		t0=math.radians(90.-MainUiClass.lat)
		t1=math.radians(90.-RaD) 
		p0=math.radians(MainUiClass.lon)
		p1=math.radians(RaD)
		
		zz=math.cos(t0)*math.cos(t1)+math.sin(t0)*math.sin(t1)*math.cos(p1-p0)
		MainUiClass.z=math.acos(zz) #zenith angle [radians]
		
		self.telinfo.close()

	def ADC_home(self):
		top_switch.pin_start()
		bottom_switch.pin_start()
		global top_abs 
		global bot_abs
		if gpio.input(37):
			while gpio.input(37):
				stepper2.step()
		if gpio.input(38):
			while gpio.input(38):
				stepper3.step()
		print "ADC sent home"
		top_switch.pin_stop()
		bottom_switch.pin_stop()
		top_abs = 0
		bot_abs = 0
		self.adc_top(top_abs)
		self.adc_bot(bot_abs)


#-------------------------------------------------------------------------------------#
	#***NEED TO CHANGE TO TELINFO UTC TIME***
	def updateUTC(self,UTC):
		self.UTC=UTC
		self.UTC_lbl2.setText(str(self.UTC)[0:19])
	
	#***CHECK TO SEE IF WORKS***
	def autosaving(self,status):
		if status==True:
			self.autosaving==True
		elif status==False:
			self.autosaving==True

	def autoguiding(self,status):
		if status==True:
			self.guiding==True
			print("Autoguiding Turned On")
		elif status==False:
			self.guiding==False
			print("Autoguiding Turned Off")
#---------------------------------------------------------------------------------------#
	def setClaudiuslnk(self,lnk):
		self.claudiuslnk=lnk
	
	#Display modes for stage indicator
	def stage_indicator(self,position):
		if position==0:
			self.stage_ind.setText("BUSY")
			self.stage_ind.setStyleSheet("background-color: orange;\n""border: orange;")
		if position==1:
			self.stage_ind.setText("HOME")
			self.stage_ind.setStyleSheet("background-color: rgb(0, 255, 0);\n""border: rgb(0,255,0);")
		if position==2:
			self.stage_ind.setText("MIRROR")
			self.stage_ind.setStyleSheet("background-color: rgb(0, 255, 0);\n""border: rgb(0,255,0);")
		if position==3:
			self.stage_ind.setText("SPLITTER")
			self.stage_ind.setStyleSheet("background-color: rgb(0, 255, 0);\n""border: rgb(0,255,0);")
		if position==4:
			self.stage_ind.setText("UNKNOWN")
			self.stage_ind.setStyleSheet("background-color: rgb(255, 92, 42);\n""border: rgb(255,92,42);")

	#Get complete path from Threadclass's exposing method -- updates after every exposure
	def get_path(self):
		print("MainClass path: "+str(self.complete_path))

	#Change format of complete path to only the image for the ds9 list
	def set_path(self,path):
		self.complete_path=str(path)
		print("Set path: "+self.complete_path)
		self.img_name=self.complete_path.split("/")[-1]
		self.ds9_list.addItem(self.img_name)
		self.last_exposed_2.setText(self.complete_path)

	#Selecting image from list saves that full image path into the variable ds9_path ***DOESN'T WORK*** ** Fixed it?**
	def set_ds9(self):
		print("Set ds9 path?")
		self.ds9_path=str(self.complete_path).split(str(self.img_name))[0]+str(self.ds9_list.currentItem().text())

	#Open the image selected from the list in ds9 & overlay saved region box
	def open_ds9(self):
		os.system('xpaset -p ds9 fits ' + str(self.ds9_path)+' zscale')
		os.system('xpaset -p ds9 regions load '+self.main.regionpath) 

	#Reopen a ds9 window if accidentally closed -- new
	def reopen_ds9(self):
		os.system('ds9 -geometry 636x360+447+87 &')

	#Print filter names when set -- What 6 filters will we have?	
	def filter_names(self):
		if self.filter_cmb.currentIndex==1:
			print("Empty")		
			MainUiClass.lam=0	
		if self.filter_cmb.currentIndex==2:
			print("U Filter")
			MainUiClass.lam=.3656 #in micrometers (U Filter)
		if self.filter_cmb.currentIndex==3:
			print("B Filter")
			MainUiClass.lam=.4353 #B Filter
		if self.filter_cmb.currentIndex==4:
			print("V Filter")
			MainUiClass.lam=.5477 #V Filter
		if self.filter_cmb.currentIndex==5:
			print("R Filter")
			MainUiClass.lam=.6349 #R Filter
		if self.filter_cmb.currentIndex==6:
			print("I Filter") 
			MainUiClass.lam=.8797 #I Filter
		if self.filter_cmb.currentIndex==7:
			print("ND 1.8") 
			MainUiClass.lam=0 #ND
		if self.filter_cmb.currentIndex==8:
			print("ND 3.0") 
			MainUiClass.lam=0 #ND

	def lamb_change(self,index): #***Don't need to repeat previous method***
		if index==0:
			print("Empty")
			MainUiClass.lam=0
			MainUiClass.nglass=0
		if index==1:
			print("U Filter")
			MainUiClass.lam=.3656 #in micrometers
			MainUiClass.nglass=1.4745
		if index==2:
			print("B Filter")
			MainUiClass.lam=.4353
			MainUiClass.nglass=1.4667
		if index==3:
			print("V Filter")
			MainUiClass.lam=.5477
			MainUiClass.nglass=1.4600
		if index==4:
			print("R Filter")
			MainUiClass.lam=.6349
			MainUiClass.nglass=1.4570
		if index==5:
			print("I Filter")
			MainUiClass.lam=.8797
			MainUiClass.nglass=1.4520
		#***NEED nglass FOR ND FILTERS***			
		if index==6:
			print("ND 1.8")
		if index==7:
			print("ND 3.0") #ND 1.8
		print MainUiClass.lam	
	
#--------------------------------------------------------------------------------------------#
	#Centroiding method -- ***When is it called? Is it set for autoguiding or just manually with the button?***
	def mycen(self):
		#imgpath=self.complete_path
		#***DOES imgpath NOT WORK???*** ** Fixed it? **
		imgpath='/home/fhire/Desktop/GUI/GAMimage71.fit'
		print("Centroid accessing: "+str(imgpath))

		#Position of optical fiber
		os.system("xpaset -p ds9 regions command '{point 1065 360 # point=x 20 color=red}'")
		
		# save current ds9 regions to reg file and then read and compute centroid
		os.system('xpaset -p ds9 regions save '+self.regionpath)
		[xcenter, ycenter] = imexcentroid(imgpath, self.regionpath)
		
		# compute the offset and display
		xdiff = (xcenter)-1065
		ydiff = (ycenter)-360

		if xdiff < 0:
			xoffset = "nn "+str(abs(int(.044*xdiff)))
		elif xdiff >= 0:
			xoffset = "ss "+str(int(.044*xdiff))
		if ydiff < 0:
			yoffset = "ee "+str(abs(int(.044*ydiff)))
		elif ydiff >= 0:
			yoffset = "ww "+str(int(.044*ydiff))	
			
		self.centroid_lbl.setText("("+str(xcenter)+","+str(ycenter)+")")
		print("("+str(xcenter)+","+str(ycenter)+")")
		self.move_offset=(xoffset+";"+yoffset)
		self.move_lbl_2.setText(xoffset+" "+yoffset)
#---------------------------------------------------------------------------------------------#
	def mycen2(self,imgpath): #Why is there 2 methods of mycen? - autoguiding
		#imgpath=self.complete_path
		#***DOES imgpath NOT WORK???***
		#imgpath='/home/fhire/Desktop/GAMimage1.fit'
		print("Centroid accessing: "+str(imgpath))

		#Position of optical fiber
		os.system("xpaset -p ds9 regions command '{point 1065 360 # point=x 20 color=red}'")
		
		# save current ds9 regions to reg file and then read and compute centroid
		os.system('xpaset -p ds9 regions save '+self.regionpath)
		[xcenter, ycenter] = imexcentroid(imgpath, self.regionpath)
		
		# compute the offset and display
		xdiff = (xcenter)-1065
		ydiff = (ycenter)-360

		if xdiff < 0:
			xoffset = "nn "+str(abs(int(.044*xdiff)))
		elif xdiff >= 0:
			xoffset = "ss "+str(int(.044*xdiff))
		if ydiff < 0:
			yoffset = "ee "+str(abs(int(.044*ydiff)))
		elif ydiff >= 0:
			yoffset = "ww "+str(int(.044*ydiff))	
			
		self.centroid_lbl.setText("("+str(xcenter)+","+str(ycenter)+")")
		print("("+str(xcenter)+","+str(ycenter)+")")
		self.move_offset=(xoffset+";"+yoffset)
		self.move_lbl_2.setText(xoffset+" "+yoffset)
		self.send_command2() #Move telescope

	#Print set temperature when set
	def temp_notif(self):
		print("Temperature set to "+str(self.temp_lineEdit.text())+" C")
		
	#Events when window is closed -- replace with a shutdown button?
	def closeEvent(self,event):
		self.photlog.close() #new
		self.claudiuslnk.logout() #new
		self.threadclass.cooler_off
		#self.cooler_rdb_off_3.setChecked(True)
	#	proc.send_signal(signal.SIGINT) #***WHAT IS THIS?***

	#Updates i for exposure updates
	def update_i(self):
		global i
		i=0

	#Update number of exposures variable j
	def update_num(self):
		global j
		j=self.num_exp_spn.value()

#--------------------------------------------------------------------------------#
	#Send command to Claudius via subprocess -- ***THERE WAS AN ERROR WITH THIS!*** ** Fixed it? **
	def send_command(self):
		#Get command and print
		command=str(self.claudius_command_lineEdit.text())
		self.claudius_command_lineEdit.clear()
		print ("<span style=\"color:#0000ff;\"><b>observer@claudius: </b>"+command+"</span>")
		
		#same as above
		"""command_claudius=("ssh observer@claudius "+ command)
		command_final=command_claudius.split(" ")
		print command_final
		call(command_final)"""

		#Send command and print Claudius output
		self.claudiuslnk.sendline(command) 
		self.claudiuslnk.prompt() 
		print ("<span style=\"color:#0000ff;\">"+self.claudiuslnk.before+"</span>") 
 
		#out, err=Popen(command,stdout=PIPE).communicate()
		#print (out)

	def send_command2(self):
		#Get command and print
		command=self.move_offset
		self.claudius_command_lineEdit.clear()
		print ("<span style=\"color:#0000ff;\"><b>observer@claudius: </b>"+command+"</span>")
		
		#same as above
		"""command_claudius=("ssh observer@claudius "+ command)
		command_final=command_claudius.split(" ")
		print command_final
		call(command_final)"""

		#Send command and print Claudius output
		self.claudiuslnk.sendline(command) 
		self.claudiuslnk.prompt() 
		print ("<span style=\"color:#0000ff;\">"+self.claudiuslnk.before+"</span>") 
 
		#out, err=Popen(command,stdout=PIPE).communicate()
		#print (out)
#------------------------------------------------------------------------------------#

	#Make frame size input more responsive -- clears text and changes placeholder
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

	#Update remaining time, progress bar and exposure count
	def time_start(self,exp_update):
		global i
		i+=1
		self.time_left=float(exp)
		self.percent_elapsed=0
		self.qtimer=QtCore.QTimer(self)
		self.qtimer.timeout.connect(self.time_dec)
		self.qtimer.start(1000) #1000 msec intervals
		print("Exposure ("+str(i)+ ") started")
		
	def time_dec(self,abort=False):
		global exp
		self.time_left-=1
		print(str(self.time_left))
		self.percent_elapsed+=100/float(exp)
		if self.time_left<=0:
			self.qtimer.stop()
			print("STOP")
			self.exp_prog.setValue(0)
			self.remaining_lbl2.setText("0.0 s")
		elif abort==True:
			self.qtimer.stop()
			self.exp_prog.setValue(0)
			self.remaining_lbl2.setText("0.0 s")
		else:
			self.update_txt()
	
	def update_txt(self):
		global j
		global i
		j=self.num_exp_spn.value()
		self.remaining_lbl2.setText(str(self.time_left)+"s")
		self.exp_prog.setValue(self.percent_elapsed)
		self.currentexp_lbl2.setText(str(i)+"/"+str(j))

	def adc_top(self,top):
		self.top=top
	def adc_bot(self,bot):
		self.bot=bot
		self.adc_current()
	#Current ADC position in steps
	def adc_current(self):
		self.ADC_current_lbl2.setText("Top:"+str(self.top)+"     Bottom:"+str(self.bot))	

	#Make exposure time input more responsive -- clears text and changes placeholder
	def clear_exp(self):
		global exp
		exp=self.exp_inp.text()
		print("Set exposure time to: "+exp+" seconds")
		self.exp_inp.clear()
		self.exp_inp.setPlaceholderText(exp)
		return exp

	#Non returnPressed alternative to setting exposure time
	def get_exp(self):
		global exp
		exp=self.exp_inp.text()
		return exp
		
	#Set amount of steps -- focus stepper motors
	def cmove(self):
		i=0
		num=int(self.cfocus_lineEdit.text())
		if(num < 0):
			stepper.set_direction(ccw)
			while (i>num):
				stepper.step()
				i-=1
				self.cfocus_count_sub()
		if(num > 0):
			stepper.set_direction(cw)
			while (i<num):
				stepper.step()
				i+=1
				self.cfocus_count_add()		

	# (Add a check to make sure the directory exists. If not, prompt user to create new one (Doesn't work).)
	def setDirectory(self):
		self.file_path
		self.file_path=self.dir_inp.text()
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
			#	self.logfile.write("Directory created\n")
			#	return file_path
			#	self.dir_inp.setPlaceholderText(file_path)				
		
	def setPrefix(self):
		self.file_name
		self.file_name=self.prefix_inp.text()
		self.prefix_inp.clear()
		print("Image prefix set to: "+self.file_name+"XXX.fit")
		self.prefix_inp.setPlaceholderText(self.file_name+"XXX.fit")
		return self.file_name

	#Restores sys.stdout and sys.stderr
	def __del__(self):
		sys.stdout=sys.__stdout__
		sys.stderr=sys.__stderr__

	#Write to textBox terminal_edit 
	def normalOutputWritten(self,text):
		self.terminal_edit.append(text)

	#Set default frame size values 
	def setXPosition(self,xposition):
		self.leftmost_lineEdit.setPlaceholderText(str(xposition))
		
	def setYPosition(self,yposition):
		self.tpmost_lineEdit.setPlaceholderText(str(yposition))

	def setXFrame(self,xframe):
		self.xframe_size.setPlaceholderText(str(xframe))
		
	def setYFrame(self,yframe):
		self.yframe_size.setPlaceholderText(str(yframe))
		
	#Focus counter methods
	def cfocus_count_add(self):
		count=int(self.cfocus_count.text())
		count+=1
		self.cfocus_count.setText(str(count))

	def cfocus_count_sub(self):
		count=int(self.cfocus_count.text())
		count-=1
		self.cfocus_count.setText(str(count))

	#Set default filter position
	def setSlot(self,slot):
		self.filter_cmb.setCurrentIndex(slot)

	#Set default checked frame type radiobutton
	def setFrameType(self,typ):
		if typ==0:
			self.frameType_rdb_light.setChecked(True)
		if typ==1:
			self.frameType_rdb_bias.setChecked(True)
		if typ==2:
			self.frameType_rdb_dark.setChecked(True)
		if typ==3:
			self.frameType_rdb_flat.setChecked(True)

	#Set default checked bit/pix radiobutton
	def setBit(self,bit):
		if bit==0:
			self.eight_rdb.setChecked(True)
		if bit==1:
			self.sixteen_rdb.setChecked(True)

	#Set default checked cooler radiobutton 
	def setCooler(self,cool):
		if cool==0:
			self.cooler_rdb_on.setChecked(True)
		if cool==1:
			self.cooler_rdb_off.setChecked(True)

	#Set spinbutton default values
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

	#Update temperature and graph -- ***graph is lagging now***
	def setTemp(self,temp):
		self.temp=temp
		self.ctemp_lbl2.setText(str(self.temp)+" C")
		#print(type(str(self.UTC)))
		#self.UTCtemp=str(self.UTC)[10:18]
		#self.templist.append({'x':self.UTCtemp,'y':self.temp})
		#ix=[item['x'] for item in self.templist]
		#iy=[item['y'] for item in self.templist]	
		#self.tempgraph.setData(x=ix,y=iy)	
		#self.templist.append(self.temp)
		#self.tempgraph.plot(self.templist,pen=(255,0,0))

	#Update cooler power 
	def setCPower(self,cpower):
		self.cpower_lbl2.setText(str(cpower)+" %")

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

	#Update filter indicator -- (add one for errors)
	def setFilterInd(self,busy):
		if(busy==True):
			self.filter_ind.setText("BUSY") 
			self.filter_ind.setStyleSheet("background-color: orange;\n""border: orange;")
		if(busy==False):
			self.filter_ind.setText("OKAY")
			self.filter_ind.setStyleSheet("background-color: rgb(0, 255, 0)")

#==============================================================================#
#Client thread
class ThreadClass(QtCore.QThread): 		
	def __init__(self,main):
		self.main=main
		super(ThreadClass,self).__init__(main)
		#Define global variables
		self.wheel="QHYCFW2"
		#self.wheel="ASI EFW"
		self.dwheel=None
		self.connect_dwheel=None

		self.camera="ZWO CCD ASI174MM-Cool"
		self.dcamera=None
		self.connect_dcamera=None

		self.slot_dwheel=None
		
		self.cpower_dcamera=None
		self.cool_dcamera=None
		self.cpower_dcamera=None
		self.temp_dcamera=None

		self.binning_dcamera=None
		self.frame_dcamera=None
		self.frametype_dcamera=None
		self.controls_dcamera=None
		self.bit_dcamera=None

		self.expose_dcamera=None
		self.abort_dcamera=None
		self.blob_dcamera=None
	
		self.complete_path=None
		self.j=None

		#Starts an exposure progress thread
		p=threading.Thread(target=self.time_start)
		p.start()
#================================================================================================#
#
# -------------------- Connect to server, devices, indi properties ------------------------------
#
#================================================================================================#

#(Do you want the extra notifications? Print statements can be uncommented. Vis versa)
	def run(self):
		#Connect to server
		start=time.time()
		time.sleep(1)
		self.indiclient=filterclient.IndiClient()
		self.indiclient.setServer("localhost",7624) 
		print("Connecting...")
		self.indiclient.connectServer() 

		#Connect to filterwheel
		self.dwheel=self.indiclient.getDevice(self.wheel)
		while not(self.dwheel):
			time.sleep(0.5)
			self.dwheel=self.indiclient.getDevice(self.wheel)

		self.connect_dwheel=self.dwheel.getSwitch("CONNECTION")
		while not(self.connect_dwheel):
			time.sleep(0.5)
			self.connect_dwheel=self.dwheel.getSwitch("CONNECTION")

		time.sleep(0.5)

		while not(self.dwheel.isConnected()): 
			self.connect_dwheel[0].s=filterclient.PyIndi.ISS_ON 
			self.connect_dwheel[1].s=filterclient.PyIndi.ISS_OFF
			self.indiclient.sendNewSwitch(self.connect_dwheel) 
			print("Connecting QHYCFW (Filterwheel)")
			time.sleep(1)

		time.sleep(1)
		if(self.dwheel.isConnected()):
			print("Connected: QHYCFW (Filterwheel)")

		if not(self.dwheel.isConnected()):
			print("Disconnected: QHYCFW (Filterwheel)")

		#Connect FILTER_SLOT
		self.slot_dwheel=self.dwheel.getNumber("FILTER_SLOT")

		while not(self.slot_dwheel):
			self.slot_dwheel=self.dwheel.getNumber("FILTER_SLOT")
		if(self.slot_dwheel):	
			print("property setup: FILTER_SLOT")
			print(self.slot_dwheel[0].value)

		#Connect to camera
		self.dcamera=self.indiclient.getDevice(self.camera)
		while not(self.dcamera):
			time.sleep(0.5)
			self.dcamera=self.indiclient.getDevice(self.camera)

		self.connect_dcamera=self.dcamera.getSwitch("CONNECTION") 
		while not(self.connect_dcamera):
			time.sleep(0.5)
			self.connect_dcamera=self.dcamera.getSwitch("CONNECTION")

		time.sleep(1)

		if not(self.dcamera.isConnected()): 
			self.connect_dcamera[0].s=filterclient.PyIndi.ISS_ON
			self.connect_dcamera[1].s=filterclient.PyIndi.ISS_OFF
			self.indiclient.sendNewSwitch(self.connect_dcamera) 
			print("Connecting (Guide Camera)")

		time.sleep(1)
		if(self.dcamera.isConnected()):
			print("Connected: ZWO CCD (Guide Camera)")

		if not(self.dcamera.isConnected()):
			print("Disconnected: ZWO CCD (Guide Camera)")

		#Connect CCD_COOLER
		self.cool_dcamera=self.dcamera.getSwitch("CCD_COOLER") 
		while not(self.cool_dcamera):
			self.cool_dcamera=self.dcamera.getSwitch("CCD_COOLER")
		if(self.cool_dcamera):	
			print("property setup: CCD_COOLER")

		#Connect CCD_CONTROLS
		self.controls_dcamera=self.dcamera.getNumber("CCD_CONTROLS")
		while not(self.controls_dcamera):
			self.controls_dcamera=self.dcamera.getNumber("CCD_CONTROLS")
		if(self.controls_dcamera):	
			print("property setup: CCD_CONTROLS")

		#Connect CCD_BINNING
		self.binning_dcamera=self.dcamera.getNumber("CCD_BINNING")
		while not(self.binning_dcamera):
			self.binning_dcamera=self.dcamera.getNumber("CCD_BINNING")
		if(self.binning_dcamera):
			print("property setup: CCD_BINNING")

		#Connect CCD_FRAME_TYPE
		self.frametype_dcamera=self.dcamera.getSwitch("CCD_FRAME_TYPE")
		while not(self.frametype_dcamera):
			self.frametype_dcamera=self.dcamera.getNumber("CCD_FRAME_TYPE")
		if(self.frametype_dcamera):
			print("property setup: CCD_FRAME_TYPE")

		#Connect CCD_FRAME
		self.frame_dcamera=self.dcamera.getNumber("CCD_FRAME")
		while not(self.frame_dcamera):
			self.frame_dcamera=self.dcamera.getNumber("CCD_FRAME")
		if(self.frame_dcamera):
			print("property setup: CCD_FRAME")

		#Connect CCD_TEMPERATURE
		self.temp_dcamera=self.dcamera.getNumber("CCD_TEMPERATURE")
		while not(self.temp_dcamera):
			self.temp_dcamera=self.dcamera.getNumber("CCD_TEMPERATURE")
		if(self.temp_dcamera):	
			print("property setup: CCD_TEMPERATURE")

		#Connect CCD_EXPOSURE
		self.expose_dcamera=self.dcamera.getNumber("CCD_EXPOSURE") #def getNumber(self, name) in BaseDevice
		while not(self.expose_dcamera):
			self.expose_dcamera=self.dcamera.getNumber("CCD_EXPOSURE")
		if(self.expose_dcamera):	
			print("property setup: CCD_EXPOSURE")	

		#Inform indi server to receive the "CCD1" blob from this device
		self.indiclient.setBLOBMode(PyIndi.B_ALSO,self.camera,"CCD1")
		self.blob_dcamera=self.dcamera.getBLOB("CCD1")
		while not(self.blob_dcamera):
			time.sleep(0.5)
			self.blob_dcamera=self.dcmaera.getBLOB("CCD1")
		if(self.blob_dcamera):
			print("property setup: CCD1 -- BLOB")

		#Connect CCD_COOLER_POWER
		self.cpower_dcamera=self.dcamera.getNumber("CCD_COOLER_POWER")
		while not(self.cpower_dcamera):
			self.cpower_dcamera=self.dcamera.getNumber("CCD_COOLER_POWER")
		if(self.cpower_dcamera):
			print("property setup: CCD_COOLER_POWER")

		#Connect CCD_ABORT_EXPOSURE
		self.abort_dcamera=self.dcamera.getSwitch("CCD_ABORT_EXPOSURE") 
		while not(self.abort_dcamera):
			self.abort_dcamera=self.dcamera.getSwitch("CCD_ABORT_EXPOSURE")	
		if(self.abort_dcamera):
			print("property setup: CCD_ABORT_EXPOSURE")

		#Connect CCD_VIDEO_FORMAT
		self.bit_dcamera=self.dcamera.getSwitch("CCD_VIDEO_FORMAT") 
		while not(self.bit_dcamera):
			self.bit_dcamera=self.dcamera.getSwitch("CCD_VIDEO_FORMAT")	
		if(self.bit_dcamera):
			print("property setup: CCD_VIDEO_FORMAT")
		

		#set up thread for creating the blob
		filterclient.blobEvent=threading.Event() 
		filterclient.blobEvent.clear()

		self.event=threading.Event()
		self.event.clear()


		time.sleep(1)
		end=time.time()
		print ("*** Connection process complete ***"+"\nTime elapsed: "+str('%.2f'%(end-start))+" seconds")

#=================================================================================================#
#
# ------------------------ Receive default properties and send to MainUiClass ---------------------
#
#=================================================================================================#
		
		#Set cooler radiobutton default -- send current value to MainUiClass
		if(self.cool_dcamera[0].s==filterclient.PyIndi.ISS_ON):
			cool=0
		if(self.cool_dcamera[1].s==filterclient.PyIndi.ISS_ON):
			cool=1
		self.emit(QtCore.SIGNAL('COOLER'),cool)

		#Set frame type radiobutton default -- send current value to MainUiClass	
		if(self.frametype_dcamera[0].s==filterclient.PyIndi.ISS_ON):#Returns an error? --sometimes
			typ=0
		if(self.frametype_dcamera[1].s==filterclient.PyIndi.ISS_ON):
			typ=1
		if(self.frametype_dcamera[2].s==filterclient.PyIndi.ISS_ON):
			typ=2
		if(self.frametype_dcamera[3].s==filterclient.PyIndi.ISS_ON):
			typ=3
		self.emit(QtCore.SIGNAL('FRAME_TYPE'),typ)
	
		#Set default filter slot default value -- send current value to MainUiClass
		slot=self.slot_dwheel[0].value-1
		self.emit(QtCore.SIGNAL('SLOT'),slot)	

		#Set default bit value -- send current value to MainUiClass
		if(self.bit_dcamera[0].s==filterclient.PyIndi.ISS_ON):
			bit=0
		if(self.bit_dcamera[1].s==filterclient.PyIndi.ISS_ON):
			bit=1
		self.emit(QtCore.SIGNAL('BITPIX'),bit)		
		

		while True:
			time.sleep(1) 

#=================================================================================================#
#
# -------------------------------- Functionalities ------------------------------------------------
#
#=================================================================================================#

	#Abort exposure 
	def abort_exposure(self):
		self.abort_dcamera[0].s=filterclient.PyIndi.ISS_ON
		self.indiclient.sendNewSwitch(self.abort_dcamera)
		print("Exposure aborted")
		abort=True
		self.emit(QtCore.SIGNAL('ABORT'),abort)

	#Retrievable method by TempThread -- Get current temperature
	def get_temp(self):
		temp=self.temp_dcamera[0].value
		return temp

	#Retrievable method by TempThread -- Get current cooler power
	def get_cooler_power(self):
		cpower=self.cpower_dcamera[0].value
		return cpower

	#Retrievable method by FilterThread -- Get status of filterwheel
	def filter_busy(self):
		busy=False
		if(self.slot_dwheel.s==filterclient.PyIndi.IPS_BUSY):
			busy=True
		if(self.slot_dwheel.s==filterclient.PyIndi.IPS_OK):
			busy=False
		return busy

	#Change filter slot 
	def change_filter(self,slot):
		#self.slot_dwheel[0].value=1
		#self.indiclient.sendNewNumber(self.slot_dwheel)
		#print("Indi (before): "+ str(self.slot_dwheel[0].value))
		#time.sleep(1.5) #doesn't help
		#print slot
		self.slot_dwheel[0].value=slot+1
		#print ("Ours: "+ str(slot+1))
		self.indiclient.sendNewNumber(self.slot_dwheel)
		#print("Indi: "+ str(self.slot_dwheel[0].value))
		#print(self.slot_dwheel[0].value)

	#Turn cooler on
	def cooler_on(self):
		self.cool_dcamera[0].s=filterclient.PyIndi.ISS_ON
		self.cool_dcamera[1].s=filterclient.PyIndi.ISS_OFF
		self.indiclient.sendNewSwitch(self.cool_dcamera)

	#Turn cooler off
	def cooler_off(self):
		self.cool_dcamera[0].s=filterclient.PyIndi.ISS_OFF
		self.cool_dcamera[1].s=filterclient.PyIndi.ISS_ON
		self.indiclient.sendNewSwitch(self.cool_dcamera)

	#Change bandwidth
	def update_band(self,band):
		self.controls_dcamera[2].value=band
		self.indiclient.sendNewNumber(self.controls_dcamera)

	#Change x binning -- ***NOT WORKING?***
	def update_xbin(self,xbin):
		#print("New bin:"+str(xbin))
		self.binning_dcamera[0].value=xbin
		self.indiclient.sendNewNumber(self.controls_dcamera)

	#Change y binning -- ***NOT WORKING?***
	def update_ybin(self,ybin):
		self.binning_dcamera[1].value=ybin
		self.indiclient.sendNewNumber(self.controls_dcamera)

	#Change offset
	def update_offset(self,offset):
		self.controls_dcamera[1].value=offset
		self.indiclient.sendNewNumber(self.controls_dcamera)

	#Change gain
	def update_gain(self,gain):
		self.controls_dcamera[0].value=gain
		self.indiclient.sendNewNumber(self.controls_dcamera)

	#Set bit/pixel
	def bit_eight(self):
		self.bit_dcamera[0].s=filterclient.PyIndi.ISS_ON
		self.bit_dcamera[1].s=filterclient.PyIndi.ISS_OFF
		
	def bit_sixteen(self):
		self.bit_dcamera[0].s=filterclient.PyIndi.ISS_OFF
		self.bit_dcamera[1].s=filterclient.PyIndi.ISS_ON

	#Set frametype --- (could have also passed a value)
	def frametype_light(self):
		self.frametype_dcamera[0].s=filterclient.PyIndi.ISS_ON
		self.frametype_dcamera[1].s=filterclient.PyIndi.ISS_OFF
		self.frametype_dcamera[2].s=filterclient.PyIndi.ISS_OFF
		self.frametype_dcamera[3].s=filterclient.PyIndi.ISS_OFF
		self.indiclient.sendNewSwitch(self.frametype_dcamera)

	def frametype_bias(self):
		self.frametype_dcamera[0].s=filterclient.PyIndi.ISS_OFF
		self.frametype_dcamera[1].s=filterclient.PyIndi.ISS_ON
		self.frametype_dcamera[2].s=filterclient.PyIndi.ISS_OFF
		self.frametype_dcamera[3].s=filterclient.PyIndi.ISS_OFF
		self.indiclient.sendNewSwitch(self.frametype_dcamera)

	def frametype_dark(self):
		self.frametype_dcamera[0].s=filterclient.PyIndi.ISS_OFF
		self.frametype_dcamera[1].s=filterclient.PyIndi.ISS_OFF
		self.frametype_dcamera[2].s=filterclient.PyIndi.ISS_ON
		self.frametype_dcamera[3].s=filterclient.PyIndi.ISS_OFF
		self.indiclient.sendNewSwitch(self.frametype_dcamera)

	def frametype_flat(self):
		self.frametype_dcamera[0].s=filterclient.PyIndi.ISS_OFF
		self.frametype_dcamera[1].s=filterclient.PyIndi.ISS_OFF
		self.frametype_dcamera[2].s=filterclient.PyIndi.ISS_OFF
		self.frametype_dcamera[3].s=filterclient.PyIndi.ISS_ON
		self.indiclient.sendNewSwitch(self.frametype_dcamera)
	
	#Set frame size -- ***NOT WORKING?***
	def update_xposition(self,xposition):
		self.frame_dcamera[0].value=xposition
		self.indiclient.sendNewNumber(self.frame_dcamera)

	def update_yposition(self,yposition):
		self.frame_dcamera[2].value=yposition
		self.indiclient.sendNewNumber(self.frame_dcamera)

	def update_xframe(self,xframe):
		self.frame_dcamera[2].value=xframe
		self.indiclient.sendNewNumber(self.frame_dcamera)

	def update_yframe(self,yframe):
		self.frame_dcamera[3].value=yframe
		self.indiclient.sendNewNumber(self.frame_dcamera)

	#Change temperature
	def change_temp(self,temp):
		if(self.cool_dcamera[0].s==filterclient.PyIndi.ISS_OFF):
			self.cool_dcamera[0].s==filterclient.PyIndi.ISS_ON
			self.indiclient.sendNewSwitch(self.cool_dcamera)
			cool=0
			self.emit(QtCore.SIGNAL('COOLER'),cool)
		self.temp_dcamera[0].value=temp
		self.indiclient.sendNewNumber(self.temp_dcamera)

	#[AUTOGUIDING]Get the photometry / average flux of an image
	def get_phot(self, imgpath):
		iraf.noao()
		s = iraf.digiphot(Stdout=1)
		s = iraf.apphot(Stdout=1)

		s = iraf.phot(imgpath, coords="/home/fhire/Desktop/GUI/Reference/coords.txt", output="/home/fhire/Desktop/GUI/Reference/phot.txt", interactive="NO", graphics="no", verify="no", Stdout=1)

		txdump = iraf.txdump("/home/fhire/Desktop/GUI/Reference/phot.txt", "I*,XCEN,YCEN,FLUX,MAG", "yes", Stdout=1)

		#update the photlog file
		self.main.photlog.write(' '.join(txdump)+'\n')
		
		return txdump[0].split()[7]

	#Take exposure -- Autosave ON -- Autoguiding OFF
	def take_exposure(self):
		start=time.time()
		while(self.j>0):
			self.expose_dcamera[0].value=float(exp)
			self.event.set()
			self.indiclient.sendNewNumber(self.expose_dcamera)
			filterclient.blobEvent.wait()
			filterclient.blobEvent.clear()
			#Save image
			for blob in self.blob_dcamera:
				fits=blob.getblobdata()
				blobfile = io.BytesIO(fits)
				#Set image prefix and directory path
				self.complete_path=self.file_path+"/"+self.file_name+"1.fit"
				#Increment the images
				if os.path.exists(self.complete_path): 
					expand=1
					while True:
						expand+=1
						new_file_name=self.complete_path.split('1.fit')[0]+str(expand)+".fit"
						if os.path.exists(new_file_name):
							continue
						else:
							self.complete_path=new_file_name
							break
				with open(self.complete_path, "wb") as f:
					f.write(blobfile.getvalue())
				#[AUTOGUIDING]Save region, open new image in ds9, overlay saved region
				os.system('xpaset -p ds9 regions save '+self.main.regionpath)
				os.system('xpaset -p ds9 fits '+str(self.complete_path)+' -zscale')
				os.system('xpaset -p ds9 regions load '+self.main.regionpath) 
				print("Image Saved:")
				print self.complete_path
				'''
				#Update coords.txt ***WILL NEED TO ACCESS FOR OFFSET***
				#if guidebox drawn -> get the centroid
				#if not -> use the center of image
				if read_region(self.main.regionpath) != None:
					print "Region found. Computing centroid."
					[xcenter2, ycenter2] = imexcentroid(self.complete_path, self.main.regionpath)
					
				else:
					#compute the center of the frame just taken
					print "No region found. Centroid set to center of image. "+str(read_region(self.main.regionpath))
					hdulist1 = pyfits.open(self.complete_path)
					scidata1 = hdulist1[0].data
					[xcenter2, ycenter2] = [int(scidata1.shape[0]/2),int(scidata1.shape[1]/2)]
				print("Centroid: "+str(xcenter2)+','+str(ycenter2))
				#close and reopen coordinate file so it overwrites ***better way to do this?***
				self.main.coordsfile = open('/home/fhire/Desktop/GUI/Reference/coords.txt', 'w')
				self.main.coordsfile.write(str(xcenter2)+' '+str(ycenter2))
				self.main.coordsfile.close()
				'''
				#Update intensity graph
				#f = int(float(self.get_phot(self.complete_path)))
				#self.emit(QtCore.SIGNAL('newFluxPoint'),f)

			self.j-=1
			#Update image path
			print("Saving image path")
			self.emit(QtCore.SIGNAL('PATH'),self.complete_path)
			end=time.time()
			print("Total time elapsed: "+str(end-start))
			QtGui.QApplication.processEvents()
		time.sleep(1)
####################################################################################################################
	#Take exposure -- Autosave ON -- Autoguiding ON
	def take_exposure2(self):
		start=time.time()
		while(self.j>0):
			self.expose_dcamera[0].value=float(exp)
			self.event.set()
			self.indiclient.sendNewNumber(self.expose_dcamera)
			filterclient.blobEvent.wait()
			filterclient.blobEvent.clear()
			#Save image
			for blob in self.blob_dcamera:
				fits=blob.getblobdata()
				blobfile = io.BytesIO(fits)
				#Set image prefix and directory path
				self.complete_path=self.file_path+"/"+self.file_name+"1.fit"
				#Increment the images
				if os.path.exists(self.complete_path): 
					expand=1
					while True:
						expand+=1
						new_file_name=self.complete_path.split('1.fit')[0]+str(expand)+".fit"
						if os.path.exists(new_file_name):
							continue
						else:
							self.complete_path=new_file_name
							break
				with open(self.complete_path, "wb") as f:
					f.write(blobfile.getvalue())
				#[AUTOGUIDING]Save region, open new image in ds9, overlay saved region
				os.system('xpaset -p ds9 regions save '+self.main.regionpath)
				os.system('xpaset -p ds9 fits '+str(self.complete_path)+' -zscale')
				os.system('xpaset -p ds9 regions load '+self.main.regionpath) 
				print("Image Saved:")
				print self.complete_path
				print("Sending to centroid")
				self.emit(QtCore.SIGNAL('GUIDE'),self.complete_path)

			self.j-=1
			#Update image path
			#print("Saving image path")
			#self.emit(QtCore.SIGNAL('PATH'),self.complete_path)
			end=time.time()
			print("Total time elapsed: "+str(end-start))
			QtGui.QApplication.processEvents()
		time.sleep(1)


	#Separate exposure thread
	def thread(self,exp,j,file_path,file_name,guiding):
		self.j=j
		self.file_path=file_path
		self.file_name=file_name
		self.exp=exp
		print(guiding)
		saving=True
		if saving==True and guiding==False:
			t=threading.Thread(target=self.take_exposure)
			t.start()
		if saving==True and guiding==True:
			t=threading.Thread(target=self.take_exposure2)
			t.start()
		if saving==False and guiding==False:
			t=threading.Thread(target=self.take_exposure_delete)
			t.start()
		if saving==False and guiding==True:
			t=threading.Thread(target=self.take_exposure_delete2)
			t.start()

	#Make complete_path available for MainUiClass -- (Doesn't work)
	def path(self):
		return self.complete_path

	#Retrievable method by FilterThread -- status of exposure
	def exp_busy(self):
		busy=False
		if(self.expose_dcamera.s==filterclient.PyIndi.IPS_BUSY):
			busy=True
		if(self.expose_dcamera.s==filterclient.PyIndi.IPS_OK):
			busy=False
		return busy

	#Update remaining time, progress bar and exposure count
	def time_start(self):
		time.sleep(8)
		while 1:
			self.event.wait()
			self.event.clear()
			start=True
			self.emit(QtCore.SIGNAL('TIMER'),start)


class ADCThread(QtCore.QThread):
	def __init__(self,main):
		self.main=main
		super(ADCThread,self).__init__(main)
		
		global j
		j=0
		global k
		k=0
		self.hum=self.main.telhum
		self.altitude=self.main.altitude
		self.lon=self.main.lon
		self.lat=self.main.lat
		self.h=self.altitude #why is this repeated?

		self.lam_naught=.5 #[microns]
		self.P_sea=101325 #[pascals]
		self.T_b=288.15 #[kelvin]
		self.R=8.3144598 #[J/mol*K]
		self.g=9.80665 #[m/s**2]
		self.obslat=41.097056 #[degrees]
	def run(self):
		time.sleep(8)
		self.main.ADC_home()
		time.sleep(6)
		while 1:	
			self.main.updatePosition()	
			print self.main.teldec
			self.calc_steps_top()
			self.move_steps_top()
			self.calc_steps_bottom()
			self.move_steps_bottom()
			print("Here")
			time.sleep(10)
	#------------Top prism----------------------#
	#finds parallactic angle and aligns top prism to parallactic 
	#angle and bottom prism to zero correction position
	def calc_steps_top(self):
		had_r=math.radians(float(self.main.telhad))
		obslat_r=math.radians(float(self.obslat))
		dec_r=math.radians(float(self.main.teldec))

		print ("Dec:"+str(dec_r))
		
		#finds sin of parallactic angle
		sinpar = (math.sin(had_r)*math.cos(obslat_r))/(1.-(math.sin(obslat_r)*math.sin(dec_r)+math.cos(obslat_r)*math.cos(dec_r)*math.cos(had_r))**2)**0.5	

		#gets parallactic angle in degrees
		par_angle = math.degrees(math.asin(sinpar))
		print ("Parallactic:"+str(par_angle))
		#converts parallactic angle into motor steps
		parstepsfloat = par_angle/.315 
		self.parstepsint = int(parstepsfloat)
		print ("Top Prism")
		print self.parstepsint
		
	def move_steps_top(self):
		global top_abs
		
		if top_abs > self.parstepsint:
			while j>self.parstepsint:
				#print j
				stepper2.set_direction(False) 
				stepper2.step()
				top_abs -= 1
		elif top_abs < self.parstepsint:
			while j<self.parstepsint:
				#print j
				stepper2.set_direction(True)
				stepper2.step()
				top_abs +=1
		
		self.emit(QtCore.SIGNAL('ADC_top'),top_abs)
		stepper2.set_direction(True)
	#----------------Bottom prism-------------------#
	def calc_steps_bottom(self):
		M=.02897 #[kg/mole]
		#finds atmospheric differential dispersion relative to .5 microns
		#in arc seconds as a function of pressure, temperature, humidity and zenith angle
		P = float((self.P_sea*math.exp((-self.g*M*self.h)/(self.R*self.T_b)))/133.322)	#mmHg --- what is M?
		#--#Hum_cor = ((0.0624-(0.00068/(lam**2)))/(1+(0.003661*T)))*hum   #scale the things
		N_sea5 = float(((1/(10**6))*(64.328+(29498.1/(146-((1/self.lam_naught)**2)))+(255/(41-((1/self.lam_naught)**2)))))+1)
		
		N_WIRO5 = float(((N_sea5-1)*((P*(1+((1.049-(0.0157*self.main.teltemp))*(10**-6)*P)))/(720.883*(1+(0.003661*self.main.teltemp)))))+1)
		N_sea = float(((1/(10**6))*(64.328+(29498.1/(146-((1/self.main.lam)**2)))+(255/(41-((1/self.main.lam)**2)))))+1)
		N_WIRO = float(((N_sea5-1)*((P*(1+((1.049-(0.0157*self.main.teltemp))*(10**-6)*P)))/(720.883*(1+(0.003661*self.main.teltemp)))))+1)
		Delta = float((N_WIRO-N_WIRO5)*math.tan(self.main.z))

		#compares value of atmospheric diffraction with needed value of correction and displaces bottom prism
		F = 14925 # focal length in mm
		prismangle = math.radians(15) #***Added temp.***
		H = math.tan(prismangle) # normalized prism base
		D = 269	# distance between prisms and focus mm
		nglass15 = 1.4623
		nglass1lam = self.main.nglass
		dnglass1 = nglass15-nglass1lam
		Fee = math.degrees(math.acos((1/H)*math.tan((F*Delta)/(D*(dnglass1))))) 
		stepsfloat = Fee/.315
		stepsint = int(stepsfloat)
		self.bot_steps = top_abs+stepsint
		print("Bottom Prism")
		print self.bot_steps
	def move_steps_bottom(self):
		#print self.bot_steps
		global k
		global bot_abs
		
		if k > self.bot_steps:
			while k>self.bot_steps:
				stepper3.set_direction(False)
				stepper3.step()
				k -= 1
				bot_abs -= 1
		elif k < self.bot_steps:
			while k<self.bot_steps:
				stepper3.set_direction(True)
				stepper3.step()
				k += 1
				bot_abs +=1
		
		print ("k:"+str(k))
		self.emit(QtCore.SIGNAL('ADC_bot'),bot_abs)
		stepper3.set_direction(True)

#=========================================================================================#
#
# ---------------------------- Focuser (+Terminal) Threads -------------------------------
#
#=========================================================================================#
class TelUpdate(QtCore.QThread):
	def __init__(self,parent=None):
		super(TelUpdate,self).__init__(parent)
	def run(self):
		while 1:
			telUpdate=subprocess.call(['scp','observer@claudius:/var/Telinfo','/home/fhire/Desktop'])
			time.sleep(25)

#class UTCThread(QtCore.QThread):#replace with the utc from Claudius?
#	def __init__(self,parent=None):
#		super(UTCThread,self).__init__(parent)
#	def run(self):
#		while 1:
#			UTC=datetime.utcnow()
#			self.emit(QtCore.SIGNAL('CURRENT_UTC'),UTC)
#			time.sleep(10)


#Continuously update temperature and emit it to MainUiClass
class TempThread(QtCore.QThread):
	def __init__(self,client):
		self.client=client
		super(TempThread,self).__init__(client)
	def run(self):
		time.sleep(10)
		while 1:
			temp=self.client.get_temp()
			self.emit(QtCore.SIGNAL('TEMP'),temp)
			cpower=self.client.get_cooler_power()
			self.emit(QtCore.SIGNAL('CPOWER'),cpower)
			time.sleep(3)

#For use only once at startup -- updates filter indicator and exposure countdowns
class FilterThread_Startup(QtCore.QThread):
	def __init__(self,client):
		self.client=client
		super(FilterThread_Startup,self).__init__(client)
	def run(self):
		time.sleep(6)
		#print ("Filter thread")
		while 1:
			busy=self.client.filter_busy()
			self.emit(QtCore.SIGNAL('FILT_BUSY'),busy)
			time.sleep(0.5)

class ConfigThread(QtCore.QThread):
	def __init__(self,client):
		self.client=client
		super(ConfigThread,self).__init__(client)
	def run(self):
		time.sleep(8)
		while 1:
			#Set spinbutton default values -- send current value to MainUiClass
			band=self.client.controls_dcamera[2].value
			self.emit(QtCore.SIGNAL('BAND_VAL'),band)
			xbin=self.client.binning_dcamera[0].value
			self.emit(QtCore.SIGNAL('XBIN_VAL'),xbin)
			ybin=self.client.binning_dcamera[1].value
			self.emit(QtCore.SIGNAL('YBIN_VAL'),ybin)
			offset=self.client.controls_dcamera[1].value
			self.emit(QtCore.SIGNAL('OFFSET_VAL'),offset)
			gain=self.client.controls_dcamera[0].value
			self.emit(QtCore.SIGNAL('GAIN_VAL'),gain)
	
			#Set default frame size placeholder text -- send current value to MainUiClass
			xposition=self.client.frame_dcamera[0].value
			self.emit(QtCore.SIGNAL('XPOSITION'),xposition)
			yposition=self.client.frame_dcamera[1].value
			self.emit(QtCore.SIGNAL('YPOSITION'),yposition)
			xframe=self.client.frame_dcamera[2].value
			self.emit(QtCore.SIGNAL('XFRAME'),xframe)
			yframe=self.client.frame_dcamera[3].value
			self.emit(QtCore.SIGNAL('YFRAME'),yframe)
			time.sleep(0.5)

class Claudius(QtCore.QThread):
	def __init__(self,parent=None):
		super(Claudius,self).__init__(parent)
	def run(self):
		time.sleep(1)
		start=time.time()
		lnk = pxssh.pxssh()
		#hostname = '10.212.212.160' #10.214.214.110 (or claudius) Claudius needs to be running
		hostname='10.214.214.110'
		#username= 'aylin' #observer -- lia
		username='observer'
		password='iii2skY!'
		#password = 'fcgdaeb' #iii2skY! -- Summer2k18
		lnk.login(hostname,username,password)
		self.emit(QtCore.SIGNAL('LNK'),lnk)
		end=time.time()
		print ('<span style=\"color:#6666FF;\">Claudius connected. Time elapsed: '+str('%.2f'%(end-start))+" seconds</span>")
		
		
#(Maybe you should define all threads like this? Might be cleaner.)

#Define focus threads and execute
class thread1(QtCore.QThread):
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

#Stage thread that watches/checks status
class watchStageThread(QtCore.QThread):
	def __init__(self,parent=None):
		super(watchStageThread,self).__init__(parent)
		self.stage=stage()
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
					position=1 #Home				
					self.emit(QtCore.SIGNAL('STAGE'),position)
					QtGui.QApplication.processEvents()		
                    
				elif out == '\x64\x04\x0e\x00\x81\x50':
					move_out += self.stage.ser.read(14)
					if '\x00\xC0\xF3\x00' in move_out:
						print("MIRROR")
						position=2 #Mirror
						self.emit(QtCore.SIGNAL('STAGE'),position)
						QtGui.QApplication.processEvents()
					elif '\x00\x40\xDB\x02' in move_out:
						print("SPLITTER")
						position=3 #Splitter
						self.emit(QtCore.SIGNAL('STAGE'),position)
						QtGui.QApplication.processEvents()
					else:
						print("[ERROR] Unknown position -- please send home")						
						position=4 #Unknown
						self.emit(QtCore.SIGNAL('STAGE'),position)
						QtGui.QApplication.processEvents()
						break
	            		else:
					print("[ERROR] Unknown position -- please send home")
					position=4 #Unknown
					self.emit(QtCore.SIGNAL('STAGE'),position)
					QtGui.QApplication.processEvents()
			time.sleep(0.5)


#Start/Run GUI window
if __name__=='__main__':
	app=QtGui.QApplication(sys.argv)
	GUI=MainUiClass()
	GUI.show()
	app.exec_()

		
