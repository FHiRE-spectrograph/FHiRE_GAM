import serial, io, sys, os, logging, time, datetime, threading, Queue

# plotting imports
import matplotlib.dates as mdates
from matplotlib.ticker import AutoMinorLocator
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

# GUI imports
from PyQt4 import QtGui,QtCore
import adminGUI

# set up logging. Change level=logging.INFO to level=logging.DEBUG to show raw serial communication
LOG_FILENAME = 'TIC.log'
	
logging.basicConfig(
    format='%(asctime)s, %(levelname)s, %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S',
	filename=LOG_FILENAME)

logr = logging.getLogger(LOG_FILENAME)

# link printed and logging messages
def printInfo(message):
	logr.info(message)
	print message

def printWarning(message):
	logr.warning(message)
	print message

def printError(message):
	logr.error(message)
	print message

def printDebug(message):
	logr.debug(message)
	if logr.getEffectiveLevel() == 10:	
		print message
	else:
		pass

# set display options for navigation toolbar
class NavigationToolbar(NavigationToolbar2QT):
	def __init__(self, *args, **kwargs):
		super(NavigationToolbar, self).__init__(*args, **kwargs)
		self.layout().takeAt(6)  # removes weird edit parameters button

	# only display the buttons we need
	toolitems = [t for t in NavigationToolbar2QT.toolitems if t[0] in ('Home', 'Forward', 'Back', 'Pan', 'Zoom', 'Save')]

# set terminal output to GUI textBox
class EmittingStream(QtCore.QObject):
	textWritten=QtCore.pyqtSignal(str) 
	
	def write(self,text):
		self.textWritten.emit(str(text))

#--------------------------------------------------------------------
#GUI CLASSES
#--------------------------------------------------------------------

# graphing window GUI class
class SecondUiClass(QtGui.QMainWindow):
	# class variables	
	pressure = np.array([])
	ion_pressure = np.array([])
	date = np.array ([])
	import_pressure = np.array ([])
	import_date = np.array ([])
	Log_pressure = False
	Import = False

	def __init__(self, parent=None):
		super(SecondUiClass,self).__init__(parent)	
		# create window
		self._main = QtGui.QWidget()
		self.setCentralWidget(self._main)
		self.layout = QtGui.QVBoxLayout(self._main)
		self.setGeometry(100, 100, 1000, 600)
		self.setWindowTitle("FHiRE Vacuum Controller - Graphing Window")

		#set up action menu
		actionPressure = QtGui.QAction("Graph Pressure", self)
		actionLog_Pressure = QtGui.QAction("Graph Log Pressure", self)	
		actionPressure.triggered.connect(self.PlotPressure)
		actionLog_Pressure.triggered.connect(self.PlotLogPressure)

		mainMenu = self.menuBar()
		fileMenu = mainMenu.addMenu('&Options')
		fileMenu.addAction(actionPressure)
		fileMenu.addAction(actionLog_Pressure)

		# set up figure
		self.figure = Figure()
		self.canvas = FigureCanvas(self.figure)
		self.layout.addWidget(self.canvas)
		self.toolbar=NavigationToolbar(self.canvas, self)
		self.addToolBar(QtCore.Qt.TopToolBarArea, self.toolbar)
		
	# main plot process
	def Plot(self, dat_file):
		# set up graph	
		self.ax = self.figure.add_subplot(111)	
		self.ax.hold(False)
		
		# check if import or live data
		if dat_file == False:
			self.ax.plot(self.date, self.pressure, 'r-')
		else:
			self.Import = True
			self.ax.plot(self.import_date, self.import_pressure, 'r-')
		
		# format axes
		self.ax.set_xlabel('Time (h:m:s)')
		self.ax.set_ylabel('Pressure (Torr)')
		myFmt = mdates.DateFormatter('%H:%M:%S')
		self.ax.xaxis.set_major_formatter(myFmt)
		self.ax.xaxis.set_minor_locator(AutoMinorLocator())
		self.ax.yaxis.set_minor_locator(AutoMinorLocator())

		self.canvas.draw()
		self.canvas.flush_events()

	# modify plot to show pressure or log pressure
	def PlotPressure(self):
		self.Log_pressure = False
		self.updateThread()	

	def PlotLogPressure(self):
		self.Log_pressure = True
		self.updateThread()

	# update graph
	def updateThread(self):	
		update_thread = threading.Thread(target=self.UpdatePlot)
		update_thread.start()

	def UpdatePlot(self):
		# check if graphing imported data, live data, log pressure or pressure
		if self.Log_pressure == False and self.Import == False:		
			self.ax.plot(self.date, self.pressure, 'r-')
			self.ax.set_ylabel('Pressure (Torr)')
		elif self.Log_pressure == False and self.Import == True:		
			self.ax.plot(self.import_date, self.import_pressure, 'r-')
			self.ax.set_ylabel('Pressure (Torr)')
		elif self.Log_pressure == True and self.Import == False:		
			self.ax.plot(self.date, np.log10(self.pressure), 'r-')
			self.ax.set_ylabel('Log Pressure (Torr)')
		else:
			self.ax.plot(self.import_date, np.log10(self.import_pressure), 'r-')
			self.ax.set_ylabel('Log Pressure (Torr)')	
		
		# format axes
		self.ax.set_xlabel('Time (h:m:s)')
		myFmt = mdates.DateFormatter('%I:%M:%S')
		self.ax.xaxis.set_major_formatter(myFmt)
		self.ax.xaxis.set_minor_locator(AutoMinorLocator())
		self.ax.yaxis.set_minor_locator(AutoMinorLocator())
		self.ax.relim()
		self.ax.autoscale_view()
		self.toolbar.update()
		self.canvas.draw()
		self.canvas.flush_events()

