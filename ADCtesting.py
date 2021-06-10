# 
# Updated: 03/29/21
#
from PyQt5 import QtGui,QtCore,QtWidgets,uic
from PyQt5.QtCore import QThread,pyqtSignal
import time, math
import numpy as np
import RPi.GPIO as gpio

import adcwindow  # imports PyQt ADC testing window
import easydriver as ed  # imports GPIO stuff for focuser

# Initialize ADC stepper motors.
# steps pin, delay, direction pin, MS1, MS2, MS3, sleep pin, enable pin, reset pin
stepper2 = ed.easydriver(13, 0.04, 32, 18, 11, 22, 0, 36, 0, 'stepper2')  # top
stepper3 = ed.easydriver(16, 0.04, 32, 18, 11, 22, 0, 40, 0, 'stepper3')  # bottom

stepper2.set_direction(True)
stepper3.set_direction(True)

# Initialize ADC microswitches.
class switch(object):
	def __init__(self, pin_out=0, pin_in=0, name='switch'):
		self.pin_out = pin_out
		self.pin_in = pin_in
		gpio.setmode(gpio.BOARD)
		gpio.setwarnings(False)

		# Check that pins have been defined & setup input/output
		# **Important that no other GPIO pins set to output other than 
		# 37, 38. 3.3k resistors added to 37 and 38 to protect against 
		# the microswitch shorting GPIO pins.**
		if self.pin_out in [37,38]:
			gpio.setup(self.pin_out, gpio.OUT)
			gpio.output(self.pin_out, 0)
			#print("pin %s set to output: %s" %(
			#	self.pin_out, gpio.input(self.pin_out)))

		if self.pin_in in [31,35]:
			gpio.setup(self.pin_in, gpio.IN, pull_up_down=gpio.PUD_DOWN) 
			#print("pin %s set to input: %s" %(
			#	self.pin_in, gpio.input(self.pin_in)))

	def pin_start(self):
		gpio.output(self.pin_out, 1)
		#print("%s output turned on: %s" %(
		#		self.pin_out, gpio.input(self.pin_out)))
	def pin_stop(self):
		gpio.output(self.pin_out, 0)
		#print("%s output turned off: %s" %(
		#		self.pin_out, gpio.input(self.pin_out)))

top_switch = switch(38,35)  # microswitch out, in
bottom_switch = switch(37,31) 

class ADCTestingWindow(QtWidgets.QMainWindow, adcwindow.Ui_ADC):
	# Widget definitions
	def __init__(self, main):
		self.main = main

		super(ADCTestingWindow, self).__init__(main)
		self.setupUi(self)

		self.pb_adcHome.pressed.connect(self.main.adc_motor.ADC_home) 
		self.pb_adcHome.setStyleSheet("background-color: #95fef9; \
					       outline: none")

		#self.afocus1_lineEdit.returnPressed.connect(
		#		lambda:self.main.adc_motor.move_top(
		#			self.afocus1_lineEdit.text()))
		#self.afocus2_lineEdit.returnPressed.connect(
		#		lambda:self.main.adc_motor.move_bottom(
		#			self.afocus1_lineEdit.text()))

		#self.afocus1_btn_sub.pressed.connect(
		#		self.main.adc_motor.calc_steps_top)
		#self.afocus2_btn_sub.pressed.connect(
		#		self.main.adc_motor.calc_steps_bottom)

	def adc_top(self, top):
		self.top = top

	def adc_bot(self, bot):
		self.bot = bot
		self.adc_current()

	# Current ADC position in steps.
	def adc_current(self):
		self.top_current.setText(str(self.top))
		self.btm_current.setText(str(self.bot))

