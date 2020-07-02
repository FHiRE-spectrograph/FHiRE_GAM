# FHiRE GAM software
## Updated: 07/02/2020 

__GUI_pyqt5.py:__ Most up to date version of the GAM user interface. Provides communications with QHY filter wheel, ZWO ASI174MM-Cool guide camera, ThorLabs stage, camera focuser, and ADC focusers. Implements the autoguiding procedure and telescope communication. *Doesn't have ADC focusing included though.* + *Needs to be tested to make sure there're no bugs attributed to PyQt5 upgade.* + *There's a memory leak that needs to be found and fixed.*  
__fhireGUI10.py:__ Provides PyQt5 interface layout and definitions created using QtCreator. Derived from fhireGUI10.ui (needs to be kept in the same directory). Version allows for ADC testing.  

### Devices:
__LTS300.py:__ Driver for ThorLabs stage used to switch between OPEN, the mirror, and beam splitter. *Currently doesn't provide protocol to receive location from stage. (Not absolutely necessary though.)*  
__easydriver.py:__ Driver for the camera focuser.   
__filterclient.py:__ IndiClient loop for device communications with QHY filter wheel and the ZWO guide camera.  

### Autoguiding:
__Centroid_DS9.py:__ Centroiding algorithm for autoguiding. 
__ReadRegions.py:__ Reads dimensions of a user created region in DS9. Used by Centroid_DS9.py as bounds for calculating the centroid (in this case, point of highest intensity) of the region.

## Retired scripts:
__GAM_GUI.py:__ The PyQt4 version of the GAM interface. Last updated 04/26/2019.

## Not included in GitHub:  
__fhireGUI11.py:__ Identical to fhireGUI10.py except that the ADC is setup for use, not testing. Also, it's for PyQt4, not PyQt5.  
__fhireGUI11_pyqt5.py:__ PyQt5 version of fhireGUI11.py.  
__Telinfo:__ Telescope information file copied from Claudius.

## Need to:
[]Make sure PyQt5 version of GUI works.  
[]Fix memory leak of application.  
[]Test the ADC in lab.  
[]Create a better user interface for autoguiding.  
[]Embed DS9 into GUI.  
[]Improve centroiding.  
[]Make sure the camera settings are adjustable. Such as gain and frame size.  
[]Complete the temperature and intensity graphics. Improve fps.  
[]Is there a good closing method in place?  
[]Update documentation.  
[]Add spectrograph communications.  
