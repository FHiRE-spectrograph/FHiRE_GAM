from pexpect import pxssh
import sys, time, os
import pyds9
import numpy as np
from PIL import Image
from astropy.io import fits
from pydng.core import RPICAM2DNG
from cr2fits import cr2fits
from PyQt5.QtCore import pyqtSignal
from PyQt5 import QtCore

class Clouds(QtCore.QObject):
	sig1 = pyqtSignal('PyQt_PyObject')
	sig2 = pyqtSignal('PyQt_PyObject')
	sig3 = pyqtSignal('PyQt_PyObject')
	sig4 = pyqtSignal('PyQt_PyObject')
	
	def __init__(self):
		super().__init__()
#		self.sig1 = pyqtSignal('PyQt_PyObject')
#		self.sig2 = pyqtSignal('PyQt_PyObject')
#		self.sig3 = pyqtSignal('PyQt_PyObject')
#		self.sig4 = pyqtSignal('PyQt_PyObject')
		

	def openDS9(self):			
		# Opens DS9 or points to existing window if already open.
		pyds9.DS9()
		# If called after taking an exposure open that exposure.
		#print("> Opening image in ds9...")
		os.system('xpaset -p ds9 fits ' + str('/home/fhire/Desktop/FHiRE_GAM/RefractorImage_temp-G.fits'))
		os.system('xpaset -p ds9 zoom to fit')
		os.system('xpaset -p ds9 zscale')
		
	def ssh(self):
		t = 1
		sleep = t + 2
		fname = 'RefractorImage_temp-G.fits'

		s = pxssh.pxssh()
		hostname = '10.214.214.115'
		username = 'fhire'
		password = 'WIROfhire17'
	
		s.login(hostname, username, password)
		print("Logged In")
		time.sleep(sleep)
	
		s.sendline('cd Desktop/FHiRE-Refractor/')
		print('Changing Directory')
		time.sleep(sleep)
		s.sendline('python3.7 refractor_camera_1.py') #Put a 1 after refractor_camera.py for a 1 second exposure 
							      #because it is the first index of the sys.argv array if necessary
		time.sleep(15)
		print('Copying fits')
		s.sendline('scp %s fhire@10.212.212.20:/home/fhire/Desktop/FHiRE_GAM' %fname)
		time.sleep(10)
		print('fhire@10.212.212.20\'s password:')
		time.sleep(sleep)
		i = s.expect('fhire@10.212.212.20\'s password:')
		if i == 0:
			#print("Sending Password")
			s.sendline(password)
			time.sleep(sleep)
			#lnk.expect(pxssh.EOF)
			#print("Password Sent")
		elif i ==1:
			#print("Got the key or connection timeout")
			pass
		
		s.logout()

	def Monitor(self):
		self.ssh()
		self.openDS9()
		image_data = fits.getdata('RefractorImage_temp-G.fits')
		self.baseline_count = np.mean(image_data)
		self.sig1.emit(1)
		#print('Mean:', count_mean)
		#print("BASELINE FOR COUNTS ESTABLISHED")
		#print("REMINDER: CHECK FOR CLOUDS")
		i = 1
		while i < 25:
			time.sleep(240)
			self.ssh()
			self.openDS9()
			image_data = fits.getdata('RefractorImage_temp-G.fits')
			self.mean_count = np.mean(image_data)
			if self.mean_count < (self.baseline_count * 0.95):
				#print("WARNING: POSSIBLE CLOUD COVER DETECTED")
				#print("CHECK FOR CLOUDS")
				Warn = 1
				self.sig2.emit(1)
				break
			i = i+1
		if i==25:
			self.sig3.emit(1)
		self.sig4.emit(1)

