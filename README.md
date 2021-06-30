# FHiRE GAM software
## Updated: 06/30/2021 

__GUI_pyqt5.py:__ Most up to date version of the GAM user interface. Provides communications with QHY filter wheel, ZWO ASI174MM-Cool guide camera, ThorLabs stage, camera focuser, the ADC, and CMOS camera for the refractor. Implements the autoguiding procedure and telescope communication. Mainly includes code required by the mainwindow widgets. Inherits code for seperate windows.  
__ZWOguiding_camera.py:__ Includes options to toggle cooling, set binning, gain, bandwidth, offset, frame settings, and select exposure type (light, dark, etc.) and bits. Inherited by GUI_pyqt5.py  
__VacuumControl.py:__ Currently empty. Need to integrate Jason's vacuum control code.  
__ADCtesting.py:__ Includes all ADC methods - initiating x2 stepper motors and x2 microswitches, home method for absolute positioning, and methods for calculating and updating ADC positions. *ADC calculations need to be tested during observation runs.* *Need to rewrite thread for accessing Claudius to retrieve Telinfo.*   
__CloudMonitor.py:__ Communicates with the refractor telescope to monitor for potential cloud interference with the observations.  
__DataGetter.py:__ Class that communicates with the other RPi's using pxssh to retrieve the log files for temperature, pressure, and eventually, brightness.   

### Devices:
__LTS300.py:__ Driver for ThorLabs stage used to switch between OPEN, the mirror, and beam splitter. *Currently doesn't provide protocol to receive location from stage. (Relevant location code developed by Jason and needs to be integrated)*  
__easydriver.py:__ Driver for the camera focuser and ADC stepper motors.   
__client.py:__ IndiClient loop for device communications with QHY filter wheel and the ZWO guide camera. Now also includes the variable and method definitions for the filter wheel and guide camera within ThreadClass. Methods include changing filter slot, taking an exposure, and changing camera settings.(previously named filterclient.py)  
__shuttuh.py:__ Toggles ThorLabs shutter which will be installed at the optical fiber. Not implemented within the GAM GUI yet.  
__GAMconnections.dat:__ Set whether ZWO camera, filter wheel, stage, or ADC are connected at start up of the GAM GUI. Helpful for running the GUI when a device isn't connected to avoid errors.  
__GAMinfo.dat:__ Stores information such as filter names, ZWO preset settings and current focuser position to be loaded by the GAM GUI.  

### Autoguiding:
__Centroid_DS9.py:__ Centroiding algorithm for autoguiding.   
__ReadRegions.py:__ Reads dimensions of a user created region in DS9. Used by Centroid_DS9.py as bounds for calculating the centroid (in this case, point of highest intensity) of the region.  

## Retired scripts:
__GAM_GUI.py:__ The PyQt4 version of the GAM interface. Last updated 04/26/2019.  
__fhireGUI10.py:__ Provides PyQt5 interface layout and definitions created using QtCreator. Derived from fhireGUI10.ui (needs to be kept in the same directory). Version allows for ADC testing.  
__filterclient.py:__ Setup IndiClient loop for device communications with QHY filter wheel and the ZWO guide camera.  

## Not included in GitHub:  
### Qt Designer layouts:
__fhireGUI11.py:__ New layout for GAM GUI. Includes options to open new windows for monitoring, testing and settings. Doesn't include empty space for ds9. PyQt5.   
__zwocamerawindow.py:__  Layout for ZWO camera settings window. Inherited by ZWOguiding_camera.py.  
__vacuumwindow.py:__ Layout for vacuum control window. Inherited by VacuumControl.py.  
__adcwindow.py:__ Layout for the ADC window. Inherited by ADCtesting.py.  
__devicewindow.py:__ Layout for the device connection window.  
### External files:
__Telinfo:__ Telescope information file copied from Claudius.  

## Need to:
Guiding camera:  
[]Add co-add option for a sequence of exposures.  
[]Disable guiding camera while autoguiding.  
[]Add dialog box asking if you're sure you want to expose with the guiding camera if autoguiding.  
[]Update 'total number of exposures' progress bar.  
[]Add option to browse for image file path.  
[]Add option to save the current ZWO settings to a preset (except for the first one), like saving radio stations.  

Refractor camera:  
[]Add manual save option for the refractor camera.  

Focuser:  
[]Store current position of the focuser to simulate an absolute home/reference.  
[]Track temperatures inside the dome. (Using refractor RPi?)  
[]Show dome temperatures on the main page with a combobox to select different sensors.  
[]Print recommendations for the focuser based on the trend of dome temperatures.  

Guiding:  
[]Add a thread to continuously communicate with Claudius to update Telinfo.  
[]Improve centroiding by adding the refractor camera.  
[]Add functionality update the nominal location of the fiber.  
[]Add a protocol to spiral search about a bright target to line up the optical fiber on the brightest spectra.  

ADC:  
[]Show nominal ADC values.  

Communicating with other RPis:  
[]Add a window to track the sensors in the temperature control and monitoring system. (pulls from a .dat file on the TCMS RPi.)  
[]Add combobox (or list widget?) to select TCMS sensors and option to graph.  
[]Track the vacuum pressure in a similar way to the TCMS and cloud coverage. (scp a .dat file)  
[]Add widgets to start up vnc to the other RPis.  

Etc:  
[]Add enable/disable option for ZWO camera, filter wheel and ADC.  
[]Add a shutdown button to make shutting down the GUI more responsive.  
[]Add spectrograph communications.  


