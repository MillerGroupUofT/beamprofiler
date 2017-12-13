import glob
import warnings
import os

import numpy as np
import matplotlib.pyplot as plt
import scipy.optimize as opt
import uncertainties as un

from matplotlib.gridspec import GridSpec
from mpl_toolkits.mplot3d import Axes3D

from beamprofileranalysis import *

#Override defaults if necessary (imported from *)
#BITS = 8       #image channel intensity resolution
#SATLIM = 0.001  #fraction of non-zero pixels allowed to be saturated
#PIXSIZE = 1.745E-6  #pixel size in m, measured 1.75um in x and y

cur_dir = False
alt_file_location = '/Users/cpkmanchee/Google Drive/PhD/Data/2017-09-20 Rod seed beam profile/2017-09-20 Unamplied seed'

if cur_dir:
    file_dir = os.getcwd()
else:
    file_dir = alt_file_location

files = glob.glob(file_dir+'/*.jp*g')
files.sort()

# Consistency check, raises error if failure
if not files:
    stop('No files found... try again, but be better')

try:
    z = read_position(file_dir)
    #z = np.loadtxt(file_dir + '/position.txt', skiprows = 2)
    #double pass configuration, covert mm to meters
    #z = 2*z*1E-3
except (AttributeError, FileNotFoundError):
    stop('No position file found --> best be named "position.txt"')

if np.size(files) is not np.size(z):
    stop('# of images does not match positions - fix ASAP')

order = np.argsort(z)
z = np.array(z)[order]
files = np.array(files)[order]

#output parameters
beam_stats = []
chl_sat = []
img_roi = []

for f in files:

    im = plt.imread(f)
    data, sat = flatten_rgb(im, BITS, SATLIM, sgl_chn=False)
    d4stats, roi , _ = calculate_beamwidths(data)

    beam_stats += [d4stats]
    chl_sat += [sat]
    img_roi += [roi]

beam_stats = np.asarray(beam_stats)
chl_sat = np.asarray(chl_sat)
img_roi = np.asarray(img_roi)

#x and y beam widths
d4x = beam_stats[:,0]
d4y = beam_stats[:,1]

#fit to gaussian mode curve
valx, stdx = fit_M2(d4x,z)
valy, stdy = fit_M2(d4y,z)


##
#plotting for pretty pictures

#obtain 'focus image', chooses based on x-direction
focus_number = np.argmin(np.abs(valx[0]-z))

im = plt.imread(files[focus_number])
data, SAT = flatten_rgb(im, BITS, SATLIM)
data = normalize(get_roi(data.astype(float), img_roi[focus_number]))

#put x,y in um, z in mm
x = pix2len(1)*(np.arange(data.shape[1]) - data.shape[1]/2)*1E6
y = pix2len(1)*(np.arange(data.shape[0]) - data.shape[0]/2)*1E6
X,Y = np.meshgrid(x,y)
Z = (z-valx[0])*1E3

#set up plot grid
plot_grid = [3,6]
plot_w = 10
asp_ratio = plot_grid[0]/plot_grid[1]
plot_h = plot_w*asp_ratio


fig = plt.figure(figsize=(plot_w,plot_h), facecolor='w')
gs = GridSpec(plot_grid[0], plot_grid[1])
ax1 = plt.subplot(gs[:2, 0])
# identical to ax1 = plt.subplot(gs.new_subplotspec((0,0), colspan=3))
ax2 = plt.subplot(gs[:2,1:3])
ax3 = plt.subplot(gs[:2, 3:], projection='3d')
ax4 = plt.subplot(gs[2,1:3])
ax5 = plt.subplot(gs[2,3:])
ax6 = plt.subplot(gs[-1,0])

ax6.axis('off')
make_ticklabels_invisible([ax2])

ax2.imshow(data, cmap=plt.cm.plasma, origin='lower', interpolation='bilinear',
    extent=(x.min(), x.max(), y.min(), y.max()))
contours = data.max()*(np.exp(-np.array([2,1.5,1])**2/2))
widths = np.array([0.5,0.25,0.5])
CS = ax2.contour(data, contours, colors = 'k', linewidths = widths, origin='lower', interpolation='bilinear', extent=(x.min(), x.max(), y.min(), y.max()))

ax4.plot(x, normalize(np.sum(data,0)), 'k')
ax4.set_xlabel('x (um)')

ax1.plot(normalize(np.sum(data,1)), y, 'k')
ax1.set_ylabel('y (um)')

ax3.plot_surface(X,Y,data, cmap=plt.cm.plasma)
ax3.set_ylabel('y (um)')
ax3.set_xlabel('x (um)')

ax5.plot(Z,d4x*1E6,'bx',markerfacecolor='none')
ax5.plot(Z,d4y*1E6,'g+',markerfacecolor='none')
ax5.plot(Z,2*gaussianbeamwaist(z,*valx[:3])*1E6,'b', label='X')
ax5.plot(Z,2*gaussianbeamwaist(z,*valy[:3])*1E6,'g', label='Y')
ax5.set_xlabel('z (mm)')
ax5.set_ylabel('Spot size, 2w (um)')
ax5.yaxis.tick_right()
ax5.yaxis.set_label_position('right')
ax5.legend(loc=9)

ax6.text(-0.2,0.2,'M2x = {:.2f}\nM2y = {:.2f}\nwx = {:.0f} um\nwy = {:.0f} um'.format(valx[2],valy[2],(1E6)*valx[1]/2,(1E6)*valy[1]/2))

plt.show()
