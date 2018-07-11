#Cockpit Device file for Alpao AO device.
#Copyright Ian Dobbie, 2017
#released under the GPL 3+
#
#This file provides the cockpit end of the driver for the Alpao deformable
#mirror as currently mounted on DeepSIM in Oxford

from collections import OrderedDict
import device
import depot
import devices.boulderSLM
import events
import wx
import interfaces.stageMover
import interfaces.imager
import socket
import util
import time
import struct
import gui.device
import gui.guiUtils
import gui.toggleButton
import Pyro4
import Tkinter as tk
from PIL import Image, ImageTk
import util.userConfig as Config

import numpy as np
import scipy.stats as stats

#Create accurate look up table for certain Z positions
##LUT dict has key of Z positions
try:
    LUT_array = np.loadtxt("remote_focus_LUT.txt")
    LUT = {}
    for ii in (LUT_array[:,0])[:]:
        LUT[ii] = LUT_array[np.where(LUT_array == ii)[0][0],1:]
except:
    pass

#the AO device subclasses Device to provide compatibility with microscope.
class Alpao(device.Device):
    def __init__(self, name, config={}):
        device.Device.__init__(self, name, config)
        self.AlpaoConnection = None
        self.sendImage=False
        self.curCamera = None

        #device handle for SLM device
        self.slmdev=None

        self.buttonName='Alpao'
        events.subscribe('camera enable', lambda c, isOn: self.onCameraEnable(c, isOn))

        ## Connect to the remote program
    def initialize(self):
        self.AlpaoConnection = Pyro4.Proxy(self.uri)
        self.socket=socket.socket()
        self.socket.bind(('129.67.73.152',8867))
        self.socket.listen(2)
        self.listenthread()
        self.awaitimage=False
        #No using a connection, using a listening socket.
        #self.connectthread()
        #subscribe to enable camera event to get access the new image queue
        events.subscribe('camera enable',
                lambda c, isOn: self.enablecamera( c, isOn))

    def remote_ac_fits(self):
        #For Z positions which have not been calibrated, approximate with
        #a regression of known positions.
        ## ACTUATOR_FITS has key of actuators
        self.no_actuators = self.AlpaoConnection.get_n_actuators()
        self.actuator_slopes = np.zeros(self.no_actuators)
        self.actuator_intercepts = np.zeros(self.no_actuators)

        pos = np.sort(LUT_array[:,0])[:]
        ac_array = np.zeros((np.shape(LUT_array)[0],self.no_actuators))

        count = 0
        for jj in pos:
            ac_array[count,:] = LUT_array[np.where(LUT_array == jj)[0][0],1:]
            count += 1

        for kk in range(self.no_actuators):
            s, i, r, p, se = stats.linregress(pos, ac_array[:,kk])
            self.actuator_slopes[kk] = s
            self.actuator_intercepts[kk] = i

    @util.threads.callInNewThread
    def listenthread(self):
        while 1:
            (self.clientsocket, address)=self.socket.accept()
            if self.clientsocket:
                print "socket connected", address
                noerror=True
                while noerror:
                    try:
                        input=self.clientsocket.recv(100)
                        print input
                    except socket.error,e:
                        noerror=False
                        print 'Labview socket disconnected'
                        break

                    if(input[:4]=='getZ'):
                        reply=str(self.getPiezoPos())+'\r\n'
                    elif (input[:4]=='setZ'):
                        pos=float(input[4:])
                        reply=str(self.movePiezoAbsolute(pos))+'\r\n'
                    elif (input[:8]=='getimage'):
                        self.sendImage=True
                        self.takeImage()
                        reply=None
                    elif (input[:13]=='setWavelength'):
                        print "setWavelength",input
                        self.wavelength=float(input[14:])
                        print "wavelength=",self.wavelength
                        reply=str(self.wavelength)+'\r\n'
                        self.awaitimage=True
                    else:
                        reply='Unknown command\r\n'
                    #print reply
                    try:
                        if (reply is not None):
                            self.clientsocket.send(reply)
                    except socket.error,e:
                        noerror=False
                        print 'Labview socket disconnected'
                        break
                    if self.awaitimage:
                        if (self.slmdev is None):
                            self.slmdev=depot.getDevice(devices.boulderSLM)
                            self.slmsize=self.slmdev.connection.get_shape()
                            print self.slmsize
                            print self.wavelength
                        #self.slmImage=N.zero((512,512),dtype=uint16)
                        try:
                            data=self.clientsocket.recv(512*512*2)
                            print len(data)
                            tdata=struct.unpack('H'*(512*512),data)
                            print tdata[:10]
                            #self.slmImage=N.frombuffer(
                             #   buffer(self.clientsocket.recv(512*512*2)),
                              #  dtype='uint16',count=512*512)
                            self.awaitimage=False
                            self.slmdev.connection.set_custom_sequence(
                                self.wavelength,
                                [tdata,tdata])

                        except socket.error,e:
                            noerror=False
                            print 'Labview socket disconnected'
                            break

    def onCameraEnable(self, camera, isOn):
        self.curCamera = camera

    ### UI functions ###
    def makeUI(self, parent):
        self.panel = wx.Panel(parent)
        self.panel.SetDoubleBuffered(True)
        sizer = wx.BoxSizer(wx.VERTICAL)
        label_setup = gui.device.Label(
            parent=self.panel, label='AO set-up')
        sizer.Add(label_setup)
        rowSizer = wx.BoxSizer(wx.VERTICAL)
        self.elements = OrderedDict()

        selectCircleButton = gui.toggleButton.ToggleButton(
            label='Select ROI',
        #Button to calibrate the DM
            activateAction=self.onSelectCircle,
            deactivateAction=self.deactivateSelectCircle,
            activeLabel='Selecting ROI',
            inactiveLabel='Select ROI',
            parent=self.panel,
            size=gui.device.DEFAULT_SIZE)
        self.elements['selectCircleButton'] = selectCircleButton

        calibrateButton = gui.toggleButton.ToggleButton(
            label='Calibrate',
        #Button to calibrate the DM
            parent=self.panel,
            size=gui.device.DEFAULT_SIZE)
        calibrateButton.Bind(wx.EVT_LEFT_DOWN, lambda evt: self.onCalibrate())
        self.elements['calibrateButton'] = calibrateButton

        characteriseButton = gui.toggleButton.ToggleButton(
            label='Characterise',
        #Button to calibrate the DM
            parent=self.panel,
            size=gui.device.DEFAULT_SIZE)
        characteriseButton.Bind(wx.EVT_LEFT_DOWN, lambda evt: self.onCharacterise())
        self.elements['characteriseButton'] = characteriseButton

        label_use = gui.device.Label(
            parent=self.panel, label='AO use')
        self.elements['label_use'] = label_use

        # Reset the DM actuators
        resetButton = gui.toggleButton.ToggleButton(
            label='Reset DM',
            parent=self.panel,
            size=gui.device.DEFAULT_SIZE)
        resetButton.Bind(wx.EVT_LEFT_DOWN, lambda evt:self.AlpaoConnection.send(
                                            np.zeros(self.AlpaoConnection.get_n_actuators())))
        self.elements['resetButton'] = resetButton

        # Visualise current interferometric phase
        visPhaseButton = gui.toggleButton.ToggleButton(
            label='Visualise Phase',
            parent=self.panel,
            size=gui.device.DEFAULT_SIZE)
        visPhaseButton.Bind(wx.EVT_LEFT_DOWN, lambda evt: self.onVisualisePhase())
        self.elements['visPhaseButton'] = visPhaseButton

        # Button to flatten the wavefront
        flattenButton = gui.toggleButton.ToggleButton(
            label='Flatten',
            parent=self.panel,
            size=gui.device.DEFAULT_SIZE)
        flattenButton.Bind(wx.EVT_LEFT_DOWN, lambda evt: self.onFlatten())
        self.elements['flattenButton'] = flattenButton

        # Step the focal plane up one step
        stepUpButton = gui.toggleButton.ToggleButton(
            label='Step up',
            parent=self.panel,
            size=gui.device.DEFAULT_SIZE)
        stepUpButton.Bind(wx.EVT_LEFT_DOWN, lambda evt: None)
        self.elements['stepUpButton'] = stepUpButton

        # Step the focal plane up one step
        stepDownButton = gui.toggleButton.ToggleButton(
            label='Step down',
            parent=self.panel,
            size=gui.device.DEFAULT_SIZE)
        stepDownButton.Bind(wx.EVT_LEFT_DOWN, lambda evt: None)
        self.elements['stepDownButton'] = stepDownButton

        for e in self.elements.values():
            rowSizer.Add(e)
        sizer.Add(rowSizer)
        self.panel.SetSizerAndFit(sizer)
        self.hasUI = True
        return self.panel


    @util.threads.callInNewThread
    def connectthread(self):
        self.socket=socket.socket()
        self.socket.connect(('129.67.77.21',8868))
 #       self.socket.setblocking(0)
        i=0
        while 1:
            i=i+1
            input=self.recv_end(self.socket)

            print input

            output=self.socket.send('hello'+str(i)+'\r\n')
            print "sent bytes",output
            time.sleep(1)



    def recv_end(self,the_socket):
        End='crlf'
        total_data=[];data=''
        while True:
            data=the_socket.recv(100)
            print data
            if End in data:
                total_data.append(data[:data.find(End)])
                break
            total_data.append(data)
            if len(total_data)>1:
                #check if end_of_data was split
                last_pair=total_data[-2]+total_data[-1]
                if End in last_pair:
                    total_data[-2]=last_pair[:last_pair.find(End)]
                    total_data.pop()
                    break
        return ''.join(total_data)

    def getPiezoPos(self):
        return(interfaces.stageMover.getAllPositions()[1][2])

    def movePiezoRelative(self, distance):
        current=self.getPiezoPos()
        currentpos=self.movePiezoAbsolute(current+distance)
        return currentpos

    def movePiezoAbsolute(self, position):
