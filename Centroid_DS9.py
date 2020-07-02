
import numpy as np
import os
from astropy.io import fits as pyfits
from os import path
from ReadRegions import read_region
import re
__version__ = '0.2.0'
__author__ = 'Mihai Cara and Lia Eggleston'
__vdate__ = '10-jul-2018'


def imexcentroid(image, xyin=None):

    """
    Provided with an input image, the code will output centroid of the source within the guidebox
    provided by an open window of DS9, computed using the original IRAF's centroid algorithm. 
    Subtracts the average sky value taken from the first 10 rows of pixels in the image.

    Parameters
    ----------
        image : str, numpy.ndarray
            Either a string file name of an image file or a numpy.ndarrray
            containing image data
	xyin : either str or list
	    Regions file name or a list of guidebox dimensions 

    Returns
    -------
        centroid_xy : list
            A list of centroid coordinates, integer rounded to the pixel


    Examples
    --------
    >>> from Centroid2 import imexcentroid
    >>> imexcentroid('GAMimage162.fit')
    [1653, 372]

    """

    # get image data:
    if isinstance(image, str):
	hdulist = pyfits.open(image)
	scidata = hdulist[0].data
        image = scidata
    elif not isinstance(image, np.ndarray):
        raise TypeError("Unsupported type for the 'image' parameter")

    # make sure we are dealing with 2D images:
    if len(image.shape) != 2:
        raise ValueError("Input image must 2-dimensional")

    # get region data for the guidebox;
    if isinstance(xyin, str):
	xyin = read_region(xyin)
	if xyin == None:
		raise ValueError('Error: No guidebox detected in DS9 or regions file not properly saved')
    elif not isinstance(xyin, list):
	raise TypeError("Unsupported type for the 'xyin' or guidebox dimensions parameter")

    # make sure width and height of guidebox > 0:
    if xyin[2] <= 0.0 or xyin[3] <= 0.0:
        raise ValueError("Width/height must be a strictly positive number")

    # set xyin values to default if none given (will also be None if no guidebox is found in Ds9)
    if xyin==None:
	# set to default values: use whole image
	xyin = [image.shape[1]/2, image.shape[0]/2, image.shape[1], image.shape[0]]

    ################################################
    ##  Main algorithm for computing centroid     ##
    ##  within the guidebox coordinates:          ##
    ################################################

    centroid_xy = []
    ymax = image.shape[0] - 1
    xmax = image.shape[1] - 1
    niter = range(3)

    [xi, yi, w, h] = xyin
    xc0 = xi
    yc0 = yi
    xradius = w/2
    yradius = h/2
   
    # find the bounding box for extraction
    x1 = int(xc0 - xradius + 0.5)
    x2 = int(xc0 + xradius + 0.5)
    y1 = int(yc0 - yradius + 0.5)
    y2 = int(yc0 + yradius + 0.5)

    (x1, x2, y1, y2) = _inbounds_box(x1-1, x2-1, y1-1, y2-1, xmax, ymax)
    box = image[y1:y2,x1:x2]

    # create lists of coordinates
    xs = np.arange(x1+1,x2+1)
    ys = np.arange(y1+1,y2+1)

    # take the avg flux of the first 10 rows as sky value and subtract from guidebox
    rows = image[(ymax-9):ymax+1, 0:xmax+1]
    avgsky = np.mean(rows)
    for i in range(0, y2-y1):
	for j in range(0,x2-x1):
		if box[i,j] <= avgsky:
			box[i,j] = 0
		else:
			box[i,j] = box[i,j]-avgsky

    # compute marginal distribution for x-axis
    margx = box.sum(axis=0, dtype=np.float64)
    meanx = margx.mean()
    margx -= meanx
    goodx = margx > 0.0 # no data
    if not goodx.any():
          xc = np.nan
          yc = np.nan
          return None

    # compute marginal distribution for y-axis
    margy = box.sum(axis=1, dtype=np.float64)
    meany = margy.mean()
    margy -= meany
    goody = margy > 0.0
    if not goody.any(): # no data
          xc = np.nan
          yc = np.nan
          return None

    # compute centroid
    margx_good = margx[goodx]
    margy_good = margy[goody]
    xc = np.dot(xs[goodx], margx_good) / margx_good.sum()
    yc = np.dot(ys[goody], margy_good) / margy_good.sum()

    centroid_xy = [int(xc), int(yc)]

    return centroid_xy


def _inbounds_box(x1, x2, y1, y2, xmax, ymax):
    # xmax, ymax - upper bound for indeces (should be image size along a
    #              dimension - 1)
    # x1, x2, y1, y2 - bounds of an image slice
    # Assumtions: x1 < x2, y1 < y2, xmax >= 0, ymax >= 0
    if x2 < 0 or x1 > xmax or y2 < 0 or y1 > ymax:
	raise ValueError('Guidebox in Ds9 is outside the dimensions of the image')
        return (0, 0, 0, 0)
    if x1 < 0:
        x1 = 0
    if x2 > xmax:
        x2 = xmax
    if y1 < 0:
        y1 = 0
    if y2 > ymax:
        y2=ymax
    return (x1, x2+1, y1, y2+1)

#print imexcentroid('GAMimage162.fit', [1645, 604, 444, 1143])

#print imexcentroid('/d/users/lia/Desktop/Summer2018/20180702/GAMimage67.fit', '/d/users/lia/Desktop/Summer2018/regions.reg')












