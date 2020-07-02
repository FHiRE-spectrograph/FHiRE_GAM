import logging, time, sys
import PyIndi
from PyQt5 import QtGui,QtCore
#inherits from module PyIndi.BaseClient class

#file=open("update.txt","w")
#import fhireGUI2

class IndiClient(PyIndi.BaseClient):
#CLASS IndiClient FUNCTIONS:
	def __init__(self):
		super(IndiClient, self).__init__()
		#self.logger = logging.getLogger('IndiClient')
		#self.logger.info('Creating an instance of IndiClient')
	def newDevice(self, d): #called when new device is detected
		pass
	def newProperty(self,p):
		pass
	def removeProperty(self, p):
		pass
	def newBLOB(self, bp): 
		global blobEvent
		blobEvent.clear()
		blobEvent.set()
		blobEvent.clear()
		pass
	def newSwitch(self, svp):
		pass
	def newNumber(self, nvp): 
		pass
	def newText(self, tvp):
		pass
	def newLight(self, lvp):
		pass
	def newMessage(self, d, m):
        	pass
	def serverConnected(self):	
		pass
	def serverDisconnected(self, code):
		pass