#        originalHandlerIndex= interfaces.stageMover.mover.curHandlerIndex
#        interfaces.stageMover.mover.curHandlerIndex=1
        handler=interfaces.stageMover.mover.axisToHandlers[2][1]
        handler.moveAbsolute(position)
#        interfaces.stageMover.mover.curHandlerIndex=originalHandlerIndex
        return (self.getPiezoPos())

    def bin_ndarray(self, ndarray, new_shape, operation='sum'):
        """
        Function acquired from Stack Overflow: https://stackoverflow.com/a/29042041. Stack Overflow or other Stack Exchange
        sites is cc-wiki (aka cc-by-sa) licensed and requires attribution.
        Bins an ndarray in all axes based on the target shape, by summing or
            averaging.
        Number of output dimensions must match number of input dimensions and
            new axes must divide old ones.
        Example
        -------
        m = np.arange(0,100,1).reshape((10,10))
        n = bin_ndarray(m, new_shape=(5,5), operation='sum')
        print(n)
        [[ 22  30  38  46  54]
         [102 110 118 126 134]
         [182 190 198 206 214]
         [262 270 278 286 294]
         [342 350 358 366 374]]
        """
        operation = operation.lower()
        if not operation in ['sum', 'mean']:
            raise ValueError("Operation not supported.")
        if ndarray.ndim != len(new_shape):
            raise ValueError("Shape mismatch: {} -> {}".format(ndarray.shape,
                                                               new_shape))
        compression_pairs = [(d, c // d) for d, c in zip(new_shape,
                                                         ndarray.shape)]
        flattened = [l for p in compression_pairs for l in p]
        ndarray = ndarray.reshape(flattened)
        for i in range(len(new_shape)):
            op = getattr(ndarray, operation)
            ndarray = op(-1 * (i + 1))
        return ndarray

    def onSelectCircle(self):
        image_raw = self.AlpaoConnection.acquire_raw()
        if np.max(image_raw) > 10:
            temp = self.bin_ndarray(image_raw, new_shape=(512, 512), operation='mean')
            self.createCanvas(temp)
        else:
            print("Detecting nothing but background noise")

    def createCanvas(self,temp):
        app = App(image_np=temp)
        app.master.title('Select a circle')
        app.mainloop()

    def deactivateSelectCircle(self):
        # Read in the parameters needed for the phase mask
        try:
            self.parameters = np.asarray(Config.getValue('alpao_circleParams', isGlobal = True))
        except IOError:
            print("Error: Masking parameters do not exist. Please select circle.")
            return
        self.AlpaoConnection.set_roi(self.parameters[0], self.parameters[1],
                                         self.parameters[2])

    def enablecamera(self,camera,isOn):
        self.curCamera = camera
        # Subscribe to new image events only after canvas is prepared.
        if (isOn is True):
            events.subscribe("new image %s" % self.curCamera.name, self.onImage)
        else:
            events.unsubscribe("new image %s" % self.curCamera.name, self.onImage)
        ## Receive a new image and send it to our canvas.

    def onCalibrate(self):
        try:
            self.AlpaoConnection.get_roi()
        except Exception as e:
            try:
                self.parameters = Config.getValue('alpao_circleParams', isGlobal=True)
                self.AlpaoConnection.set_roi(self.parameters[0], self.parameters[1],
                                            self.parameters[2])
            except:
                raise e

        try:
            self.AlpaoConnection.get_fourierfilter()
        except Exception as e:
            try:
                test_image = self.AlpaoConnection.acquire()
                self.AlpaoConnection.set_fourierfilter(test_image=test_image)
            except:
                raise e

        controlMatrix = self.AlpaoConnection.calibrate()
        Config.setValue('alpao_controlMatrix', np.ndarray.tolist(controlMatrix), isGlobal=True)

    def onCharacterise(self):
        try:
            self.AlpaoConnection.get_roi()
        except Exception as e:
            try:
                self.parameters = Config.getValue('alpao_circleParams', isGlobal=True)
                self.AlpaoConnection.set_roi(self.parameters[0], self.parameters[1],
                                             self.parameters[2])
            except:
                raise e

        try:
            self.AlpaoConnection.get_fourierfilter()
        except Exception as e:
            try:
                test_image = self.AlpaoConnection.acquire()
                self.AlpaoConnection.set_fourierfilter(test_image=test_image)
            except:
                raise e

        try:
            self.AlpaoConnection.get_controlMatrix()
        except Exception as e:
            try:
                self.controlMatrix = Config.getValue('alpao_controlMatrix', isGlobal=True)
                self.AlpaoConnection.set_controlMatrix(self.controlMatrix)
            except:
                raise e
        assay = self.AlpaoConnection.assess_character()
        np.save('characterisation_assay', assay)
        app = View(image_np=assay)
        app.master.title('Characterisation')
        app.mainloop()

    def onVisualisePhase(self):
        try:
            self.AlpaoConnection.get_roi()
        except Exception as e:
            try:
                param = np.asarray(Config.getValue('alpao_circleParams', isGlobal=True))
                self.AlpaoConnection.set_roi(y0 = param[0], x0 = param[1],
                                             radius = param[2])
            except:
                raise e

        try:
            self.AlpaoConnection.get_fourierfilter()
        except:
            try:
                test_image = self.AlpaoConnection.acquire()
                self.AlpaoConnection.set_fourierfilter(test_image=test_image)
            except Exception as e:
                raise e

        interferogram, unwrapped_phase = self.AlpaoConnection.acquire_unwrapped_phase()
        np.save('interferogram', interferogram)
        np.save('unwrapped_phase', unwrapped_phase)
        original_dim = int(np.shape(unwrapped_phase)[0])
        resize_dim = original_dim/2
        while original_dim % resize_dim is not 0:
            resize_dim -= 1
        unwrapped_phase_resize = self.bin_ndarray(unwrapped_phase, new_shape=
                                    (resize_dim, resize_dim), operation='mean')
        app = View(image_np=unwrapped_phase_resize)
        app.master.title('Unwrapped interferogram')
        app.mainloop()

    def onFlatten(self):
        try:
            self.AlpaoConnection.get_roi()
        except Exception as e:
            try:
                self.parameters = Config.getValue('alpao_circleParams', isGlobal=True)
                self.AlpaoConnection.set_roi(self.parameters[0], self.parameters[1],
                                             self.parameters[2])
            except:
                raise e

        try:
            self.AlpaoConnection.get_fourierfilter()
        except Exception as e:
            try:
                test_image = self.AlpaoConnection.acquire()
                self.AlpaoConnection.set_fourierfilter(test_image=test_image)
            except:
                raise e

        try:
            self.AlpaoConnection.get_controlMatrix()
        except Exception as e:
            try:
                self.controlMatrix = Config.getValue('alpao_controlMatrix', isGlobal=True)
                self.AlpaoConnection.set_controlMatrix(self.controlMatrix)
            except:
                raise e
        flat_values = self.AlpaoConnection.flatten_phase(iterations=10)
        Config.setValue('alpao_flat_values', np.ndarray.tolist(flat_values), isGlobal=True)



    def onImage(self, data, *args):
        if(self.sendImage):
            if(self.clientsocket):
                try:
                    message=''
                    t=time.clock()
                    print data.shape
                    print "presend"
                    #for i in range(data.shape[0]):
                    #    for j in range(data.shape[1]):
                    #        message=message+str(data[i,j])+'\t'
                    #    message=message+'\n'
                    #print message
                    self.clientsocket.send(data)
                    print "sent data"
 #                   self.clientsocket.send('\r\n')
 #                   print "sent end"
                    self.sendImage=False
                    end=time.clock()-t
                    print "time=",end
                except socket.error,e:
                    noerror=False
                    print 'Labview socket disconnected'

    def showDebugWindow(self):
        # Ensure only a single instance of the window.
        global _windowInstance
        window = globals().get('_windowInstance')
        if window:
            try:
                window.Raise()
                return None
            except:
                pass
        # If we get this far, we need to create a new window.
        global _deviceInstance
        alpaoOutputWindow(self, parent=wx.GetApp().GetTopWindow()).Show()