# main window GUI class (inherits from qt designer's adminGUI.ui or userGUI.ui)
# change adminGUI to userGUI to switch interfaces
class MainUiClass(QtGui.QMainWindow, adminGUI.Ui_MainWindow):

	def __init__(self):
		super(MainUiClass,self).__init__()
		self.setupUi(self)
		
		# start queue
		self.q = Queue.Queue()
		self.queueThread()

		# send terminal output to textBox
		sys.stdout=EmittingStream(textWritten=self.normalOutputWritten)
		#sys.stderr=EmittingStream(textWritten=self.normalOutputWritten)

		# start threads and connect buttons
		self.createTICThread()
		self.connectSignals()	

		# turn off to run code without connection to controllers
		time.sleep(1)
		self.tic.Collect_data()
		self.Backing_check()
		self.Ion_check()
		self.Turbo_check()
		self.cycleThread()
		
	# Disable printing
	def blockPrint(self):
		sys.stdout = open(os.devnull, 'w')

	# Restore printing
	def enablePrint(self):
		sys.stdout=EmittingStream(textWritten=self.normalOutputWritten)

	# connect buttons not realated to workers
	def connectSignals(self):
		# set up pump switches
		self.ion_switch.setCheckable(True)
		self.ion_switch.setStyleSheet("QPushButton#ion_switch {background-color : #e57373; border-style: inset; border-width: 2px; border-radius: 10px; padding: 6px;}" "QPushButton#ion_switch:checked {background-color: #8bc34a; border-style: outset;}")  

		self.neg_switch.setCheckable(True)
		self.neg_switch.setStyleSheet("QPushButton#neg_switch {background-color : #e57373; border-style: inset; border-width: 2px; border-radius: 10px; padding: 6px;}" "QPushButton#neg_switch:checked {background-color: #8bc34a; border-style: outset;}")  

		self.backing_switch.setCheckable(True)
		self.backing_switch.setStyleSheet("QPushButton#backing_switch {background-color : #e57373; border-style: inset; border-width: 2px; border-radius: 10px; padding: 6px;}" "QPushButton#backing_switch:checked {background-color: #8bc34a; border-style: outset;}") 

		self.turbo_switch.setCheckable(True)		
		self.turbo_switch.setStyleSheet("QPushButton#turbo_switch {background-color : #e57373; border-style: inset; border-width: 2px; border-radius: 10px; padding: 6px;}" "QPushButton#turbo_switch:checked {background-color: #8bc34a; border-style: outset;}") 

		# buttons and options
		self.ion_switch.clicked.connect(lambda: self.q.put(self.ionSwitch))
		self.neg_switch.clicked.connect(lambda: self.q.put(self.negSwitch))
		self.backing_switch.clicked.connect(lambda: self.q.put(self.backingSwitch))
		self.turbo_switch.clicked.connect(lambda: self.q.put(self.turboSwitch))
		self.graph.clicked.connect(lambda: self.create_new_window(False))
		self.actionImport.triggered.connect(self.importFile)
		self.pump_down.clicked.connect(self.pumpDownDialog)
		self.vent.clicked.connect(self.ventDialog)
		self.actionExit.triggered.connect(self.Close)

	# Setup the TIC worker object and the tic_thread.
	def createTICThread(self):
		self.tic = TIC()
		self.tic_thread = QtCore.QThread()
		self.tic.moveToThread(self.tic_thread)
		self.tic_thread.start()

		# Connect tic worker signals
		self.gauge_button.clicked.connect(lambda: self.q.put(self.tic.Collect_data))	
		self.pump_button_on.clicked.connect(lambda: self.q.put(self.tic.Backing_on))
		self.pump_button_off.clicked.connect(lambda: self.q.put(self.tic.Backing_off))
		self.turbo_button_on.clicked.connect(lambda: self.q.put(self.tic.Turbo_on))
		self.turbo_button_off.clicked.connect(lambda: self.q.put(self.tic.Turbo_off))
		self.auto_plot.clicked.connect(lambda: self.q.put(self.autoPlotThreader))
		self.stop_plot.clicked.connect(lambda: self.q.put(self.tic.Stop_plotting))
		self.connect(self.tic,QtCore.SIGNAL('block_print'),self.blockPrint)
		self.connect(self.tic,QtCore.SIGNAL('enable_print'),self.enablePrint)
		self.connect(self,QtCore.SIGNAL('create_new_window'),self.create_new_window)
		self.connect(self,QtCore.SIGNAL('update_window'),self.tic.graph_window.UpdatePlot)
		self.connect(self.tic,QtCore.SIGNAL('backing_on'),self.setBackingTextOn)
		self.connect(self.tic,QtCore.SIGNAL('backing_off'),self.setBackingTextOff)
		self.connect(self.tic,QtCore.SIGNAL('turbo_on'),self.setTurboTextOn)
		self.connect(self.tic,QtCore.SIGNAL('turbo_off'),self.setTurboTextOff)
		self.connect(self.tic,QtCore.SIGNAL('pressure'),self.setPressure)
		self.connect(self.tic,QtCore.SIGNAL('ion_pressure'),self.setIonPressure)

		# Connect ion worker signals
		self.ion_button_on.clicked.connect(lambda: self.q.put(self.tic.Ion_on))
		self.ion_button_off.clicked.connect(lambda: self.q.put(self.tic.Ion_off))
		self.neg_button_on.clicked.connect(lambda: self.q.put(self.tic.Neg_on))
		self.neg_button_off.clicked.connect(lambda: self.q.put(self.tic.Neg_off))
		self.connect(self.tic,QtCore.SIGNAL('block_print'),self.blockPrint)
		self.connect(self.tic,QtCore.SIGNAL('enable_print'),self.enablePrint)
		self.connect(self.tic,QtCore.SIGNAL('ion_on'),self.setIonTextOn)
		self.connect(self.tic,QtCore.SIGNAL('ion_off'),self.setIonTextOff)
		self.connect(self.tic,QtCore.SIGNAL('neg_on'),self.setNegTextOn)
		self.connect(self.tic,QtCore.SIGNAL('neg_off'),self.setNegTextOff)
	
	# checks queue and calls functions. Runs indefinitely
	def queueRunner(self):
		while True:
			f = self.q.get()
			f()
			self.q.task_done()

	# thread that runs the queue
	def queueThread(self):
		queueWorker = threading.Thread(target=self.queueRunner)
		# daemon thread will close when application is closed
		queueWorker.setDaemon(True)
		queueWorker.start()

	# thread that checks pump states and pressure
	def cycleThread(self):
		cycle_thread = threading.Thread(target=self.cycleCheck)
		cycle_thread.setDaemon(True)
		cycle_thread.start()

	# pump down and vent threads
	def pumpDownThread(self):	
		pumpdown_thread = threading.Thread(target=self.tic.Pump_down)
		pumpdown_thread.setDaemon(True)
		pumpdown_thread.start()

	def ventThread(self):	
		vent_thread = threading.Thread(target=self.tic.Vent)
		vent_thread.setDaemon(True)
		vent_thread.start()

	# plotting thread
	def autoPlotThreader(self):
		plot_thread = threading.Thread(target=self.Auto_plotter)
		plot_thread.start()	

	# live plotting
	def Auto_plotter(self):
		self.tic.plotting = True
		n = 1
		while self.tic.plotting == True:
			if n == 1:		
				# create dat pressure log with todays date
				datfile = self.tic.Create_dat()

			self.q.put(self.tic.Collect_data)
			time.sleep(3)
			self.tic.Update_dat(datfile, self.tic.graph_window.date[-1], self.tic.graph_window.pressure[-1])
			
			if n == 2:
				# call plot window
				self.emit(QtCore.SIGNAL('create_new_window'),False)
			
			elif n > 2:
				# update plot window
				self.emit(QtCore.SIGNAL('update_window'),True)

			n += 1
			printDebug('Sleeping...')
			time.sleep(30)

	# on/off pump switch configurations
	def ionSwitch(self):
		# if ion pump is turned on change to green and 'ON'
		if self.ion_switch.isChecked():  
			self.tic.Ion_on()
        # if ion pump is turned off change to red and 'OFF'
		else: 
			self.tic.Ion_off()

	def setIonTextOn(self):
		self.ion_switch.setChecked(True)
		self.ion_switch.setText('ON')

	def setIonTextOff(self):
		self.ion_switch.setChecked(False)
		self.ion_switch.setText('OFF')

	def negSwitch(self):
		# if NEG pump is turned on change to green and 'ON'
		if self.neg_switch.isChecked():  
			self.tic.Neg_on()
        # if NEG pump is turned off change to red and 'OFF'
		else: 
			self.tic.Neg_off()

	def setNegTextOn(self):
		self.neg_switch.setChecked(True)
		self.neg_switch.setText('ON')

	def setNegTextOff(self):
		self.neg_switch.setChecked(False)
		self.neg_switch.setText('OFF')
		
	def backingSwitch(self):
		# if backing pump is turned on change to green and 'ON'
		if self.backing_switch.isChecked(): 
			self.tic.Backing_on()
        # if backing pump is turned off change to red and 'OFF'
		else: 
			self.tic.Backing_off()

	def setBackingTextOn(self):
		self.backing_switch.setChecked(True)
		self.backing_switch.setText('ON')

	def setBackingTextOff(self):
		self.backing_switch.setChecked(False)
		self.backing_switch.setText('OFF')

	def turboSwitch(self):
		# if turbo pump is turned on change to green and 'ON'
		if self.turbo_switch.isChecked(): 
			self.tic.Turbo_on()
        # if turbo pump is turned off change to red and 'OFF'
		else: 
			self.tic.Turbo_off()

	def setTurboTextOn(self):
		self.turbo_switch.setChecked(True)
		self.turbo_switch.setText('ON')

	def setTurboTextOff(self):
		self.turbo_switch.setChecked(False)
		self.turbo_switch.setText('OFF')
	
	# pulls up new graphing window (window.py)
	def create_new_window(self, dat_file):
		printInfo('Plotting...')
		self.tic.graph_window.show()
		self.tic.graph_window.Plot(dat_file)

	# pump status checks
	def Backing_check(self):
		status = self.tic.Backing_check()
		if status == '4':
			printInfo('Backing pump is on')
			self.setBackingTextOn()
		elif status == '0':
			printInfo('Backing pump is off') 
			self.setBackingTextOff()
		elif status == '1':
			printInfo('Backing pump is turning on')
			self.setBackingTextOn()
		elif status == '2' or status == '3':
			printInfo('Backing pump is turning off') 
			self.setBackingTextOff()
		else:
			printError('Backing pump state unknown')

	def Ion_check(self):
		ion_status, neg_status = self.tic.Status_check()
		if ion_status == 'IP ON':
			printInfo('Ion pump is on')
			self.setIonTextOn()
			if self.tic.pressure_reading > 1e-5:
				printWarning('Pressure is too high (> 1e-5 Torr) for ion pump to function')
				self.q.put(self.tic.Ion_off)
			else:
				pass
		elif ion_status == 'IP OFF':
			printInfo('Ion pump is off')
			self.setIonTextOff()
		else:
			printError('Ion pump state unknown')

		if any("NP ON" in s for s in neg_status):
			printInfo('NEG pump is on')
			self.setNegTextOn()
			if self.tic.pressure_reading > 1e-4:
				printWarning('Pressure is too high (> 1e-4 Torr) for NEG pump to function')
				self.q.put(self.tic.Neg_off)
			else:
				pass
		elif any("NP OFF" in s for s in neg_status):
			printInfo('NEG pump is off')
			self.setNegTextOff()
		else:
			printError('NEG pump state unknown')

	def Turbo_check(self):
		status = self.tic.Turbo_check()
		if status == '4':
			printInfo('Turbo pump is on')
			self.setTurboTextOn()
		elif status == '0':
			printInfo('Turbo pump is off')
			self.setTurboTextOff()
		elif status == '6' or status == '7':
			printInfo('Turbo pump is braking') 
			self.setTurboTextOff()
		elif status == '5':
			printInfo('Turbo pump is accelerating')
			self.setTurboTextOn()
		elif status == '1':
			printInfo('Turbo pump is starting with delay')
			self.setTurboTextOn()
		elif status == '2' or status == '3':
			printInfo('Turbo pump is stopping with delay')
			self.setTurboTextOff()
		else:
			printError('Turbo pump state unknown')

	def cycleCheck(self):
		while True:
			time.sleep(10)
			self.q.put(self.Backing_check)
			time.sleep(10)
			self.q.put(self.Turbo_check)
			time.sleep(10)
			self.q.put(self.Ion_check)
			time.sleep(10)
			self.q.put(self.tic.Collect_data)
		
	# pressure updates
	def setPressure(self,pressure):
		self.tic.pressure_reading = float(pressure)
		self.tic_pressureText.setText(str(self.tic.pressure_reading)+" Torr")

	def setIonPressure(self,pressure):
		self.tic.ion_pressure_reading = float(pressure)
		if self.tic.ion_pressure_reading == 0:
			self.ion_pressureText.setText("Ion Gauge Off")
		else:
			self.ion_pressureText.setText(str(self.tic.ion_pressure_reading)+" Torr")
			
	# vent warning message
	def ventDialog(self):
		msg = QtGui.QMessageBox(self.centralwidget)
		msg.setIcon(QtGui.QMessageBox.Warning)
		msg.setText("Are you sure you want to vent the system? This will take approximately 4 hours. There is no way to abort a vent procedure.")
		msg.setWindowTitle("Vent Warning")
		msg.setStandardButtons(QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel)
		msg.setDefaultButton(QtGui.QMessageBox.Cancel)
		ret = msg.exec_();

		if ret == QtGui.QMessageBox.Ok:
			printInfo('Starting vent procedure...')			
			self.ventThread
		elif ret == QtGui.QMessageBox.Cancel:
			printInfo('Vent procedure canceled...')

	# pump down warning message
	def pumpDownDialog(self):
		msg = QtGui.QMessageBox(self.centralwidget)
		msg.setIcon(QtGui.QMessageBox.Warning)
		msg.setText("Are you sure you want to pump down the system? This will take approximately 36 hours. You can abort a pump down procedure.")
		msg.setWindowTitle("Pump Down Warning")
		msg.setStandardButtons(QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel)
		msg.setDefaultButton(QtGui.QMessageBox.Cancel)
		ret = msg.exec_();

		if ret == QtGui.QMessageBox.Ok:
			printInfo('Starting pump down procedure...')			
			self.pumpDownThread
		elif ret == QtGui.QMessageBox.Cancel:
			printInfo('Pump down canceled...')

		# importing data from a .dat file
	def importFile(self):
		printInfo('Select a .dat file to import a pressure log...')
		dialog = QtGui.QFileDialog		
		filepath = dialog.getOpenFileName(self, 'Select dat file', '.', 'DAT files(*.dat)')
		filename = str(filepath.split("/")[-1])
		
		try:
			c = np.loadtxt(filename,unpack=True,delimiter=',',skiprows=1,usecols=(0,1))
			self.tic.graph_window.import_date = c[0,:]
			self.tic.graph_window.import_pressure = c[1,:]
			self.create_new_window(True)
		except:
			printInfo('Pressure log import canceled')

	# close connection
	def Close(self):
		self.tic.ser.close()
		exit()

	# Restores sys.stdout and sys.stderr
	def __del__(self):
		sys.stdout=sys.__stdout__
		sys.stderr=sys.__stderr__

	# Write to textBox textEdit
	def normalOutputWritten(self,text):		
		self.textEdit.insertPlainText(text)
		# set scroll bar to focus on new text			
		sb = self.textEdit.verticalScrollBar()
		sb.setValue(sb.maximum()- .8 * sb.singleStep())

	# on exit
	def CloseEvent(self, event):
		self.Close()

