#
# Updated: 02/17/21 
#
from PyQt5 import QtGui,QtCore,QtWidgets,uic
from PyQt5.QtCore import QThread,pyqtSignal
from pexpect import pxssh 
import time,pexpect

import vacuumwindow #imports PyQt vacuum window

class VacuumWindow(QtWidgets.QMainWindow, vacuumwindow.Ui_VacummWindow):
	#Widget definitions
	def __init__(self, main):
		self.main = main
		super(VacuumWindow,self).__init__(main)
		self.setupUi(self)

		#Toggle backing, turbo, ion pumps [admin]
		self.backing_btn.setCheckable(True)
		self.backing_btn.setStyleSheet("background-color: #c9d1d1")
		self.backing_btn.setStyleSheet("QPushButton:checked {background-color: #95fef9}") #blue/ON
		#self.backing_btn.pressed.connect(

		self.turbo_btn.setCheckable(True)
		self.turbo_btn.setStyleSheet("background-color: #c9d1d1")
		self.turbo_btn.setStyleSheet("QPushButton:checked {background-color: #95fef9}")
		#self.turbo_btn.pressed.connect(self.main.vacuumthread.printing)

		self.ion_btn.setCheckable(True)
		self.ion_btn.setStyleSheet("background-color: #c9d1d1")
		self.ion_btn.setStyleSheet("QPushButton:checked {background-color: #95fef9}")
		#self.ion_btn.pressed.connect(self.main.vacuumthread.continuePrinting)


class Vacuum(QtCore.QThread):
	signal = pyqtSignal('PyQt_PyObject')

	def __init__(self,parent=None):
		super(Vacuum,self).__init__(parent)
	def run(self):
		time.sleep(5)
		start = time.time()
		self.lnk = pxssh.pxssh()
		hostname = '10.212.212.49'
		username = 'fhire'
		password = 'WIROfhire17'
		self.lnk.login(hostname,username,password)
		end = time.time()
		print('Vacuum RPi connected. Time elapsed: '+str('%.2f'%(end-start))+" seconds")
		self.lnk.sendline("cd ~/Desktop/vacuum_controller2")
		self.lnk.sendline("python")
		self.lnk.sendline("import vacuum_control")
		self.lnk.sendline("tic = vacuum_control.TIC()")
		print("Vacuum RPi - connected to vacuum_control.py")

	def sendCommand(self,cmd):
		self.lnk.sendline(cmd)

	'''
	def printing(self):
		print("Printing ls")
		self.lnk.sendline("test.printThis()")

	def continuePrinting(self):
		self.lnk.sendline("test.testThis()")
		self.lnk.prompt()
		output = self.lnk.before.decode('utf-8','ignore')
		print(output)
		#print(type(output))
	'''

	def stop(self):
		self.terminate()