class ADCThread(QtCore.QObject):
	sig1 = pyqtSignal('PyQt_PyObject')
	sig2 = pyqtSignal('PyQt_PyObject')
	
	def __init__(self, parent=None):
		super(ADCThread, self).__init__(parent)

		self.telra   = 1
		self.teldec  = 1
		self.telhum  = 1
		self.teltemp = 1
		self.telutc  = 1
		self.telhad  = 1
		self.telP    = 1
		self.telairm = 1
		self.z       = 1		

		stepper3.disable() 
		stepper2.disable()

		self.stop_thread = False

	def run(self):
		time.sleep(8)
		self.ADC_home()
		print("ADC set home.")
		time.sleep(6)

		while 1:	
			#print("Updating ADC position.")
			#self.updatePosition()
			#self.calc_steps_top() 
			#self.calc_steps_bottom()
			#print("ADC update complete.")
			if self.stop_thread == True:
				print("ADCthread break")
				break
			time.sleep(1)

	#------------Top prism----------------------#
	# Finds parallactic angle and aligns top and bottom prism to parallactic angle.
	def calc_steps_top(self): 
		obslat = 41.097056  # degrees
		had_r = math.radians(float(self.telhad))
		obslat_r = math.radians(float(obslat))
		dec_r = math.radians(float(self.teldec))

		print("Dec: %s" %dec_r)
		
		# Finds tan of parallactic angle
		# Equation from https://sites.astro.caltech.edu/~mcs/CBI/pointing/ 
		# and Egner et al. 2010
		tanpar = (math.sin(had_r)) / ((math.tan(obslat_r) * math.cos(dec_r)) - 
					      (math.sin(dec_r) * math.cos(had_r)))

		# Gets parallactic angle in degrees.
		par_angle = math.degrees(math.atan(tanpar))
		print("Parallactic angle (preflip): %s degrees" %par_angle)

		#
		# Have to add or subtract 180 depending on hour angle and dec
		# if dec is higher than 41 degrees par angle should start at 
		# 180 instead of 0, and if HA is positive par values should 
		# be positive. If dec is lower par angle should start at 0, 
		# and if HA is negative values are negative.
		#
		if dec_r > obslat_r:
			if par_angle > 0 and had_r < 0:
				par_angle -= 180
			elif par_angle <= 0 and had_r >= 0:
				par_angle += 180

		# Add 360 to negative par angles to ensure smooth prism rotation.
		if dec_r > obslat_r and par_angle < 0:
			par_angle += 360

		print("Parallactic angle (postflip): %s degrees" %par_angle)

		# Converts parallactic angle into motor steps from home.
		parstepsfloat = par_angle / .315 
		self.parstepsint = int(parstepsfloat)

		#
		# Calculates rotation angle to move both top and bottom prism 
		# to account for dispersion at a given zenith angle, temperature, 
		# and pressure.
		#
		# 0.38 - 0.68 microns range of FHiRE
		lam_min = 0.38  # microns
		lam_max = 0.68  # microns
		
		# Equations (from https://refractiveindex.info/) to determine 
		# index of refraction for BaK2 and CaF2 prisms.
		# n1= BaK2, n2 = CaF2
		a0 = 2.319725
		a1 = 0.002602493
		a2 = 0.02249807
		a3 = -0.002672041
		a4 = 0.0003926686
		a5 = -2.043303*10**-5

		n1_min = np.sqrt(
			    a0 + (a1 * lam_min ** 2) + (a2 * lam_min ** (-2)) + 
			    (a3 * lam_min ** (-4)) + (a4 * lam_min ** (-6)) + 
			    (a5 * lam_min ** (-8)))

		n1_max = np.sqrt(
			    a0 + (a1 * lam_max ** 2) + (a2 * lam_max ** (-2)) + 
			    (a3 * lam_max ** (-4)) + (a4 * lam_max ** (-6)) + 
			    (a5 * lam_max ** (-8)))

		n1 = n1_max - n1_min

		b0 = 0.443749998
		b1 = 0.444930066
		b2 = 0.150133991
		b3 = 8.85319946
		b4 = 0.00178027854
		b5 = 0.00788536061
		b6 = 0.0124119491
		b7 = 2752.28175

		n2_min = (b0 * lam_min ** 2) / (lam_min ** 2 - b4) + \
			 (b1 * lam_min ** 2) / (lam_min ** 2 - b5) + \
			 (b2 * lam_min ** 2) / (lam_min ** 2 - b6) + \
			 (b3 * lam_min ** 2) / (lam_min ** 2 - b7)

		n2_min = np.sqrt(n2_min + 1)

		n2_max = (b0 * lam_max ** 2) / (lam_max ** 2 - b4) + \
			 (b1 * lam_max ** 2) / (lam_max ** 2 - b5) + \
			 (b2 * lam_max ** 2) / (lam_max ** 2 - b6) + \
			 (b3 * lam_max ** 2) / (lam_max ** 2 - b7)

		n2_max = np.sqrt(n2_max + 1)

		n2 = n2_max - n2_min

		# Equations from Filippenko 1982, Brescia et al. 2006, Tendulkar 2014.
		# Calculating atmospheric refraction for range of wavelengths min
		# to max.
		R_min_sealevel = float((
			64.328 + 29498.1 / (146 - lam_min ** (-2)) + 
			255.4 / (41 - lam_min ** (-2))) * 10 ** (-6))

		R_min_scaled = float(
			(R_min_sealevel) * self.telP * (1 + (1.049 - 0.0157 * 
								self.teltemp) *
							self.telP * 10 ** (-6)) /
		 	(720.883 * (1 + 0.003661 * self.teltemp)))

		R_max_sealevel = float(
			(64.328 + 29498.1 / (146 - lam_max ** (-2)) + 255.4 / 
			(41 - lam_max ** (-2))) * 10 ** (-6))

		R_max_scaled = float(
			(R_max_sealevel) * self.telP * (1 + (1.049 - 0.0157 * 
								self.teltemp) *
 							self.telP * 10 ** (-6)) /
 			(720.883 * (1 + 0.003661 * self.teltemp)))

		# Atmospheric dispersion in radians
		Delta = (self.telP / (760 + (2.9 * self.teltemp))) * \
			(R_min_scaled - R_max_scaled) * np.tan(self.z)

		print("Dispersion = %s rads" %Delta)

		# Compares value of atmospheric diffraction with needed value 
		# of correction and calculates rotation angle.

		# Focal length in mm ***change once finalized in Zemax***
		F = 12700.3  
		# Prism angle according to new ADC design.
		prismangle = math.radians(5.54)  
 		# Normalized prism base.
		H = math.tan(prismangle) 
		# Distance between prisms and focus mm.
		# ***change once finalized in Zemax.***
		D = 367.79  

		dnglass1 = n1 - n2
		
		#
		# There are two options to calculate the angle of prism rotation
		# both give similar curves (see ADC_test_graph.py for comparative
		# graphs of each) so decide which one to use after ADC finalized 
		# and tests are done.
		#

		# Equation from Brescia et al 2006 uses atmospheric dispersion.
		Phi = np.degrees(np.arccos(
					np.tan(F * Delta / (D * dnglass1)) / H)) - 90

		# or equation based on maximum zenith angle ADC desgined to 
		# correct (Tendulkar 2014).
		# Max zenith angle calculated to be ~83 from 7.4 arcsec max 
		# ADC dispersion.

		#max_z = (7.4 / 206265) * (760 + (2.9 * self.teltemp)) / (
		#			self.telP * (R_min_scaled - R_max_scaled))
		#max_z = np.degrees(np.arctan(max_z))
		#Phi = np.degrees(
		#	np.arcsin(np.tan(np.deg2rad(self.z)) / 
		#	np.tan(np.deg2rad(max_z))))

		print("Rotation angle = %s degrees" %Phi)
		rotstepsfloat = Phi / .315
		self.rotstepsint = int(rotstepsfloat)
		#total steps=parallactic angle + dispersion compensation angle 
		# of rotation.
		self.top_steps = self.parstepsint + self.rotstepsint
		
		print("Top Prism move: %s steps" %self.top_steps)
		
		self.move_steps_top()
		
	def move_steps_top(self):
		stepper2.enable()
		if self.top_abs > self.top_steps:
			while self.top_abs > self.top_steps:
				stepper2.set_direction(False) 
				stepper2.step()
				self.top_abs -= 1
		elif self.top_abs < self.top_steps:
			while self.top_abs < self.top_steps:
				stepper2.set_direction(True)
				stepper2.step()
				self.top_abs += 1
		
		self.sig1.emit(self.top_abs)
		stepper2.set_direction(True)
		# Disabling and enabling outputs prevent motors from getting 
		# too hot from idle current.
		stepper2.disable()

	#----------------Bottom prism-------------------#
	def calc_steps_bottom(self):
		# Bottom steps=top steps - 2*dispersion compensation angle of 
		# rotation (since already subtracted from top).
		self.bot_steps = self.top_abs - (2 * self.rotstepsint)
		print("Bottom Prism move: %s steps" %self.bot_steps)

		self.move_steps_bottom()

	def move_top(self, steps):
		self.top_steps = steps
	def move_bot(self, steps):
		self.bot_steps = steps

	def move_steps_bottom(self):
		print("bottom steps: %s" %self.bot_abs)
		stepper3.enable()
		if self.bot_abs > self.bot_steps:
			while self.bot_abs > self.bot_steps:
				stepper3.set_direction(True)
				stepper3.step()
				self.bot_abs -= 1
		elif self.bot_abs < self.bot_steps:
			while self.bot_abs < self.bot_steps:
				stepper3.set_direction(False)
				stepper3.step()
				self.bot_abs +=1
		
		self.sig2.emit(self.bot_abs)
		stepper3.set_direction(True)
		stepper3.disable()

	def updatePosition(self):
		lat = math.radians(41.097)
		lon = math.radians(105.977)

		# Outside temperature in fahrenheit.
		fileopen = open("/home/fhire/Desktop/Telinfo","r")
		self.telinfo = fileopen.read()
		
		teltemp = self.telinfo.split('\n')[66].split('>')[1].split('<')[0]
		self.teltemp = float(teltemp.replace('\U00002013','-'))
		# Convert to celsius.
		self.teltemp = (5*self.teltemp/9 - 5*32/9)
		# Outside humidity --- in percentage. ***NEEDS TO BE IN mmhg.***
		self.telhum = float(
			self.telinfo.split('\n')[71].split('>')[1].split('<')[0])
		# Hour Angle in degress.
		self.telhad = float(
			self.telinfo.split('\n')[41].split('>')[1].split('<')[0])
		# RA in hour:minute:seconds.
		self.telra = self.telinfo.split('\n')[26].split('>')[1].split('<')[0] 
		# Current UTC.
		self.telutc = self.telinfo.split('\n')[16].split('>')[1].split('<')[0]
		# DEC in hour:minute:seconds.
		self.teldec = self.telinfo.split('\n')[31].split('>')[1].split('<')[0]
		# Barometric pressure in inHg.
		self.telP = self.telinfo.split('\n')[76].split('>')[1].split('<')[0]
		self.telP = float(self.telP)*25.4  # mmHg
		# Airmass.
		self.telairm = self.telinfo.split('\n')[46].split('>')[1].split('<')[0]
		
		# Convert RA to degrees.
		rahour = float(self.telra.split(":")[0])
		raminute = float(self.telra.split(":")[1])
		raseconds = float(self.telra.split(":")[2])
		RaD = rahour+raminute/60+raseconds/3600
		self.telra = RaD
		# Convert dec to degrees.
		dechour = float(self.teldec.split(":")[0])
		decminute = float(self.teldec.split(":")[1])
		decseconds = float(self.teldec.split(":")[2])
		self.teldec = dechour+decminute/60+decseconds/3600
	
		print("RA: %s\nDEC: %s\nUTC: %s\nHUM: %s %%\nTEMP: %s C\n"
		      "HA: %s\nP: %s mmHg\nAirmass: %s" %(
				self.telra, self.teldec, self.telutc, self.telhum, 
				self.teltemp, self.telhad, self.telP, self.telairm))
	
		self.z = math.acos(1 / float(self.telairm))
		print("z: %s" %self.z)
		
		fileopen.close()
		
	def ADC_home(self):
		stepper3.enable()
		stepper2.enable()
		bottom_switch.pin_start()
		time.sleep(0.05)
		if gpio.input(31) == 1:  # send bottom ADC home
			while gpio.input(31) == 1:
				stepper3.step()
				time.sleep(0.05)
		bottom_switch.pin_stop()

		top_switch.pin_start()
		if gpio.input(35) == 1:  # send top ADC home
			while gpio.input(35) == 1:
				stepper2.step()
				time.sleep(0.05)

		#print("ADC sent home")
		top_switch.pin_stop()
		stepper3.disable()
		stepper2.disable()

		self.top_abs = 0
		self.bot_abs = 0
		self.sig1.emit(self.top_abs)
		self.sig2.emit(self.bot_abs)

	def stop(self):
		gpio.cleanup()
		self.stop_thread = True
		#self.terminate()
		#self.quit()











	
