#==============================================================================================#
# ------------------------------ FHiRE GUI code -----------------------------------------------
# ----------(GAM: Filterwheel, Guide Camera, Camera focuser, ADC focusers) --------------------
# --------------------------- Version: 10/01/2020 ---------------------------------------------
#==============================================================================================#
#=======================================================================================#
# -------------------------------- Imports: --------------------------------------------
#=======================================================================================#
from PyQt5 import QtCore,QtWidgets,uic
from PyQt5.QtCore import QThread,pyqtSignal

import fhireGUI11 #imports PyQt design
import client #imports basic indiclient loop
import GUI_windows as windows
import ZWOguiding_camera as zwo

import sys,os,io,time,threading,PyIndi,struct
import numpy as np 

import easydriver as ed #imports GPIO stuff for focuser
#from LTS300 import stage #imports driver for stage ***Disable when stage is disconnected ***

# Autoguiding:
from pexpect import pxssh 
#from pyraf import iraf 
from Centroid_DS9 import imexcentroid
from ReadRegions import read_region 
#=======================================================================================#
#=======================================================================================#
#Run IndiServer
#indiserver = subprocess.Popen(["x-terminal-emulator","-e","indiserver -v indi_qhycfw2_wheel indi_asi_ccd"])

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
			QtWidgets.QApplication.processEvents()

	def move_reverse(self):
		stepper.set_direction(ccw)
		self.moving_reverse = True
		i = add = 0
		while (self.moving_reverse == True):
			stepper.step()
			add += 1
			self.sig2.emit(add)
			QtWidgets.QApplication.processEvents()

	def stop(self):
		self.moving_forward = False
		self.moving_reverse = False

#===============================================================================================#
# ------------------------------------ Main GUI Class ------------------------------------------
#===============================================================================================#
#GUI class -- inherits qt designer's .ui file's class
class MainUiClass(QtWidgets.QMainWindow, fhireGUI11.Ui_MainWindow):
	def __init__(self,parent=None):
		super(MainUiClass,self).__init__(parent)
		self.setupUi(self) #this sets up inheritance for fhireGUI2 variables

		self.exp = 0
		self.current_exp = 0

		self.num_exp = self.num_exp_spn.value()
		self.offset_complete = False

		#self.setStyle(QtWidgets.QStyleFactory.create('GTK+'))

		self.vacuumwindow = windows.VacuumWindow()
		self.adcwindow = windows.ADCTestingWindow()
		self.camerawindow = zwo.ZWOCameraWindow()

		#Set up files:
		self.regionpath = '/home/fhire/Desktop/GUI/Reference/regions.reg'
		self.logfile = open('/home/fhire/Desktop/GUI/Reference/Log.txt', 'w') 
		self.photlog = open('/home/fhire/Desktop/GUI/Reference/photlog.txt', 'w') 
		self.coordsfile = None 

