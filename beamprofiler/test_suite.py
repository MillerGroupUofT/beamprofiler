# -*- coding: utf-8 -*-
"""
Created on Tue Nov 28 18:52:32 2017

@author: cpkmanchee

Tests of beamprofiler analysis
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

from beamprofileranalysis import *

def test_fit(z,val_in,na,wl_in):
    '''run test
    '''
    d_in = 2*gaussianbeamwaist(z,*val_in[:3],wl_in)*(1+(na*(np.random.randn(z.size))))

    #Fit test data
    val, err = fit_M2(d_in,z,wl_in)

    return val,err,d_in

#Define input test points
z0_in = 0
d0_in = 50.0E-6
M2_in = 2.0
wl_in = 1.03E-6
zR_in = np.pi*(d0_in/2)**2/(wl_in*M2_in)
theta_in = 2*M2_in*wl_in/(np.pi*d0_in/2)
val_in = [z0_in, d0_in, M2_in, theta_in, zR_in]

N = 1000

num_pts=10
na = 0.05
nd = np.floor(num_pts/4)

#create symmetric spacial array within ISO spec.
z = np.concatenate((np.linspace(-4*zR_in,-2*zR_in,nd), np.linspace(-zR_in,zR_in,2*nd), np.linspace(2*zR_in,4*zR_in,nd)))

print(np.size(val_in))
#Perform test
v_sum=np.zeros(np.size(val_in))
v2_sum=np.zeros(np.size(val_in))
s_sum=np.zeros(np.size(val_in))
s2_sum=np.zeros(np.size(val_in))

for i in range(N):
    v,s,_ = test_fit(z,val_in,na,wl_in)

    v_sum = v_sum + np.array(v)
    v2_sum = v2_sum + np.array(v)**2
    s_sum = s_sum + np.array(s)
    s2_sum = s2_sum + np.array(s)**2

val_avg = v_sum/N
val_std = ((1/(N-1))*(v2_sum - v_sum**2/N))**(1/2)

std_avg = s_sum/N
std_std = ((1/(N-1))*(s2_sum - s_sum**2/N))**(1/2)

#Plot results
f1,ax2 = plt.subplots(1,1)
rows = ['z0', 'd0', 'M2', 'theta', 'zR']
cols = ['Actual', 'Fit', 'MCsig', 'Fit Sigma','MCsig']

ax2.axis('tight')
ax2.axis('off')
ax2.table(cellText=np.transpose([val_in,val_avg,val_std,std_avg,std_std]), rowLabels = rows, colLabels = cols, loc='center')
plt.show()
#Create table to compare values

#ax1.plot(z,d_in,'bx')
#ax1.plot(z,2*gaussianbeamwaist(z,*val[:3], wl_in))
## Test image processing
