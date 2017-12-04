# -*- coding: utf-8 -*-
"""
Created on Wed Aug  3 11:31:57 2016

@author: cpkmanchee

Notes on beamwaist:

I ~ exp(-2*r**2/w0**2)
w0 is 1/e^2 waist radius
w0 = 2*sigma (sigma normal definition in gaussian)
"""
import glob
import warnings
import os

import numpy as np
import matplotlib.pyplot as plt
import scipy.optimize as opt
import uncertainties as un

from matplotlib.gridspec import GridSpec
from mpl_toolkits.mplot3d import Axes3D

__all__ = ['stop', 'pix2len', 'make_ticklabels_invisible', 'read_position', 'normalize', 'gaussianbeamwaist', 'fit_M2', 'flatten_rgb', 'calculate_beamwidths', 'calculate_2D_moments', 'get_roi', 'BITS', 'SATLIM', 'PIXSIZE']


BITS = 8       #image channel intensity resolution
SATLIM = 0.001  #fraction of non-zero pixels allowed to be saturated
PIXSIZE = 1.745E-6  #pixel size in m, measured 1.75um in x and y


def stop(s = 'error'): raise Exception(s)


def pix2len(input):
    '''Convert pixels to length.
    '''
    if np.isscalar(input):
        output = input*PIXSIZE
    else:
        output =  [x*PIXSIZE for x in input]

    return output


def make_ticklabels_invisible(axes):
    for ax in axes:
        for tl in ax.get_xticklabels() + ax.get_yticklabels():
            tl.set_visible(False)


def read_position(file_dir):
    '''Parse position file.
    '''
    unit_line = 2
    pos_file = file_dir + '/position.txt'
    z = np.loadtxt(pos_file, skiprows = unit_line)
    with open(pos_file) as f:
        header = f.readlines()[:unit_line]

    unit = header[unit_line-1].split('=')[1].strip().lower()

    if unit=='m':
        s = 1
    elif unit=='mm':
        s=1E-3
    elif unit=='um':
        s=1E-6
    elif unit=='nm':
        s=1E-9
    elif unit=='pm':
        s=1E-12
    else:
        #default to mm
        s=1E-3

    z = 2*s*z

    return z


def normalize(data, offset=0):
    '''
    normalize a dataset
    data is array or matrix to be normalized
    offset = (optional) constant offset
    '''
    shift = data-data.min()
    scale = data.max()-data.min()

    if scale == 0:
        warnings.warn('Divide-by-zero in Normalization. Scaled to 1.')
        return np.ones(data.shape) + offset
    else:
        return shift/scale + offset


def gaussianbeamwaist(z, z0, d0, M2=1, wl=1.030E-6, const=0):
    '''
    generate gaussian beam profile w(z)

    w(z) = w0*(1+((z-z0)/zR)^2)^(1/2)

    where zR is the Rayleigh length given by

    zR = pi*w0^2/wl

    Units for waist and wavelength is um.
    Units for optical axis positon is mm.

    Inputs:

        z = array of position along optical axis in mm
        z0 = position of beam waist (focus) in mm
        d0 = beam waist in um (diameter)
        M2 = beam parameter M^2, unitless
        wl =  wavelenth in um, default to 1030nm (1.03um)

    Outputs:

        w = w(z) position dependent beam waist in um. Same size as 'z'
    '''
    z = np.asarray(z).astype(float)
    z0 = z0
    w0 = d0/2

    w = (w0**2 + M2**2*(wl/(np.pi*w0))**2*(z-z0)**2)**(1/2) + const

    return w


def fit_M2(dz, z, wl=1.03E-6):
    '''
    Everything is SI units.
    Inputs:
        z = optical axis position array, m
        dz = calculated beamwidth data, m

    Outputs:
        z0 = focal point along optical axis, m
        d0 = beamwaist at focus, m
        M2 = M2 beam parameter, unitless
        theta = divergence, rad
        zR = Rayleigh paramter, m

    All outputs include associated uncertainties.
    '''
    di = np.min(dz)
    zi = z[np.argmin(dz)]
    dm = np.max(dz)
    zm = z[np.argmax(dz)]

    ci = (np.arctan((dm-di)/(zm-zi)))**2
    bi = -2*zi*ci
    ai = di**2 + ci*zi**2

    c_lim = np.array([0, np.inf])
    b_lim = np.array([-np.inf,np.inf])
    a_lim = np.array([0, np.inf])

    p0 = [ai, bi, ci]
    limits = ([i.min() for i in [a_lim,b_lim,c_lim]],  [i.max() for i in [a_lim,b_lim,c_lim]])

    f = lambda z,a,b,c: (a + b*z + c*z**2)**(1/2)

    popt,pcov = opt.curve_fit(f,z,dz,p0,bounds=limits)

    #create correlated uncertainty values
    (a,b,c) = un.correlated_values(popt,pcov)

    z0 = (-b/(2*c))
    d0 = ((4*a*c-b**2)**(1/2))*(1/(2*c**(1/2)))
    M2 = (np.pi/(8*wl))*((4*a*c-b**2)**(1/2))
    theta = c**(1/2)
    zR = ((4*a*c-b**2)**(1/2))*(1/(2*c))

    value = [x.nominal_value for x in [z0,d0,M2,theta,zR]]
    std = [x.std_dev for x in [z0,d0,M2,theta,zR]]

    return value, std


