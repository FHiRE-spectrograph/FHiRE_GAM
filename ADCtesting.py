from PyQt5 import QtGui,QtCore,QtWidgets,uic
from PyQt5.QtCore import QThread,pyqtSignal
import time, math
import RPi.GPIO as gpio

import adcwindow #imports PyQt ADC testing window
import easydriver as ed #imports GPIO stuff for focuser

#Initialize ADC stepper motors
#steps pin, delay, direction pin, MS1, MS2, MS3, sleep pin, enable pin, reset pin
stepper2 = ed.easydriver(13, 0.04, 32, 18, 11, 22, 0, 36, 0, 'stepper2') #top
stepper3 = ed.easydriver(16, 0.04, 32, 18, 11, 22, 0, 40, 0, 'stepper3') #bottom

stepper2.set_direction(True)
stepper3.set_direction(True)

#Initialize ADC microswitches
class switch(object):
	def __init__(self, pin_out=0, pin_in=0, name='switch'):
		self.pin_out = pin_out
		self.pin_in = pin_in
		gpio.setmode(gpio.BOARD)
		gpio.setwarnings(False)

		#check that pins have been defined & setup input/output
		#**Important that no other GPIO pins set to output other than 37, 38. 3.3k resistors added to 37 and 38 to protect against the microswitch shorting GPIO pins.**
		if self.pin_out in [37,38]:
			gpio.setup(self.pin_out, gpio.OUT)
			gpio.output(self.pin_out, 0)
			print("pin %s set to output: %s" %(self.pin_out, gpio.input(self.pin_out)))

		if self.pin_in in [31,35]:
			gpio.setup(self.pin_in, gpio.IN, pull_up_down=gpio.PUD_DOWN) 
			print("pin %s set to input: %s" %(self.pin_in, gpio.input(self.pin_in)))

	def pin_start(self):
		gpio.output(self.pin_out, 1)
		print("%s output turned on: %s" %(self.pin_out, gpio.input(self.pin_out)))
	def pin_stop(self):
		gpio.output(self.pin_out, 0)
		print("%s output turned off: %s" %(self.pin_out, gpio.input(self.pin_out)))

top_switch = switch(38,35) #microswitch out, in
bottom_switch = switch(37,31) 

class ADCTestingWindow(QtWidgets.QMainWindow, adcwindow.Ui_ADC):
	def __init__(self,main):
		self.main = main
		super(ADCTestingWindow,self).__init__(main)
		self.setupUi(self)

		self.pb_adcHome.pressed.connect(self.main.adcthread.ADC_home) 

	def adc_top(self,top):
		self.top = top

	def adc_bot(self,bot):
		self.bot = bot
		self.adc_current()

	#Current ADC position in steps
	def adc_current(self):
		self.lbl_afocus1.setText("Top: %s" %self.top)
		self.lbl_afocus2.setText("Bottom: %s" %self.bot)

