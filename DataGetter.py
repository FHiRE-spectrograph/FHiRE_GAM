from pexpect import pxssh
import numpy as np
import time

class DataGetter:
    
	def __init__(self):

		#Define hostnames for ssh
		self.username = 'fhire'
		self.password = 'WIROfhire17'
		self.GAM = '10.212.212.20'
		self.VC = '10.212.212.49' #Vacuum Control
		self.TCS = '10.212.212.70' #Temp CMS
		self.Ref = '10.214.214.115' #Refractor

	def Temp(self):
		print('Getting Temp Logs')
		self.lnk = pxssh.pxssh()
		self.lnk.login(self.TCS,self.username,self.password)
		self.lnk.sendline('cd ~/Desktop/FHiRE-TCS/')
		self.lnk.sendline('scp tempLog.dat fhire@10.212.212.20:/home/fhire/Desktop/FHiRE_GAM/logs')
		time.sleep(3)
		i = self.lnk.expect('fhire@10.212.212.20\'s password:')
		if i == 0:
			self.lnk.sendline(self.password)
			time.sleep(3)
		elif i == 1:
			pass
		self.lnk.sendline('scp LPresistorsLog.dat fhire@10.212.212.20:/home/fhire/Desktop/FHiRE_GAM/logs')
		time.sleep(3)
		i = self.lnk.expect('fhire@10.212.212.20\'s password:')
		if i == 0:
			self.lnk.sendline(self.password)
			time.sleep(3)
		elif i == 1:
			pass
		self.lnk.sendline('scp LPdiodesLog.dat fhire@10.212.212.20:/home/fhire/Desktop/FHiRE_GAM/logs')
		time.sleep(3)
		i = self.lnk.expect('fhire@10.212.212.20\'s password:')
		if i == 0:
			self.lnk.sendline(self.password)
			time.sleep(3)
		elif i == 1:
			pass
		self.lnk.sendline('scp controlTemp.dat fhire@10.212.212.20:/home/fhire/Desktop/FHiRE_GAM/logs')
		time.sleep(3)
		i = self.lnk.expect('fhire@10.212.212.20\'s password:')
		if i == 0:
			self.lnk.sendline(self.password)
			time.sleep(3)
		elif i == 1:
			pass
		self.lnk.sendline('scp monitoringTemp.dat fhire@10.212.212.20:/home/fhire/Desktop/FHiRE_GAM/logs')
		time.sleep(3)
		i = self.lnk.expect('fhire@10.212.212.20\'s password:')
		if i == 0:
			self.lnk.sendline(self.password)
			time.sleep(3)
		elif i == 1:
			pass
		self.lnk.logout()
		print('Temp Logs Obtained')

	def Pressure(self):
		print('Getting Pressure Logs')
		self.lnk = pxssh.pxssh()
		self.lnk.login(self.VC,self.username,self.password)
		self.lnk.sendline('cd ~/Desktop/FHiRE-vacuum/pressure_logs')
		self.lnk.prompt()
		self.lnk.sendline('ls -Art | tail -n 1')
		self.lnk.prompt()
		fname = self.lnk.before.splitlines()[1:]
		fname = fname[0]
		self.lnk.sendline('scp %s fhire@10.212.212.20:/home/fhire/Desktop/FHiRE_GAM/logs' %fname)
		time.sleep(3)
		i = self.lnk.expect('fhire@10.212.212.20\'s password:')
		if i == 0:
			self.lnk.sendline(self.password)
			time.sleep(3)
		elif i == 1:
			pass
		self.lnk.logout()
		print('Pressure Logs Obtained')


	#==========TO DO==========#
	# Update the paths and files to the correct location once brightness logging is established
	def Brightness(self):
		print('Getting Brightness Logs')
		self.lnk = pxssh.pxssh()
		self.lnk.login(self.Ref,self.username,self.password)
		self.lnk.sendline('cd ~/Desktop/') #TO DO: Correct Path for where brightness logs will be
		fname = 'Brighness.dat' #TO DO: Correct for actual file name
		self.lnk.sendline('scp %s fhire@10.212.212.20:/home/fhire/Desktop/FHiRE_GAM/logs' %fname)
		time.sleep(3)
		i = self.lnk.expect('fhire@10.212.212.20\'s password:')
		if i == 0:
			self.lnk.sendline(self.password)
			time.sleep(3)

		elif i == 1:
			pass
		self.lnk.logout()
		print('Pressure Logs Obtained')

