# FHiRE GAM software
## Updated: 10/05/2020 

__GUI_pyqt5.py:__ Most up to date version of the GAM user interface. Provides communications with QHY filter wheel, ZWO ASI174MM-Cool guide camera, ThorLabs stage, camera focuser, and ADC focusers. Implements the autoguiding procedure and telescope communication. *Doesn't have ADC focusing included though.* + *Transitioning to using multiple scripts. So only really includes code required by the mainwindow widgets.*  

### Devices:
__LTS300.py:__ Driver for ThorLabs stage used to switch between OPEN, the mirror, and beam splitter. *Currently doesn't provide protocol to receive location from stage. (Not absolutely necessary though.)*  
__easydriver.py:__ Driver for the camera focuser.   
__filterclient.py:__ IndiClient loop for device communications with QHY filter wheel and the ZWO guide camera.  

### Autoguiding:
__Centroid_DS9.py:__ Centroiding algorithm for autoguiding.   
__ReadRegions.py:__ Reads dimensions of a user created region in DS9. Used by Centroid_DS9.py as bounds for calculating the centroid (in this case, point of highest intensity) of the region.  

## Retired scripts:
__GAM_GUI.py:__ The PyQt4 version of the GAM interface. Last updated 04/26/2019.  
__fhireGUI10.py:__ Provides PyQt5 interface layout and definitions created using QtCreator. Derived from fhireGUI10.ui (needs to be kept in the same directory). Version allows for ADC testing.  

## Not included in GitHub:  
__fhireGUI11.py:__ New layout for GAM GUI. Includes options to open new windows for monitoring, testing and settings. Doesn't include empty space for ds9. PyQt5.   
__Telinfo:__ Telescope information file copied from Claudius.  

## Need to:
[x]Make sure PyQt5 version of GUI works.  
[x]Fix memory leak of application.  
[]Test the ADC in lab.  
[x]Create a better user interface for autoguiding.  
[!x]Embed DS9 into GUI.  
[]Improve centroiding.  
[]Make sure the camera settings are adjustable. Such as gain and frame size.  
[]Complete the temperature and intensity graphics. Improve fps.  
[]Update documentation.  
[]Add spectrograph communications.  
[]Fix long startup time.  
[]Setup windows for vacuum control, ZWO settings, ADC testing.  
[]Add functionalities for vacuum control.  
[]Add functionalities for ZWO settings.  
[]Add functionalities for ADC testing.  
[]Shutdown indiserver at closing.  
[]Add error catches.  
[]Add progress bar for total images?  
[]Have progress bar update for refractor images?  
[]Add logging option?  

