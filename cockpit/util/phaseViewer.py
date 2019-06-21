##This is a window for selecting the ROI for interferometry
# !/usr/bin/python
# -*- coding: utf-8
#
# Copyright 2019 Nick Hall (nicholas.hall@dtc.ox.ac.uk)
# Copyright 2019 Mick Phillips (mick.phillips@gmail.com)
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

import numpy as np
import wx
from wx.lib.floatcanvas.FloatCanvas import FloatCanvas
import cockpit.util.userConfig as Config
import matplotlib.pyplot as plt

## Default viewer dimensions.
DEF_VIEW_WIDTH, DEF_VIEW_HEIGHT = (512, 512)

def normalise(array, scaling = 1):
    minimum = np.min(array)
    maximum = np.max(array)
    norm_array = ((array-minimum)/(maximum-minimum))*scaling
    return norm_array

class viewPhase(wx.Frame):
    def __init__(self, input_image, image_ft):
        cycle_diff = abs(np.max(input_image) - np.min(input_image)) / (2.0 * np.pi)
        rms_phase = np.sqrt(np.mean(input_image ** 2))

        VIEW_HEIGHT = max(DEF_VIEW_HEIGHT, input_image.shape[0], image_ft.shape[0])
        VIEW_WIDTH = max(DEF_VIEW_WIDTH, input_image.shape[1], image_ft.shape[1])

        wx.Frame.__init__(self, None, -1, 'Visualising phase. '
                                          'Peak difference: %.05f, RMS difference: %.05f'
                          %(cycle_diff,rms_phase))
        # Use np.require to ensure data is C_CONTIGUOUS.
        image_norm = np.require(normalise(input_image,scaling=255), requirements='C')
        image_norm_rgb = np.stack((image_norm.astype('uint8'),)*3,axis=-1)

        image_ft_norm = np.require(normalise(image_ft, scaling=255), requirements='C')
        image_ft_norm_rgb = np.stack((image_ft_norm.astype('uint8'),) * 3, axis=-1)

        self.Sizer = wx.BoxSizer(wx.VERTICAL)
        self.img = wx.Image(VIEW_HEIGHT,
                            VIEW_WIDTH,
                            image_norm_rgb)
        self.img_ft = wx.Image(VIEW_HEIGHT,
                               VIEW_WIDTH,
                               image_ft_norm_rgb)
        # # Canvas
        self.canvas = FloatCanvas(self, size=self.img.GetSize())
        self.bitmaps = {'r': self.canvas.AddBitmap(self.img, (0,0), Position='cc'),
                        'f': self.canvas.AddBitmap(self.img_ft, (0,0), Position='cc')}
        self.bitmaps['f'].Hide()
        #Set flag of current image type
        self.showing_fourier = False
        self.Sizer.Add(self.canvas)
        # Save button
        saveBtn = wx.Button(self, label='Real/Fourier Transform switch')
        saveBtn.Bind(wx.EVT_BUTTON, self.onSwitch)
        self.Sizer.Add(saveBtn)
        self.Fit()
        self.Show()

    def onSwitch(self, event):
        if self.showing_fourier:
            self.bitmaps['r'].Show()
            self.bitmaps['f'].Hide()
        else:
            self.bitmaps['f'].Show()
            self.bitmaps['r'].Hide()
        self.showing_fourier = not self.showing_fourier
        self.canvas.Draw(Force=True)



if __name__ == '__main__':
    image = np.zeros((768,600))
    image[:int(image.shape[0]/2),:] = 1
    image_ft = image[::-1]

    app = wx.App()
    frame = viewPhase(image,image_ft)
    app.MainLoop()