#--------------------------------------------------------------------
#SERIAL CLASSES
#--------------------------------------------------------------------

class TIC(QtCore.QObject):
	# base TIC commands
	TERMINAL = chr(13) #carriage return

	PRECEDING_QUERY = '?'
	PRECEDING_COMMAND = '!'
	PRECEDING_REPLY = '*'
	PRECEDING_RESPONSE = '='

	TYPE_COMMAND = 'C'
	TYPE_VALUE = 'V'
	TYPE_SETUP = 'S'

	SEPARATOR = ' '
	DATA_SEPARATOR = ';'

	ON = '1'
	OFF = '0'

	TURBO_PUMP = '904'
	BACKING_PUMP = '910'
	GAUGE_1 = '913'
	nEXT_PUMP = '852'
	nEXT_VENT = '853'

	# NEXTorr commands - consist of command identifier, carriage return, line feed
	STATUS = 'TS\r\n'
	PRESSURE = 'Tt\r\n' # in torr
	IP_ON = 'G\r\n'
	IP_OFF = 'B\r\n'
	NP_ON = 'GN\r\n'
	NP_OFF = 'BN\r\n'

	def __init__(self, parent=None):
		super(self.__class__, self).__init__(parent)
		
		# connect to the TIC through serial port
		# ll /sys/class/tty/ttyUSB* to check port number
		try:
			self.ser = serial.Serial(port = '/dev/ttyUSB0',
						        baudrate=9600,
						        bytesize=serial.EIGHTBITS,
						        parity=serial.PARITY_NONE,
						        stopbits=serial.STOPBITS_ONE,
								timeout=.5)   
			self.sio = io.TextIOWrapper(io.BufferedRWPair(self.ser, self.ser))
			printInfo('Connected to TIC Controller')

		except:
			printError('Could not connect to TIC Controller')

		# connect to the NEXTorr controller through serial port
		try:
			self.serIon = serial.Serial(port = '/dev/ttyUSB1',
										baudrate=115200,
										bytesize=serial.EIGHTBITS,
										parity=serial.PARITY_NONE,
										stopbits=serial.STOPBITS_ONE,
										timeout=.5)   

			self.sioIon = io.TextIOWrapper(io.BufferedRWPair(self.serIon, self.serIon))
			printInfo('Connected to NEXTorr Power Supply')

		except:
			printError('Could not connect to NEXTorr Power Supply')

		# list of TIC commands - consist of preceding identifier, message type, object ID, space, data, cr
		self.turbo_on = "".join([self.PRECEDING_COMMAND,self.TYPE_COMMAND,self.TURBO_PUMP,self.SEPARATOR,self.ON,self.TERMINAL]) 
		self.turbo_off = "".join([self.PRECEDING_COMMAND,self.TYPE_COMMAND,self.TURBO_PUMP,self.SEPARATOR,self.OFF,self.TERMINAL]) 
		self.turbo_check = "".join([self.PRECEDING_QUERY,self.TYPE_VALUE,self.TURBO_PUMP,self.TERMINAL]) 

		self.backing_on = "".join([self.PRECEDING_COMMAND,self.TYPE_COMMAND,self.BACKING_PUMP,self.SEPARATOR,self.ON,self.TERMINAL]) 
		self.backing_off = "".join([self.PRECEDING_COMMAND,self.TYPE_COMMAND,self.BACKING_PUMP,self.SEPARATOR,self.OFF,self.TERMINAL]) 
		self.backing_check = "".join([self.PRECEDING_QUERY,self.TYPE_VALUE,self.BACKING_PUMP,self.TERMINAL])

		self.gauge_read = "".join([self.PRECEDING_QUERY,self.TYPE_VALUE,self.GAUGE_1,self.TERMINAL])

		# instance of graphing window class
		self.graph_window = SecondUiClass()
		self.plotting = True

		# pressure holder
		self.pressure_reading = 0
		self.ion_pressure_reading = 0

	# general TIC write message and read response
	def write_msg(self, message):
		# writing to the TIC outputs bites so have to suppress write output
		self.emit(QtCore.SIGNAL('block_print'),'')
		time.sleep(.2)
		self.sio.write(unicode(message))
		self.sio.flush()
		self.emit(QtCore.SIGNAL('enable_print'),'')

		# read response
		raw_message = self.sio.readline()
		printDebug(raw_message)

		# parse response
		try:
			preceding = raw_message[0]
			type = raw_message[1]
			object = raw_message[2:5]
			data = str(raw_message[5:-1])
			data = data.strip() #removes blank spaces
			terminal = raw_message[-1]

			# possible errors 
			errors = {'0' : 'No error',
				'1' : 'Invalid command for object ID',
                '2' : 'Invalid query/command',
                '3' : 'Missing parameter',
                '4' : 'Parameter out of range',               
                '5' : 'Invalid command in current state',
                '6' : 'Data checksum error',
                '7' : 'EEPROM read or write error',
                '8' : 'Operation took too long',
                '9' : 'Invalid config ID'}

			# log and print errors and updates
			if data != '0' and preceding == self.PRECEDING_REPLY:
				if object == self.BACKING_PUMP:
					printError('Backing pump command error ' + data + ': ' + errors[data])
				elif object == self.nEXT_PUMP:
					printError('Turbo pump error code ' + data + ': ' + errors[data])
			elif data == '0' and preceding == self.PRECEDING_REPLY:
				if object == self.BACKING_PUMP:
					printInfo('Backing pump command successful')
				elif object == self.nEXT_PUMP:
					printInfo('Turbo pump command successful')
			# return any necessary info
			elif object == self.GAUGE_1:
				return data.split(';')[0]
			elif object == self.BACKING_PUMP:
				return data.split(';')[0]
			elif object == self.TURBO_PUMP:
				return data.split(';')[0]
		except: 
			printError('No response was received from the TIC Controller')

	def Backing_on(self):
		printInfo('Turning backing pump on...')
		self.emit(QtCore.SIGNAL('backing_on'),'')
		self.write_msg(self.backing_on)

	def Backing_off(self):
		if self.pressure_reading > 6:
			printInfo('Turning backing pump off...')
			self.emit(QtCore.SIGNAL('backing_off'),'')
			self.write_msg(self.backing_off)
			
		else:
			printWarning('Pressure too low to turn off backing pump')	
			self.emit(QtCore.SIGNAL('backing_on'),'')
		
	def Backing_check(self):
		printInfo('Checking backing pump status...')
		return self.write_msg(self.backing_check)

	def Turbo_on(self):
		if self.pressure_reading < .005:
			printInfo('Turning turbo pump on...')
			self.emit(QtCore.SIGNAL('turbo_on'),'')
			self.write_msg(self.turbo_on)
			
		else:
			printWarning('Pressure too high to turn on turbo pump, wait until pressure is < 5 mTorr')
			self.emit(QtCore.SIGNAL('turbo_off'),'')

	def Turbo_off(self):
		if self.pressure_reading > 1e-6:
			printInfo('Turning turbo pump off...')
			self.emit(QtCore.SIGNAL('turbo_off'),'')
			self.write_msg(self.turbo_off)
			
		else:
			printWarning('Pressure too low to turn off turbo pump, wait until pressure is > 1e-6 Torr')
			self.emit(QtCore.SIGNAL('turbo_on'),'')

	def Turbo_check(self):
		printInfo('Checking turbo pump status...')
		return self.write_msg(self.turbo_check)

	# graphing code
	def Gauge_read(self):
		printInfo('Checking pressure...')
		timestamp = mdates.date2num(datetime.datetime.now())
		try:
			pressure_check = self.write_msg(self.gauge_read)
			convert2torr = float(pressure_check) * 760 / 101325
			convert2scientific = "{:.2e}".format(convert2torr)
			printInfo('Gauge reads: ' + convert2scientific + ' Torr')
			self.emit(QtCore.SIGNAL('pressure'),convert2scientific)
			return convert2torr, timestamp;
		except:
			printError('No response was received from the TIC Controller')
			pressure_check = ''
			return pressure_check, timestamp;

	# save gauge data
	def Collect_data(self):
		pressure, timestamp = self.Gauge_read()
		ion_pressure = self.Ion_gauge()
		self.graph_window.pressure = np.append(self.graph_window.pressure, pressure)
		self.graph_window.date = np.append(self.graph_window.date, timestamp)
		self.graph_window.ion_pressure = np.append(self.graph_window.ion_pressure, ion_pressure)

	def Stop_plotting(self):
		self.plotting = False
		printInfo('Stopping plot...')

	# create pressure data log
	def Create_dat(self):
		filename = datetime.datetime.now().strftime("%Y.%m.%d")
		i = ''
		while True:
			if os.path.isfile(filename + i + '.dat'):
				if i:
					i = '('+str(int(i[1:-1])+1)+')' # Append 1 to number in brackets
				else:
					i = '(1)'
			else:
				break

		filename = filename + "%s.dat" % i
		with open(filename, "w") as tempLog:
			tempLog.seek(0,0)
			tempLog.write('Float date' + ',' + 'Pressure (Torr)' + ',' + 'Date' '\n')
		return filename

	# update pressure data log
	def Update_dat(self, filename, timestamp, pressure):
		with open(filename,'a') as tempLog:
			tempLog.write(str(timestamp) + ',' + str(pressure) + ',' + str(mdates.num2date(timestamp)) + '\n')

