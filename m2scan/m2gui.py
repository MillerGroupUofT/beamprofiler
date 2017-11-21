# -*- coding: utf-8 -*-
"""
Created on Fri Jun  6 16:50:02 2014

@author: cpkmanchee
"""

import os
import numpy as np
import queue as qu
import cv2

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

#from matplotlib import pyplot as plt

import threading
import time
import datetime
import tkinter as tk

from tkinter.filedialog import asksaveasfilename
from PIL import Image, ImageTk



PIXEL_SIZE = 1.74   #pixel size in um

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
    if A==0:
        if calc_2nd_moments:
            return np.zeros(5)
        else:
            return np.zeros(2)
    
    #first moments (averages)
    avgx = np.sum(data*x*dx*dy)/A
    avgy = np.sum(data*y*dx*dy)/A

    if calc_2nd_moments:
        #second moments (~varience)
        sig2x = np.sum(data*(x-avgx)**2*dx*dy)/A
        sig2y = np.sum(data*(y-avgy)**2*dx*dy)/A
        sig2xy = np.sum(data*(x-avgx)*(y-avgy)*dx*dy)/A
        
        return [avgx,avgy,sig2x,sig2y,sig2xy]

    else:
        return [avgx, avgy]




class Application(tk.Tk):
    """ GUI app to aid in the collection of beam profile data"""
    
    def __init__(self, master=None):
        """Initialize frame"""
        self.root = tk.Tk.__init__(self,master)
        
        self.geometry('500x400')
        self.protocol("WM_DELETE_WINDOW", self.onClose)
        
        self.grid()
        self.createWidgets()
        self.lift()
        
    def createWidgets(self):
        """Create button, text, entry widgets"""
        
        self.camSelectLabel = tk.Label(self, text = 'Select camera:')
        self.camSelectLabel.grid(row = 0, column = 0, columnspan = 1, sticky = 'W')
        
        self.default_camera = '-Select-'
        self.cameraName = tk.StringVar()
        self.cameraName.set(self.default_camera)
        camera_list = self.getCameras()
        
        self.camSelect = tk.OptionMenu(self, self.cameraName, *camera_list)
        self.camSelect.config(width=8)
        self.camSelect.grid(row = 0, column = 1, columnspan = 1, sticky = 'EW')        
        
        self.imgAvLabel = tk.Label(self, text = 'Image to average: ')
        self.imgAvLabel.grid(row=0, column=2, sticky = 'W')
        
        self.imgAvNum = tk.StringVar()
        self.imgAvNum.set('10')        
        
        self.imgAvEntry = tk.Entry(self, textvariable = self.imgAvNum, width=10)
        self.imgAvEntry.grid(row=0, column=3, columnspan=1, sticky = 'W')
        
        self.saveLabel = tk.Label(self, text = 'Save location:')
        self.saveLabel.grid(row = 1, column = 0, columnspan = 1, sticky = 'W')
        
        self.saveDir = tk.StringVar()
        #home = os.path.expanduser("~")
        #self.saveDir.set(os.path.join(home, 'default_image'))
        self.saveDir.set(os.path.join('default_image','default_image'))
        
        self.saveDirBox = tk.Entry(self, textvariable = self.saveDir)
        self.saveDirBox.grid(row=1, column=1, columnspan = 2, sticky='W')
        
        self.browseButton = tk.Button(self, text = 'Browse', command = lambda: self.browseDir(self.saveDir))
        self.browseButton.grid(row=1, column=3, columnspan=1, sticky='W')
                
        self.capture = tk.Button(self, text='Capture', command = self.onCapture)
        self.capture.grid(row=2,column=0, sticky='W')
        
        self.startPreviewButton = tk.Button(self, text='Start Preview', command = lambda: self.startPreview(self.previewPanel))
        self.startPreviewButton.grid(row=2,column=1, sticky='W')

        self.stopPreviewButton = tk.Button(self, text='Stop Preview', command = lambda: self.stopPreview(self.previewPanel))
        self.stopPreviewButton.grid(row=2,column=2, sticky='W')

        self.openBeamPointingButton = tk.Button(self, text='Beam Pointing', command = self.openBeamPointingWindow)
        self.openBeamPointingButton.grid(row=2, column=3, sticky='W')
        self.bpw = None

        #the next bit is for sensor saturation detection... not implemented yet
        self.resolutionText = tk.Label(self, text = 'Sensor resolution:')
        self.resolutionText.grid(row=3, column=0, columnspan=1, sticky='W')

        self.sensorRes = tk.DoubleVar()
        self.sensorRes.set(8)
        sensorList = np.array([8,10,12,14,16])
        self.resolutionMenu = tk.OptionMenu(self, self.sensorRes,*sensorList)
        self.resolutionMenu.grid(row=3, column=1, sticky='W')
        
        self.rSat = tk.Label(self, text='R', relief='raised', width = 5)
        self.rSat.grid(row=3, column=2, columnspan=2, sticky='W')
        self.gSat = tk.Label(self, text='G', relief='raised', width = 5)
        self.gSat.grid(row=3, column=2, columnspan=2)
        self.bSat = tk.Label(self, text='B', relief='raised', width = 5)
        self.bSat.grid(row=3, column=2, columnspan=2, sticky='E')
        
        self.bgColor = self.rSat.cget('bg')
        
        #end of sensor saturation detection

        self.imgQueue = qu.Queue(maxsize=100)        
        
        img = None
        self.previewPanel = tk.Label(self, image = img)
        self.previewPanel.image = img
        self.previewPanel.grid(row=4, column=0, columnspan=4, sticky = 'W')
        
        self.statusText = tk.StringVar()
        self.statusText.set('')
        self.statusBar = tk.Label(self, textvariable = self.statusText)
        self.statusBar.grid(row=5, column=0, columnspan=4, sticky = 'W')
    
    def openBeamPointingWindow(self):
        if self.cameraName.get() == self.default_camera:
            print('You must first select a camera')
            return

        try:
            self.stopPreview(self.previewPanel)
        except:
            pass    

        if self.bpw is None:
            self.createBeamPointingWindow()
        else:
            print('window already open')
            return


    def createBeamPointingWindow(self):
        self.bpw = tk.Toplevel(self)
        self.bpw.geometry('600x600')
        self.bpw.title('Beam Pointing')
        self.bpw.protocol('WM_DELETE_WINDOW', self.removeBeamPointingWindow)

        self.bpw.saveLabel = tk.Label(self.bpw, text = 'Save location:')
        self.bpw.saveLabel.grid(row = 0, column = 0, columnspan = 1, sticky = 'W')
        
        self.bpw.saveDir = tk.StringVar()
        #home = os.path.expanduser("~")
        #self.saveDir.set(os.path.join(home, 'default_image'))
        self.bpw.saveDir.set(os.path.join('default_image','default_image'))
        
        self.bpw.saveDirBox = tk.Entry(self.bpw, textvariable = self.bpw.saveDir)
        self.bpw.saveDirBox.grid(row=0, column=1, columnspan = 2, sticky='W')

        self.bpw.browseButton = tk.Button(self.bpw, text = 'Browse', command = lambda: self.browseDir(self.bpw.saveDir))
        self.bpw.browseButton.grid(row=0, column=3, columnspan=1, sticky='W')
        
        self.bpw.logCheck = tk.BooleanVar()
        self.bpw.logCheckBox = tk.Checkbutton(self.bpw, text = 'log', variable = self.bpw.logCheck)
        self.bpw.logCheckBox.grid(row=0, column=3, sticky='SE')
        
        self.bpw.disablePlotCheck = tk.BooleanVar()
        self.bpw.disablePlotBox = tk.Checkbutton(self.bpw, text = 'no plot', variable = self.bpw.disablePlotCheck)
        self.bpw.disablePlotBox.grid(row=1, column=3, sticky='NE')

        self.bpw.startBPButton = tk.Button(self.bpw, text='Start Beam Pointing', command = self.startBeamPointing)
        self.bpw.startBPButton.grid(row=0, column=4, columnspan=1, sticky='w')
        self.bpw.stopBPButton = tk.Button(self.bpw, text='Stop Beam Pointing', command = self.stopBeamPointing)
        self.bpw.stopBPButton.grid(row=1, column=4, columnspan=1, sticky='w')

        self.bpw.collectionTimeLabel = tk.Label(self.bpw, text='Collection time, s (-1 = inf):')
        self.bpw.collectionTimeLabel.grid(row=2, column=4, columnspan=1, sticky='sw')

        self.bpw.collectionTime = tk.StringVar()
        self.bpw.collectionTime.set('-1')

        self.bpw.collectionTimeBox = tk.Entry(self.bpw, textvariable=self.bpw.collectionTime, width = 5)
        self.bpw.collectionTimeBox.grid(row=3, column=4, columnspan=1, sticky='nw')

        self.bpw.limitIntervalLabel = tk.Label(self.bpw, text='Limit interval, s (-1 = none):')
        self.bpw.limitIntervalLabel.grid(row=4, column=4, columnspan=1, sticky='sw')

        self.bpw.limitInterval = tk.StringVar()
        self.bpw.limitInterval.set('-1')

        self.bpw.limitIntervalBox = tk.Entry(self.bpw, textvariable=self.bpw.limitInterval, width = 5)
        self.bpw.limitIntervalBox.grid(row=5, column=4, columnspan=1, sticky='nw')

        self.bpw.startPreviewButton = tk.Button(self.bpw, text='Start Preview', command = lambda: self.startPreview(self.bpw.previewPanel))
        self.bpw.startPreviewButton.grid(row=1,column=0, sticky='W')

        self.bpw.stopPreviewButton = tk.Button(self.bpw, text='Stop Preview', command = lambda: self.stopPreview(self.bpw.previewPanel))
        self.bpw.stopPreviewButton.grid(row=1,column=1, sticky='W')

        img = None
        self.bpw.previewPanel = tk.Label(self.bpw, image=img)
        self.bpw.previewPanel.image = img
        self.bpw.previewPanel.grid(row=2, column=0, rowspan=6, columnspan=4, sticky='WESN')

        fig = Figure(figsize=(6,3), dpi=100)
        self.bpw.ax = fig.add_subplot(111)
        self.bpw.ax.set_ylabel('Center position (um)')
        self.bpw.ax.set_xlabel('Time (s)')
        fig.subplots_adjust(bottom=0.15)

        self.bpw.canvas = FigureCanvasTkAgg(fig,master=self.bpw)
        self.bpw.canvas.show()
        #self.bpw.canvas.get_tk_widget().grid(row=8, column=0, columnspan=5, sticky='E')
        self.bpw.canvas._tkcanvas.grid(row=8, column=0, columnspan=5, sticky='E')

    def removeBeamPointingWindow(self):
        try:
            self.stopPreview(self.bpw.previewPanel)
        except:
            pass

        self.bpw.destroy()
        self.bpw = None


    def startBeamPointing(self):
        '''
        '''

        try:
            self.stopPreview(self.bpw.previewPanel)
        except:
            pass

        #create filename 
        if not os.path.exists(os.path.dirname(self.bpw.saveDir.get())):
            os.makedirs(os.path.dirname(self.bpw.saveDir.get()))

        save_time = datetime.datetime.now().strftime('%Y-%m-%d %H%M%S')
        filename = self.bpw.saveDir.get() + save_time + '.txt'
        
        self.bpw.logCheckBox.config(state='disabled')
        if self.bpw.logCheck.get():
            f = open(filename, 'w')
            f.write(datetime.datetime.now().isoformat() + ' Beam Pointing\n')
            f.write('time\tx0\ty0\n')
            f.close

        w = 1280
        h = 720

        #clear axes
        self.bpw.ax.cla()
        self.bpw.ax.set_ylabel('Center position (um)')
        self.bpw.ax.set_xlabel('Time (s)')
        self.bpw.canvas.show()       
        
        #create camera object
        self.bpw.cam = cv2.VideoCapture(np.int(self.cameraName.get()))
        #set image width, height
        self.bpw.cam.set(3,w)
        self.bpw.cam.set(4,h)

        self.bpw.stopEvent = threading.Event()
        self.bpw.thread = threading.Thread(target = lambda: self.beamPointingLoop(filename))
        #start image capture loop
        self.bpw.thread.start()


    def stopBeamPointing(self):
        '''
        '''
        self.bpw.stopEvent.set()
        self.bpw.cam.release()
        self.bpw.logCheckBox.config(state='normal')

        self.bpw.previewPanel.configure(image = None)
        self.bpw.previewPanel.image = None
        #self.statusText.set('Removed preview image')
        self.statusText.set('Stopped Beampointing')


    def beamPointingLoop(self,filename):
        '''
        '''
        #set collection time
        t_end = np.float(self.bpw.collectionTime.get())
        if t_end <= -1:
            t_end = np.inf
        else:
            self.bpw.ax.set_xlim([0,t_end])

        #set minimum interval
        dt_min = np.float(self.bpw.limitInterval.get())
        if dt_min <= -1:
            dt_min = 0

        t0 = time.time()
        timestamp = 0

        width = 400

        #check stop event
        while not self.bpw.stopEvent.wait(dt_min-(time.time()-t0-timestamp)):

            ret, frame = self.bpw.cam.read()
            timestamp = time.time()-t0

            if timestamp > t_end:
                self.stopBeamPointing()

            if ret:

                frame_sized = cv2.resize(frame, (width, np.int(9*width/16)))

                #calculate moments
                moments = calculate_2D_moments(frame.sum(2).astype(float), [PIXEL_SIZE,PIXEL_SIZE], False)
                x = moments[0]
                y = moments[1]

                if self.bpw.logCheck.get():
                    #save to file
                    f = open(filename,'a')
                    f.write('%.3f\t%.2f\t%.2f\n' %(timestamp,x,y))
                    f.close

                if not self.bpw.disablePlotCheck.get():
                    #update figure
                    self.bpw.ax.plot(timestamp,x,'sr')
                    self.bpw.ax.plot(timestamp,y,'ob')
                    self.bpw.canvas.show()

    
                    #update display            
                    #frame_sized = cv2.cvtColor(frame_sized,cv2.COLOR_BGR2RGB)
                    image = ImageTk.PhotoImage(Image.fromarray(frame_sized))
                    
                    self.bpw.previewPanel.configure(image = image)
                    self.bpw.previewPanel.image = image








    '''    
    def checkQueue(self):
        
      try:
         data = self.imgQueue.get_nowait()
         self.previewPanel.configure(image = data)
         self.previewPanel.image = data
      except qu.Empty:
         pass
      
      # make another check
      if not self.stopEvent.is_set():
          self.after_idle(self.checkQueue)
    '''

    def onClose(self):
        '''what to do when window is closed'''
        try:        
            self.stopPreview()   
        except:
            pass
                    
        self.destroy()
        
    
    def onCapture(self):
        """
        Capture frames and save
        """
        
        t0 = time.time()

        #self.stopPreview()

        w = 1280
        h = 720        
        
        cap = cv2.VideoCapture(np.int(self.cameraName.get()))
        #set image width, height
        cap.set(3,w)
        cap.set(4,h)


        
        FRAMES_AVG = np.int(self.imgAvNum.get())

        i = 0
        im=np.zeros((h,w,3))
        
        t1 = time.time()
        #print(t1-t0)
        
        while i<FRAMES_AVG:
            # Capture frame-by-frame

            ret, frame = cap.read()

            if ret:
    
                im = (i*im + frame.astype(float)/255)/(i+1)
            '''
            if frame is not None:
                if i == 0:
                    #first frame
                    im = frame.astype(float)/255
        
                else:
                    #average subsequent frames
                    im = (i*im + frame.astype(float)/255)/(i+1)
            '''

            i += 1


        cap.release()
        self.statusText.set('Image captured')
        #print('Image captured')
        t2 = time.time()
        #print(t2-t0, t2-t1)
        
        #self.startPreview()

        im[:,:,[0,1,2]] = im[:,:,[2,1,0]]
        img = Image.fromarray(np.uint8(im*255))
        
        j = 0
        if not os.path.exists(os.path.dirname(self.saveDir.get())):
            os.makedirs(os.path.dirname(self.saveDir.get()))
        while os.path.exists(self.saveDir.get() + '%03d.jpeg' % j):
            j += 1
        filename = self.saveDir.get() + '%03d.jpeg' % j
        img.save(filename) #this depends on what I use to get the image
        #print('Image saved')
        
        #self.stopPreview() 
        self.startPreview(self.previewPanel)

        t3 = time.time()
        #print(t3-t0, t3-t2)
        self.statusText.set('Image saved: ' + '%03d.jpeg' % j)
        
        
    def startPreview(self,display):
        '''start camera preview'''
        #print(self.stopEvent.is_set())
        self.stopEvent = None
        self.thread = None
        self.thread = threading.Thread(target= lambda: self.videoLoop(display))
        self.stopEvent = threading.Event()

        w = 1280
        h = 720

        self.cam = cv2.VideoCapture(np.int(self.cameraName.get()))
        self.cam.set(3, w)
        self.cam.set(4, h)
        
        self.thread.start()
        self.statusText.set('Preview started')
        
        #self.after(20, self.checkQueue)

    def stopPreview(self, display):
        
        try:
            self.stopEvent.set()
            #self.statusText.set('Set thread stop signal')
            self.cam.release()
            #self.statusText.set('Released camera')
            display.configure(image = None)
            display.image = None
            #self.statusText.set('Removed preview image')
            self.statusText.set('Stopped Preview')

        except:
            raise
        
       
    def videoLoop(self,display):
        
        try:
            #stop_check = self.stopEvent.is_set()
            while not self.stopEvent.wait(0.05):
                # Capture frame-by-frame

                r,frame = self.cam.read()
                
                if r:
                    #print('got frame')
                    width = 400
                    frame_sized = cv2.resize(frame, (width, np.int(9*width/16)))  
                
                    # Display the resulting frame
                    #cv2.imshow(WINDOW_NAME,frame_sized)
                
                    frame_sized = cv2.cvtColor(frame_sized,cv2.COLOR_BGR2RGB)
                    image = Image.fromarray(frame_sized)
                    img = ImageTk.PhotoImage(image)
                    
                    #self.imgQueue.put(img)
                    #self.after(20, self.videoLoop)
                    
                    display.configure(image = img)
                    display.image = img
                    #print(frame.shape)
                    sat_det = self.checkChannelSat(frame_sized)
                    self.setChannelSat(sat_det)
                
                #self.previewPanel.after(10, self.videoLoop)
                
        except AssertionError:
            #print('Some dumb AssertionError')
            raise
            
        except RuntimeError:
            #print('WTF, why a runtime error?')
            raise
        
        except:
            #print('Probably some stupid cv2 error... threading... yada, yada, yada')
            raise