def flatten_rgb(im, bits=8, satlim=0.001):
    '''
    Flattens rbg array, excluding saturated channels
    '''

    sat_det = np.zeros(im.shape[2])

    Nnnz = np.zeros(im.shape[2])
    Nsat = np.zeros(im.shape[2])
    data = np.zeros(im[...,0].shape, dtype = 'uint32')

    for i in range(im.shape[2]):

        Nnnz[i] = (im[:,:,i] != 0).sum()
        Nsat[i] = (im[:,:,i] >= 2**bits-1).sum()

        if Nsat[i]/Nnnz[i] <= satlim:
            data += im[:,:,i]
        else:
            sat_det[i] = 1

    output = normalize(data.astype(float))

    return output, sat_det


def calculate_beamwidths(data):
    '''
    data = image matrix
    '''
    error_limit = 0.0001
    it_limit = 5

    errx = 1
    erry = 1
    itN = 0

    d0x = data.shape[1]
    d0y = data.shape[0]

    roi_new = [d0x/2,d0x,d0y/2,d0y]
    full_data = data

    while any([i>error_limit for i in [errx,erry]]):

        roi = roi_new
        data = get_roi(full_data,roi)
        moments = calculate_2D_moments(data)

        dx = 4*np.sqrt(moments[2])
        dy = 4*np.sqrt(moments[3])

        errx = np.abs(dx-d0x)/d0x
        erry = np.abs(dy-d0y)/d0y

        d0x = dx
        d0y = dy

        roi_new = [moments[0]+roi[0]-roi[1]/2,3*dx,moments[1]+roi[2]-roi[3]/2,3*dy]     #[centrex,width,centrey,height]

        itN += 1
        if itN >= it_limit:
            print('exceeded iteration in calculating moments')
            break

    #create scaling array for pixels to meters
    #2nd moments must be scaled by square (units m**2)
    pixel_scale = [pix2len(1)]*2 + [pix2len(1)**2]*3

    moments = pixel_scale*moments
    [ax,ay,s2x,s2y,s2xy] = moments


    g = np.sign(s2x-s2y)
    dx = 2*np.sqrt(2)*((s2x+s2y) + g*((s2x-s2y)**2 + 4*s2xy**2)**(1/2))**(1/2)
    dy = 2*np.sqrt(2)*((s2x+s2y) - g*((s2x-s2y)**2 + 4*s2xy**2)**(1/2))**(1/2)

    if s2x == s2y:
        phi = (np.pi/4)*np.sign(s2xy)
    else:
        phi = (1/2)*np.arctan(2*s2xy/(s2x-s2y))

    beamwidths = [dx,dy,phi]

    return beamwidths,roi,moments


def calculate_2D_moments(data, axes_scale=[1,1], calc_2nd_moments = True):
    '''
    data = 2D data
    axes_scale = (optional) scaling factor for x and y

    returns first and second moments

    first moments are averages in each direction
    second moments are variences in x, y and diagonal
    '''
    x = axes_scale[0]*(np.arange(data.shape[1]))
    y = axes_scale[1]*(np.arange(data.shape[0]))
    dx,dy = np.meshgrid(np.gradient(x),np.gradient(y))
    x,y = np.meshgrid(x,y)

    A = np.sum(data*dx*dy)

    #first moments (averages)
    avgx = np.sum(data*x*dx*dy)/A
    avgy = np.sum(data*y*dx*dy)/A

    #calculate second moments if required
    if calc_2nd_moments:
        #second moments (~varience)
        sig2x = np.sum(data*(x-avgx)**2*dx*dy)/A
        sig2y = np.sum(data*(y-avgy)**2*dx*dy)/A
        sig2xy = np.sum(data*(x-avgx)*(y-avgy)*dx*dy)/A

        return np.array([avgx,avgy,sig2x,sig2y,sig2xy])

    else:
        return np.array([avgx, avgy])


def get_roi(data,roi):
    '''
    data = 2D data
    roi = [x0,width,y0,height]
    '''

    left = roi[0] - roi[1]/2
    bottom = roi[2] - roi[3]/2
    width = roi[1]
    height = roi[3]

    left = min(left,data.shape[1]-2)
    if left <= 0:
        width += left
        left = 0
    elif np.isnan(left):
        left=0
    else:
        left = np.int(left)

    bottom = min(bottom,data.shape[0]-2)
    if bottom <= 0:
        height += bottom
        bottom = 0
    elif np.isnan(bottom):
        bottom = 0
    else:
        bottom = np.int(bottom)

    if left+width > data.shape[1]:
        width = np.int(data.shape[1] - left)
    elif np.isnan(width):
        width = data.shape[1]
    else:
        width = np.int(width)

    if bottom+height > data.shape[0]:
        height = np.int(data.shape[0] - bottom)
    elif np.isnan(height):
        height = data.shape[0]
    else:
        height = np.int(height)

    return data[bottom:bottom+height,left:left+width]
