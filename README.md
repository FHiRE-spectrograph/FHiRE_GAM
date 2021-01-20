# FHiRE GAM software
## Updated: 01/19/2021 

__GUI_pyqt5.py:__ Most up to date version of the GAM user interface. Provides communications with QHY filter wheel, ZWO ASI174MM-Cool guide camera, ThorLabs stage, camera focuser, the ADC, and CMOS camera for the refractor. Implements the autoguiding procedure and telescope communication. Mainly includes code required by the mainwindow widgets. Inherits code for seperate windows.  
__ZWOguiding_camera.py:__ Includes options to toggle cooling, set binning, gain, bandwidth, offset, frame settings, and select exposure type (light, dark, etc.) and bits. Inherited by GUI_pyqt5.py  
__VacuumControl.py:__ Currently empty. Need to integrate Jason's vacuum control code.  
__ADCtesting.py:__ Includes all ADC methods - initiating x2 stepper motors and x2 microswitches, home method for absolute positioning, and methods for calculating and updating ADC positions. *Currently doesn't allow for the user to move the ADC specific number of steps.* *ADC calculations need to be tested during observation runs.* *Need to rewrite thread for accessing Claudius to retrieve Telinfo.*   

### Devices:
__LTS300.py:__ Driver for ThorLabs stage used to switch between OPEN, the mirror, and beam splitter. *Currently doesn't provide protocol to receive location from stage. (Relevant location code developed by Jason and needs to be integrated)*  
__easydriver.py:__ Driver for the camera focuser and ADC stepper motors.   
__client.py:__ IndiClient loop for device communications with QHY filter wheel and the ZWO guide camera. Now also includes the variable and method definitions for the filter wheel and guide camera within ThreadClass. Methods include changing filter slot, taking an exposure, and changing camera settings.(previously named filterclient.py)  
__shuttuh.py:__ Toggles ThorLabs shutter which will be installed at the optical fiber. Not implemented within the GAM GUI yet.  

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
### External files:
__Telinfo:__ Telescope information file copied from Claudius.  

## Need to:
[x]Make sure PyQt5 version of GUI works.  
[x]Fix memory leak of application.  
[x]Test the ADC in lab.  
[x]Create a better user interface for autoguiding.  
[!x]Embed DS9 into GUI.  
[]Improve centroiding.  
[]Make sure the camera settings are adjustable. Such as gain and frame size.  
[]Complete the temperature and intensity graphics. Improve fps.  
[]Update documentation.  
[]Add spectrograph communications.  
[x]Fix long startup time.  
[x]Setup windows for vacuum control, ZWO settings, ADC testing.  
[x]Add functionalities for ZWO settings.  
[x]Add functionalities for ADC testing.  
[]Shutdown indiserver at closing.  
[]Add error catches.  
[]Add progress bar for total images?  
[]Have progress bar update for refractor images?  
[]Add logging option?  
[]Add thread to continuously communicate with Claudius to update Telinfo.  
[]Integrate vacuum control code.  
[]Integrate new stage code for receiving location from stage.  

