from PyQt4 import QtGui, QtCore
import RPi.GPIO as gpio
import sys

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

class window(QtGui.QMainWindow):

	def __init__(self):
		super(window, self).__init__()
		self.setGeometry(50,50,500,500)
		self.setWindowTitle('Shutter Control')
		self.home()

	def home(self):
		self.open_button = QtGui.QPushButton('OPEN',self)
		self.open_button.resize(125,30)
		self.open_button.move(0,0)
		self.open_button.clicked.connect(self.opn)

		self.close_button = QtGui.QPushButton('CLOSE',self)
		self.close_button.resize(125,30)
		self.close_button.move(126,0)
		self.close_button.clicked.connect(self.cls)

		self.show()

	def opn(self):
		shutter.open_shutter()

	def cls(self):
		shutter.close_shutter()

def run():
	app = QtGui.QApplication(sys.argv)
	GUI = window()
	sys.exit(app.exec_())

run()


		