class ADCThread(QtCore.QThread):
	sig1 = pyqtSignal('PyQt_PyObject')
	sig2 = pyqtSignal('PyQt_PyObject')
	
	def __init__(self,main):
		self.main = main
		super(ADCThread,self).__init__(main)
		
		self.j = 0; self.k = 0

		self.telra = 1
		self.teldec = 1
		self.telhum = 1
		self.teltemp = 1
		self.telutc = 1
		self.telhad = 1
		self.z = 1

	def run(self):
		time.sleep(8)
		self.ADC_home()
		print("ADC set home finished")
		time.sleep(6)
		while 1:	
			self.updatePosition()
			print(self.teldec)
			self.calc_steps_top()
			#self.move_steps_top()
			self.calc_steps_bottom()
			#self.move_steps_bottom()
			print("Here")
			time.sleep(10)

	#------------Top prism----------------------#
	#finds parallactic angle and aligns top prism to parallactic 
	#angle and bottom prism to zero correction position
	def calc_steps_top(self):
		obslat = 41.097056 #[degrees]
		had_r = math.radians(float(self.telhad))
		obslat_r = math.radians(float(obslat))
		dec_r = math.radians(float(self.teldec))

		print("Dec: %s" %dec_r)
		
		#finds sin of parallactic angle
		sinpar = (math.sin(had_r)*math.cos(obslat_r))/(1.-(math.sin(obslat_r)*math.sin(dec_r)+math.cos(obslat_r)*math.cos(dec_r)*math.cos(had_r))**2)**0.5	

		#gets parallactic angle in degrees
		par_angle = math.degrees(math.asin(sinpar))
		print("Parallactic: %s" %par_angle)

		#converts parallactic angle into motor steps (?)from home(?)
		parstepsfloat = par_angle/.315 
		self.parstepsint = int(parstepsfloat)
		print("Top Prism move: %s steps" %self.parstepsint)
		
	def move_steps_top(self):
		if self.top_abs > self.parstepsint:
			while self.j > self.parstepsint:
				stepper2.set_direction(False) 
				stepper2.step()
				self.top_abs -= 1
		elif self.top_abs < self.parstepsint:
			while self.j < self.parstepsint:
				stepper2.set_direction(True)
				stepper2.step()
				self.top_abs += 1
		
		self.sig1.emit(self.top_abs)
		stepper2.set_direction(True)

	#----------------Bottom prism-------------------#
	def calc_steps_bottom(self):
		M = .02897 #[kg/mole]		
		g = 9.80665 #[m/s**2]
		R = 8.3144598 #[J/mol*K]
		T_b = 288.15 #[kelvin]
		lam_naught = 0.5 #[microns]
		P_sea = 101325 #[pascals]
		altitude = 2943 #[meters]
		nglass = 1
		lam = 1

		#finds atmospheric differential dispersion relative to .5 microns
		#in arc seconds as a function of pressure, temperature, humidity and zenith angle
		P = float((P_sea*math.exp((-g*M*altitude)/(R*T_b)))/133.322)	#mmHg --- what is M?
		#--#Hum_cor = ((0.0624-(0.00068/(lam**2)))/(1+(0.003661*T)))*hum   #scale the things
		N_sea5 = float(((1/(10**6))*(64.328+(29498.1/(146-((1/lam_naught)**2)))+(255/(41-((1/lam_naught)**2)))))+1)
		
		N_WIRO5 = float(((N_sea5-1)*((P*(1+((1.049-(0.0157*self.teltemp))*(10**-6)*P)))/(720.883*(1+(0.003661*self.teltemp)))))+1)
		N_sea = float(((1/(10**6))*(64.328+(29498.1/(146-((1/lam)**2)))+(255/(41-((1/lam)**2)))))+1)
		N_WIRO = float(((N_sea5-1)*((P*(1+((1.049-(0.0157*self.teltemp))*(10**-6)*P)))/(720.883*(1+(0.003661*self.teltemp)))))+1)
		Delta = float((N_WIRO-N_WIRO5)*math.tan(self.z))

		#compares value of atmospheric diffraction with needed value of correction and displaces bottom prism
		F = 14925 # focal length in mm
		prismangle = math.radians(15) #***Added temp.***
		H = math.tan(prismangle) # normalized prism base
		D = 269	# distance between prisms and focus mm
		nglass15 = 1.4623
		nglass1lam = nglass
		dnglass1 = nglass15-nglass1lam
		Fee = math.degrees(math.acos((1/H)*math.tan((F*Delta)/(D*(dnglass1))))) 
		stepsfloat = Fee/.315
		stepsint = int(stepsfloat)
		self.bot_steps = self.top_abs+stepsint
		print("Bottom Prism move: %s steps" %self.bot_steps)

	def move_steps_bottom(self):
		print("bottom steps: %s" %self.bot_abs)
		
		if self.k > self.bot_steps:
			while self.k > self.bot_steps:
				stepper3.set_direction(False)
				stepper3.step()
				self.k -= 1
				self.bot_abs -= 1
		elif self.k < self.bot_steps:
			while self.k < self.bot_steps:
				stepper3.set_direction(True)
				stepper3.step()
				self.k += 1
				self.bot_abs +=1
		
		print("k: %s" %self.k)
		self.sig2.emit(self.bot_abs)
		stepper3.set_direction(True)

	def updatePosition(self):
		lat = math.radians(41.097)
		lon = math.radians(105.977)

		#Outside temperature in celsius
		fileopen = open("/home/fhire/Desktop/Telinfo","r")
		self.telinfo = fileopen.read()
		
		teltemp = self.telinfo.split('\n')[66].split('>')[1].split('<')[0]
		self.teltemp = float(teltemp.replace('\U00002013','-'))
		#Outside humidity --- in percentage ***NEEDS TO BE IN mmhg***
		self.telhum = float(self.telinfo.split('\n')[71].split('>')[1].split('<')[0])
		#Hour Angle in degress
		self.telhad = float(self.telinfo.split('\n')[41].split('>')[1].split('<')[0])
		#RA in hour:minute:seconds
		self.telra = self.telinfo.split('\n')[26].split('>')[1].split('<')[0] 
		#Current UTC 	
		self.telutc = self.telinfo.split('\n')[16].split('>')[1].split('<')[0]
		#DEC in hour:minute:seconds
		self.teldec = self.telinfo.split('\n')[31].split('>')[1].split('<')[0]
		
		#Convert RA to degrees
		rahour = float(self.telra.split(":")[0])
		raminute = float(self.telra.split(":")[1])
		raseconds = float(self.telra.split(":")[2])
		RaD = rahour+raminute/60+raseconds/3600
		self.telra = RaD
		#Convert dec to degrees
		dechour = float(self.teldec.split(":")[0])
		decminute = float(self.teldec.split(":")[1])
		decseconds = float(self.teldec.split(":")[2])
		self.teldec = dechour+decminute/60+decseconds/3600
	
		print("RA: %s\nDEC: %s\nUTC: %s\nHUM: %s\nTEMP: %s C\nHA: %s" %(self.telra,self.teldec,self.telutc,self.telhum,self.teltemp,self.telhad))
	
		#Zenith calculation
		t0 = math.radians(90-lat)
		t1 = math.radians(90-RaD) 
		p0 = math.radians(lon)
		p1 = math.radians(RaD)
		
		zz = math.cos(t0)*math.cos(t1)+math.sin(t0)*math.sin(t1)*math.cos(p1-p0)
		self.z = math.acos(zz) #zenith angle [radians]
		
		fileopen.close()
		
	def ADC_home(self):
		bottom_switch.pin_start()
		time.sleep(0.05)
		if gpio.input(31) == 1: #send bottom ADC home
			while gpio.input(31) == 1:
				stepper3.step()
				time.sleep(0.05)
		bottom_switch.pin_stop()
		top_switch.pin_start()
		if gpio.input(35) == 1: #send top ADC home
			while gpio.input(35) == 1:
				stepper2.step()
				time.sleep(0.05)

		print("ADC sent home")
		top_switch.pin_stop()

		self.top_abs = 0
		self.bot_abs = 0
		self.sig1.emit(self.top_abs)
		self.sig2.emit(self.bot_abs)

	def stop(self):
		gpio.cleanup()
		self.terminate()











	