#=====================================
# Connect MainUiClass to threads =====
#=====================================
		
		self.threadclass = client.ThreadClass(self) #Client thread
		self.threadclass.start()

		self.filterthread_startup = FilterThread_Startup(self.threadclass) #Filter indicator thread
		self.filterthread_startup.start()

		self.refractorthread = Refractor()
		self.refractorthread.start()

		self.tempthread = windows.TempThread(self.threadclass)
		self.tempthread.start()

		self.configthread = windows.ConfigThread(self.threadclass)
		self.configthread.start()

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
		self.threadclass.sig1.connect(self.camerawindow.updateConfig2)
		self.threadclass.sig3.connect(self.setSlot) #Default filter slot

		#Update focus counts:
		#self.motor_loop1.sig1.connect(self.cfocus_count_add)	
		#self.motor_loop1.sig2.connect(self.cfocus_count_sub)		

		#Update filter indicator
		self.filterthread_startup.signal.connect(self.setFilterInd)

		#self.watchStageThread.connect(self.stage_indicator) #Update stage indicator

		self.threadclass.sig5.connect(self.time_dec) #Abort exposure

		self.threadclass.sig6.connect(self.set_path) #Image path + last exposed image
	
		self.threadclass.sig7.connect(self.time_start) #Start exposure updates (ie: remaining time and # exposures taken)
		self.threadclass.sig8.connect(self.mycen)
		
		#Claudius link
		#self.claudiusthread.signal.connect(self.setClaudiuslnk)

		self.tempthread.signal.connect(self.camerawindow.updateTemp)
		self.configthread.signal.connect(self.camerawindow.updateConfig)

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

	def refractor_exposure(self):
		self.refractorthread.signal.emit([float(self.exp_inp_2.text()),str(self.file_path),str(self.file_name)])

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

	#Change format of complete path to only the image for the ds9 list:
	def set_path(self,path):
		self.complete_path = str(path)
		self.img_name = self.complete_path.split("/")[-1]
		self.last_exposed_2.setText(self.complete_path)

	#Reopen a ds9 window if accidentally closed
	def reopen_ds9(self):
		os.system('ds9 -geometry 636x360+447+87 &')

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

	def setPrefix(self):
		self.file_name
		self.file_name = self.prefix_inp.text()
		self.prefix_inp.clear()
		print("Image prefix set to: "+self.file_name+"XXX.fit")
		self.prefix_inp.setPlaceholderText(self.file_name+"XXX.fit")
		return self.file_name

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

	#Focus counter methods:
	def cfocus_count_add(self):
		count = int(self.cfocus_count.text())
		count += 1
		self.cfocus_count.setText(str(count))

	def cfocus_count_sub(self):
		count = int(self.cfocus_count.text())
		count -= 1
		self.cfocus_count.setText(str(count))

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

	
	#Print filter names when set:
	def filter_names(self):
		filter_dict = {1:"ND 1.8", 2:"Empty", 3:"ND 3.0", 4:"Empty", 5:"V Filter", 6:"Empty",
				7:"R Filter", 8:"Empty"}
		print(filter_dict[self.filter_cmb.currentIndex])

	#Set default filter position:
	def setSlot(self,slot):
		self.filter_cmb.setCurrentIndex(slot)

	def setFilterInd(self,busy):
		if(busy == True):
			self.filter_ind.setStyleSheet("background-color: orange;\n""border: orange;")
		elif(busy == False):
			self.filter_ind.setStyleSheet("background-color: rgb(0, 255, 0)")

	#Restores sys.stdout and sys.stderr:
	def __del__(self):
		sys.stdout = sys.__stdout__
		sys.stderr = sys.__stderr__

	#Write to textBox terminal_edit:
	def normalOutputWritten(self,text):
		self.terminal_edit.append(text)

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

#===============================================================================================#
#===============================================================================================#

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
					QtWidgets.QApplication.processEvents()		
                    
				elif out == '\x64\x04\x0e\x00\x81\x50':
					move_out += self.stage.ser.read(14)
					if '\x00\xC0\xF3\x00' in move_out:
						print("MIRROR")
						position = 2 #Mirror
						self.signal.emit(position)
						QtWidgets.QApplication.processEvents()
					elif '\x00\x40\xDB\x02' in move_out:
						print("SPLITTER")
						position = 3 #Splitter
						self.signal.emit(position)
						QtWidgets.QApplication.processEvents()
					else:
						print("[ERROR] Unknown position -- please send home")			
						position = 4 #Unknown
						self.signal.emit(position)
						QtWidgets.QApplication.processEvents()
						break
				else:
					print("[ERROR] Unknown position -- please send home")
					position = 4 #Unknown
					self.signal.emit(position)
					QtWidgets.QApplication.processEvents()
			time.sleep(0.5)

	def stop(self):
		self.terminate()

#=========================================================================================#
#=========================================================================================#

#Start/Run GUI window
if __name__ == '__main__':
	app = QtWidgets.QApplication(sys.argv)
	GUI = MainUiClass()
	GUI.show()
	app.exec_()

		