#        cv2.waitKey(1)

        
    def getCameras(self):
        '''get list of available cameras'''

        camNum = 0
        camera_list =[]
        while camNum < 3:
            cam = cv2.VideoCapture(camNum)
            open_bool = cam.isOpened()
        
            if open_bool:
                camera_list.append(camNum)
        
            camNum += 1   
            
        return camera_list
        
    def browseDir(self, save_object):
        '''select save directory
        save_object should be tkinter string variable
        '''
        directory = asksaveasfilename()
        save_object.set(directory)
        
    
    def checkChannelSat(self,im):
        '''
        check preview image channel satursation
        '''
        bits = self.sensorRes.get()
        satlim = 0.001
        sat_det = np.zeros(im.shape[2])
        
        for ind,_ in enumerate(sat_det):
        
            sat_ratio = (im[:,:,ind] >= 2**bits-1).sum()/((im[:,:,ind] != 0).sum()+1)

            if sat_ratio <= satlim:
                sat_det[ind] = 0
            else:
                sat_det[ind] = 1
                
        return sat_det
    
    
    def setChannelSat(self, sat_det):
        '''
        set appropriate rgb indicator label for saturation
        sat_det is 1x3 boolean, 0=not sat, 1=sat
        '''
        
        channels = [self.rSat, self.gSat, self.bSat]
        cols = ['red', 'green', 'blue']

        for ind, ch in enumerate(channels):
            if sat_det[ind]:
                ch.configure(bg=cols[ind])
            else:
                ch.configure(bg=self.bgColor)

                
            
        
        
'''
root = Tk()
root.title("Beam Profile Collection")
root.geometry('425x350')

app = Application(root)

root.mainloop()
'''

app = Application()
app.title("Beam Profile Collection")
app.mainloop()
