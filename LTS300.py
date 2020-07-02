import time
import serial
from PyQt4 import QtCore, QtGui

class stage(QtCore.QObject):
    def __init__(self):  
	super(stage,self).__init__()
        self.ser = serial.Serial(port = '/dev/ttyUSB0',
                                 baudrate=115200,
                                 bytesize=serial.EIGHTBITS,
                                 parity=serial.PARITY_NONE,
                                 stopbits=serial.STOPBITS_ONE,
                                 rtscts=True)
      
        #Thorlabs recommends toggling the RTS pin
        #and reseting the input and output buffers
        #Is actually doing anything? Don't know...
             
        self.ser.setRTS(1)
        time.sleep(0.05)
        self.ser.flushInput()
        self.ser.flushOutput()
        time.sleep(0.05)
        self.ser.setRTS(0)
        
        
        #preset hex commands - see Thorlabs APT Communications Protocol
        self.disable_motor = '\x10\x02\x01\x02\x21\x01'
        self.enable_motor = '\x10\x02\x01\x02\x21\x01'
        self.home_motor = '\x43\x04\x01\x00\x21\x01'
        self.ser.write(self.home_motor)
        
        #last 4 bytes are the absolute position of the stage
        #in hex signed two's complement 
        
        self.move_m_dist = '\x53\x04\x06\x00\x80\x01\x01\x00\x00\xC0\xF3\x00'
        self.move_s_dist = '\x53\x04\x06\x00\x80\x01\x01\x00\x00\x40\xDB\x02'        
        
        #stops updates every 100 ms
        self.stop_updates = '\x12\x00\x00\x00\x21\x01'
        self.ser.write(self.stop_updates)
        
        #trying to add limit switch at 100 mm but does not work
        #self.new_limits = '\x23\x04\x10\x00\x80\x01\x01\x00\x02\x00\x02\x00\xE8\xCC\xCC\x00\x00\x00\x00\x00\x03\x00'
        #self.ser.write(self.new_limits)
        
        #sets max velocity to 20 mm/s and max accel to 5 mm/s
        self.set_vel = '\x13\x04\x0E\x00\x80\x01\x01\x00\x00\x00\x00\x00\x02\x58\x00\x00\x00\x00\x36\x1A'
        self.ser.write(self.set_vel)
        
        #sets home velocity to 5 mm/s
        self.home_vel = '\x40\x04\x0E\x00\x80\x01\x01\x00\x00\x00\x00\x00\x00\x80\x8D\x06\x00\x00\x00\x00'
        self.ser.write(self.home_vel)
       
        
    def close(self):
        self.ser.write(self.home_motor)
        self.ser.close()
        
        
    def reset(self):
        self.ser.write(self.disable_motor)
        time.sleep(1)
        self.ser.write(self.enable_motor)
        time.sleep(1)
        self.ser.write(self.home_motor)
        
        
    def enable(self):
        self.ser.write(self.enable_motor)        
        
        
    def disable(self):
        self.ser.write(self.disable_motor)
        
        
    def home(self):
	print("Sending home")
        self.ser.write(self.home_motor)     
        
        
    def move_mirror(self):
	print("Sending Mirror")
        self.ser.write(self.move_m_dist)
        
        
    def move_splitter(self,):
	print("Sending Splitter")
        self.ser.write(self.move_s_dist) 
        