### need to fix automated procedures ###
	# automated pump procedure
	def Pump_down(self):
		self.Backing_on()
		self.Gauge_read()
		self.autoPlotThread()
		while self.pressure[-1] > .001:
			print 'sleeping back'
			time.sleep(10)
		self.Turbo_on()
		#ion stuff		
		#while self.pressure[-1] > whatever:
		#	print 'sleeping turb'
		#	time.sleep(10)
		#self.Ion_on()

	# automated vent procedure
	def Vent(self):
		#ion stuff		
		self.Turbo_off()
		self.Gauge_read()
		self.autoPlotThread()
		while self.pressure[-1] < .08:
			print 'sleeping back'
			time.sleep(10)
		self.Backing_off()

	# general NEXTorr write message and read response
	@QtCore.pyqtSlot()
	def write_ion(self, message):
		self.emit(QtCore.SIGNAL('block_print'),'')
		time.sleep(.2)
		self.sioIon.write(unicode(message))
		self.sioIon.flush()
		self.emit(QtCore.SIGNAL('enable_print'),'')
	
		# print response
		raw_message = self.sioIon.readline()
		printDebug(raw_message)
		return raw_message

	# message commands:
	@QtCore.pyqtSlot()
	def Ion_on(self):
		if self.pressure_reading < 1e-5:
			printInfo('Turning ion pump on...')
			self.emit(QtCore.SIGNAL('ion_on'),'')
			check = self.write_ion(self.IP_ON)
			if '$' in check:
				printInfo('Ion pump command successful')
			else:
				printError('Ion pump command error')
		else:
			printWarning('Pressure too high to turn on ion pump, wait until pressure is < 1e-5 Torr.')
			self.emit(QtCore.SIGNAL('ion_off'),'')

	@QtCore.pyqtSlot()	
	def Ion_off(self):
		print 'Turning ion pump off...'
		self.emit(QtCore.SIGNAL('ion_off'),'')
		check = self.write_ion(self.IP_OFF)
		if '$' in check:
			printInfo('Ion pump command successful')
		else:
			printError('Ion pump command error')

	@QtCore.pyqtSlot()
	def Neg_on(self):
		if self.pressure_reading < 1e-4:
			print 'Turning NEG pump on...'
			self.emit(QtCore.SIGNAL('neg_on'),'')
			check = self.write_ion(self.NP_ON)
			if '$' in check:
				printInfo('NEG pump command successful')
			else:
				printError('NEG pump command error')
		else:
			printWarning('Pressure too high to turn on NEG pump, wait until pressure is < 1e-4 Torr.')
			self.emit(QtCore.SIGNAL('neg_off'),'')

	@QtCore.pyqtSlot()	
	def Neg_off(self):
		print 'Turning NEG pump off...'
		self.emit(QtCore.SIGNAL('neg_off'),'')
		check = self.write_ion(self.NP_OFF)
		print check
		if '$' in check:
			printInfo('NEG pump command successful')
		else:
			printError('NEG pump command error')

	@QtCore.pyqtSlot()
	def Status_check(self):
		printInfo('Checking ion/NEG pump status...')
		status = self.write_ion(self.STATUS)
		ion_status = status.split(',')[0]
		split_status = status.split(',')
		return ion_status, split_status;

	def Ion_gauge(self):
		printInfo('Checking NEXTorr gauge...')
		try:
			status = self.write_ion(self.PRESSURE)
			ion_reading = float(status.rstrip())
			printInfo('Ion gauge reads: ' + str(ion_reading) + ' Torr')
			self.emit(QtCore.SIGNAL('ion_pressure'),ion_reading)
			return ion_reading
		except:
			printError('No response was received from the NEXTorr Power Supply')
			ion_reading = ''
			return ion_reading

#Start/Run GUI window
if __name__=='__main__':
	app=QtGui.QApplication(sys.argv)
	GUI=MainUiClass()
	GUI.show()
	sys.exit(app.exec_())