## This debugging window lets each digital lineout of the DSP be manipulated
# individually.
class alpaoOutputWindow(wx.Frame):
    def __init__(self, AoDevice, parent, *args, **kwargs):
        wx.Frame.__init__(self, parent, *args, **kwargs)
        ## alpao Device instance.
        self.alpao = AoDevice
        self.SetTitle("Alpao AO device control")
        # Contains all widgets.
        self.panel = wx.Panel(self)
        font=wx.Font(12,wx.FONTFAMILY_DEFAULT,wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        allPositions = interfaces.stageMover.getAllPositions()
        self.piezoPos = allPositions[1][2]
        textSizer=wx.BoxSizer(wx.VERTICAL)
        self.piezoText=wx.StaticText(self.panel,-1,str(self.piezoPos),
                style=wx.ALIGN_CENTER)
        self.piezoText.SetFont(font)
        textSizer.Add(self.piezoText, 0, wx.EXPAND|wx.ALL,border=5)
        mainSizer.Add(textSizer, 0,  wx.EXPAND|wx.ALL,border=5)
        self.panel.SetSizerAndFit(mainSizer)
        events.subscribe('stage position', self.onMove)


    def onMove(self, axis, *args):
        if axis != 2:
            # We only care about the Z axis.
            return
        self.piezoText.SetLabel(
            str(interfaces.stageMover.getAllPositions()[1][2]))

##This is a window for selecting the ROI for interferometry
#!/usr/bin/python
# -*- coding: utf-8
#
# Copyright 2017 Mick Phillips (mick.phillips@gmail.com)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Display a window that allows the user to select a circular area."""

class App(tk.Frame):
    def __init__(self, image_np, master=None):
        tk.Frame.__init__(self, master)
        self.pack()
        self.ratio = 1
        self.offset = [45, 50]
        self.image_np = image_np
        self.create_widgets()

    def create_widgets(self):
        self.canvas = Canvas(self, width=600, height=600)
        self.array = np.asarray(self.image_np)
        self.convert = Image.fromarray(self.array)
        self.image = ImageTk.PhotoImage(image = self.convert)
        self.canvas.create_image(self.offset[0], self.offset[1], anchor = tk.NW, image = self.image)
        self.canvas.pack()

class Canvas(tk.Canvas):
    def __init__(self, *args, **kwargs):
        tk.Canvas.__init__(self, *args, **kwargs)
        self.bind("<Button-1>", self.on_click)
        self.bind("<Button-3>", self.on_click)
        self.bind("<B1-Motion>", self.circle_resize)
        self.bind("<B3-Motion>", self.circle_drag)
        self.bind("<ButtonRelease>", self.on_release)
        self.circle = None
        self.p_click = None
        self.bbox_click = None
        self.centre = [0,0]
        self.radius = 0
        self.ratio = 4
        self.offset = [45, 50]

    def on_release(self, event):
        self.p_click = None
        self.bbox_click = None

    def on_click(self, event):
        if self.circle == None:
            self.circle = self.create_oval((event.x-1, event.y-1, event.x+1, event.y+1))
            self.centre[0] = (event.x - self.offset[0]) * self.ratio
            self.centre[1] = (event.y - self.offset[1]) * self.ratio
            self.radius = ((event.x+1 - event.x+1 + 1) * self.ratio)/2
            Config.setValue('alpao_circleParams', (self.centre[1], self.centre[0], self.radius), isGlobal=True)

    def circle_resize(self, event):
        if self.circle is None:
            return
        if self.p_click is None:
            self.p_click = (event.x, event.y)
            self.bbox_click = self.bbox(self.circle)
            return
        bbox = self.bbox(self.circle)
        unscaledCentre = ((bbox[2] + bbox[0])/2, (bbox[3] + bbox[1])/2)
        r0 = ((self.p_click[0] - unscaledCentre[0])**2 + (self.p_click[1] - unscaledCentre[1])**2)**0.5
        r1 = ((event.x - unscaledCentre[0])**2 + (event.y - unscaledCentre[1])**2)**0.5
        scale = r1 / r0
        self.scale(self.circle, unscaledCentre[0], unscaledCentre[1], scale, scale)
        self.p_click= (event.x, event.y)
        self.radius = ((self.bbox(self.circle)[2] - self.bbox(self.circle)[0]) * self.ratio)/2
        Config.setValue('alpao_circleParams', (self.centre[1], self.centre[0], self.radius), isGlobal=True)

    def circle_drag(self, event):
        if self.circle is None:
            return
        if self.p_click is None:
            self.p_click = (event.x, event.y)
            return
        self.move(self.circle,
                  event.x - self.p_click[0],
                  event.y - self.p_click[1])
        self.p_click = (event.x, event.y)
        bbox = self.bbox(self.circle)
        unscaledCentre = ((bbox[2] + bbox[0]) / 2, (bbox[3] + bbox[1]) / 2)
        self.centre[0] = (unscaledCentre[0] - self.offset[0]) * self.ratio
        self.centre[1] = (unscaledCentre[1] - self.offset[1]) * self.ratio
        Config.setValue('alpao_circleParams', (self.centre[1], self.centre[0], self.radius), isGlobal=True)
        self.update()

class View(tk.Frame):
    def __init__(self, image_np, master=None):
        tk.Frame.__init__(self, master)
        self.pack()
        self.ratio = 1
        self.offset = [25, 25]
        self.image_np = image_np
        self.create_widgets()

    def create_widgets(self):
        self.canvas = tk.Canvas(self, width=700, height=700)
        self.array = np.asarray(self.image_np)
        self.array_norm = (self.image_np/np.max(self.image_np))*255.0
        self.convert = Image.fromarray(self.array_norm)
        self.convert_flip = self.convert.transpose(Image.FLIP_TOP_BOTTOM)
        self.image = ImageTk.PhotoImage(image = self.convert_flip)
        self.canvas.create_image(self.offset[0], self.offset[1], anchor = tk.NW, image = self.image)
        self.canvas.pack()
