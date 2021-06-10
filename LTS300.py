import time, serial, os, sys
from PyQt5 import QtCore
from PyQt5.QtCore import QThread,pyqtSignal

# Class that communicates with LTS300.
class Stage(QtCore.QObject):
	signal_status = pyqtSignal('PyQt_PyObject')

	# Preset hex commands - see Thorlabs APT Communications Protocol.
	disable_motor = b'\x10\x02\x01\x02\x21\x01'
	enable_motor = b'\x10\x02\x01\x01\x21\x01'
	home_motor = b'\x43\x04\x01\x00\x21\x01'
	home_str = '440401000150'

	#
	# Absolute position of the stage in hexadeximal two's complement
	# use conversion.py to determine two's complement if changing positions
	# change mirror and lens positions and strings here
	# mirror position at 102 mm.
	#
	mirror_pos = b'\x00\x80\x7D\x02'
	mirror_str = '00807d02'
	# Beam splitter position at 5 mm.
	splitter_pos = b'\x00\x40\x1F\x00'   
	splitter_str = '00401f00'

	# Move command consists of base move hex plus the move position in 
	# two's complement.
	move = b'\x53\x04\x06\x00\x80\x01\x01\x00'
	move_mirror = move + mirror_pos
	move_splitter = move + splitter_pos

	# Sets max velocity to 10 mm/s and max accel to 5 mm/s.
	setvel = b'\x13\x04\x0E\x00\x80\x01\x01\x00\x00\x00\x00\x00\x02\x58\x00\x00\x00\x00\x1B\x0D'

	# Sets home velocity to 5 mm/s.
	homevel = b'\x40\x04\x0E\x00\x80\x01\x01\x00\x00\x00\x00\x00\x00\x80\x8D\x06\x00\x00\x00\x00' 

	def __init__(self, parent=None):
		super(self.__class__, self).__init__(parent)
		#
		# Make sure not to plug in stage/filter USBs while RPi is ON.
		# The QHY filterwheel (connected through USB on the ZWO camera)
		# defaults to ttyUSB0 at restart. Stage defaults to the next USB
		# designation, ttyUSB1. Plugging in these USBs while the
		# RPi is ON sets its designation to USB0, USB1 in terms of order 
		# plugged in rather than the expected restart default. It looks
		# like it doesn't matter which port the stage, camera, 
		# filterwheel USBs are connected on the GAM RPi.
		#
		self.ser = serial.Serial(
				port = '/dev/ttyUSB1',
				baudrate=115200,
				bytesize=serial.EIGHTBITS,
				parity=serial.PARITY_NONE,
				stopbits=serial.STOPBITS_ONE,
				rtscts=True,
				timeout=1)

		# Thorlabs recommends toggling the RTS pin and resetting the 
		# input and output buffers.
		self.ser.setRTS(1)
		time.sleep(0.05)
		self.ser.flushInput()
		self.ser.flushOutput()
		time.sleep(0.05)
		self.ser.setRTS(0)
 
		# Set motor speeds.
		self.write_msg(self.setvel) 
		self.write_msg(self.homevel)
		# Disable motor and turn off lights.
		self.disable()

		self.stop_thread = False

	def run(self):
		print("Starting thread")
		#self.moveHome()		

	# Disables printing.
	def blockPrint(self):
		sys.stdout = open(os.devnull, 'w')

	# Enables printing.
	def enablePrint(self):
		sys.stdout = sys.__stdout__

	# Sends messages that dont require a response.
	def write_msg(self, message):
		self.blockPrint()
		time.sleep(1)
		self.ser.write(message)
		self.enablePrint()

	# Sends move messages that require a response and waits.
	def move_msg(self, message):
		print("Moving stage.")
		self.signal_status.emit('busy')
		self.blockPrint()
		time.sleep(1)
		self.ser.write(message)
		self.enablePrint()
		while 1:
			msg = self.ser.readline()
			if msg == b'':
				pass
			else:
				hex_msg = msg.hex()
				self.signal_status.emit(hex_msg)
				break
			if self.stop_thread == True:
				print("Stage disconnected while attempting to move.")
				break

	# Command functions.
	def enable(self):
		self.write_msg(self.enable_motor)        

	def disable(self):
		self.write_msg(self.disable_motor)

	def reset(self):
		self.disable()
		time.sleep(1)
		self.enable()
		time.sleep(1)
		self.move_msg(self.home_motor)

	def moveHome(self):
		print("Stage: Moving home")
		self.enable()
		self.move_msg(self.home_motor)
		self.disable()

	def moveMirror(self):
		self.enable()
		self.move_msg(self.move_mirror)
		self.disable()

	def moveSplitter(self):
		self.enable()		
		self.move_msg(self.move_splitter)
		self.disable()

	def stop(self, exit): 
		# Send stage to mirror at closedown to protect lenses. 
		if True:
			self.moveMirror()
		self.stop_thread = True
		self.ser.close()


