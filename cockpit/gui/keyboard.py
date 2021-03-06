#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Copyright (C) 2018 Mick Phillips <mick.phillips@gmail.com>
## Copyright (C) 2018 Ian Dobbie <ian.dobbie@bioch.ox.ac.uk>
##
## This file is part of Cockpit.
##
## Cockpit is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## Cockpit is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Cockpit.  If not, see <http://www.gnu.org/licenses/>.

## Copyright 2013, The Regents of University of California
##
## Redistribution and use in source and binary forms, with or without
## modification, are permitted provided that the following conditions
## are met:
##
## 1. Redistributions of source code must retain the above copyright
##   notice, this list of conditions and the following disclaimer.
##
## 2. Redistributions in binary form must reproduce the above copyright
##   notice, this list of conditions and the following disclaimer in
##   the documentation and/or other materials provided with the
##   distribution.
##
## 3. Neither the name of the copyright holder nor the names of its
##   contributors may be used to endorse or promote products derived
##   from this software without specific prior written permission.
##
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
## "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
## LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
## FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
## COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
## INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
## BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
## LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
## CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
## LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
## ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
## POSSIBILITY OF SUCH DAMAGE.


import wx

from cockpit import depot
import cockpit.gui.camera.window
import cockpit.gui.guiUtils
import cockpit.gui.mosaic.window
import cockpit.interfaces.stageMover

from distutils import version
from itertools import chain

def onChar(evt):
    if isinstance(evt.EventObject, wx.TextCtrl) \
            or evt.KeyCode in [wx.WXK_TAB, wx.WXK_ESCAPE]:
        evt.Skip()
        return
    if isinstance(evt.EventObject, (wx.ToggleButton, wx.Button)) \
            and evt.KeyCode in [wx.WXK_RETURN, wx.WXK_SPACE, wx.WXK_TAB]:
        evt.Skip()
        return
    if evt.KeyCode == wx.WXK_NUMPAD_MULTIPLY:
        cockpit.gui.camera.window.rescaleViews()
    elif evt.KeyCode == wx.WXK_NUMPAD_DIVIDE:
        cockpit.interfaces.stageMover.changeMover()
    elif evt.KeyCode == wx.WXK_NUMPAD_DECIMAL:
        cockpit.gui.mosaic.window.transferCameraImage()
    elif evt.KeyCode == wx.WXK_NUMPAD_SUBTRACT:
        cockpit.interfaces.stageMover.recenterFineMotion()
    elif evt.KeyCode == wx.WXK_DOWN:
        # Z down
        cockpit.interfaces.stageMover.step((0,0,-1))
    elif evt.KeyCode == wx.WXK_NUMPAD2:
        # Y down
        cockpit.interfaces.stageMover.step((0, -1, 0))
    elif evt.KeyCode == wx.WXK_NUMPAD3:
        # Decrease delta
        cockpit.interfaces.stageMover.changeStepSize(-1)
    elif evt.KeyCode == wx.WXK_NUMPAD4:
        # X up
        cockpit.interfaces.stageMover.step((1, 0, 0))
    elif evt.KeyCode == wx.WXK_NUMPAD5:
        # Stop motion
        # TODO: was never handled.
        pass
    elif evt.KeyCode == wx.WXK_NUMPAD6:
        # X down
        cockpit.interfaces.stageMover.step((-1, 0, 0))
    elif evt.KeyCode == wx.WXK_UP:
        # Z up
        cockpit.interfaces.stageMover.step((0, 0, 1))
    elif evt.KeyCode == wx.WXK_NUMPAD8:
        # Y up
        cockpit.interfaces.stageMover.step((0, 1, 0))
    elif evt.KeyCode == wx.WXK_NUMPAD9:
        # Increase delta
        cockpit.interfaces.stageMover.changeStepSize(1)
    elif evt.KeyCode in [wx.WXK_NUMPAD_ADD, wx.WXK_NUMPAD0]:
        # Take image
        cockpit.interfaces.imager.takeImage()
    else:
        evt.Skip()


## Given a wx.Window instance, set up keyboard controls for that instance.
def setKeyboardHandlers(window):
    accelTable = wx.AcceleratorTable([
        # Pop up a menu to help the user find hidden windows.
        (wx.ACCEL_CTRL, ord('M'), 6321),
        # toggle python shell state with ^P
        (wx.ACCEL_CTRL, ord('P'), 6322),
    ])
    window.SetAcceleratorTable(accelTable)
    window.Bind(wx.EVT_MENU, lambda e: martialWindows(window), id=6321)
    window.Bind(wx.EVT_MENU, lambda e: showHideShell(window), id=6322)
    window.Bind(wx.EVT_CHAR_HOOK, onChar)

## Pop up a menu under the mouse that helps the user find a window they may
# have lost.
def martialWindows(parent):
    primaryWindows = wx.GetApp().primaryWindows
    secondaryWindows = wx.GetApp().secondaryWindows
    otherWindows = [w for w in wx.GetTopLevelWindows() 
                        if w not in (primaryWindows + secondaryWindows)]
    # windows = wx.GetTopLevelWindows()
    menu = wx.Menu()
    menuId = 1000
    menu.Append(menuId, "Reset window positions")
    parent.Bind(wx.EVT_MENU,
                lambda e: wx.GetApp().SetWindowPositions(), id= menuId)
    menuId += 1
    #for i, window in enumerate(windows):
    for i, window in enumerate(primaryWindows):
        if not window.GetTitle():
            # Sometimes we get bogus top-level windows; no idea why.
            # Just skip them.
            # \todo Figure out where these windows come from and either get
            # rid of them or fix them so they don't cause trouble here.
            continue
        subMenu = wx.Menu()
        subMenu.Append(menuId, "Raise to top")
        parent.Bind(wx.EVT_MENU,
                    lambda e, window = window: window.Raise(),id=menuId)
        menuId += 1
        subMenu.Append(menuId, "Move to mouse")
        parent.Bind(wx.EVT_MENU,
                lambda e, window = window: window.SetPosition(wx.GetMousePosition()), id=menuId)
        menuId += 1
        subMenu.Append(menuId, "Move to top-left corner")
        parent.Bind(wx.EVT_MENU,
                lambda e, window = window: window.SetPosition((0, 0)),
                    id=menuId)
        menuId += 1
        # Some windows have very long titles (e.g. the Macro Stage View),
        # so just take the first 50 characters.
        if version.LooseVersion(wx.__version__) < version.LooseVersion('4'):
            menu.AppendMenu(menuId, str(window.GetTitle())[:50], subMenu)
        else:
            menu.AppendSubMenu(subMenu, str(window.GetTitle())[:50])
        menuId += 1

    menu.AppendSeparator()
    for i, window in enumerate(secondaryWindows):
        if not window.GetTitle():
            # Sometimes we get bogus top-level windows; no idea why.
            # Just skip them.
            # \todo Figure out where these windows come from and either get
            # rid of them or fix them so they don't cause trouble here.
            continue
        subMenu = wx.Menu()
        subMenu.Append(menuId, "Show/Hide")
        parent.Bind(wx.EVT_MENU,
                lambda e, window = window: ((window.Restore() and
                    (cockpit.util.userConfig.setValue('windowState'+window.GetTitle(),
                                               1)))
                                                if window.IsIconized() 
                                                else ((window.Show(not window.IsShown()) ) and (cockpit.util.userConfig.setValue('windowState'+window.GetTitle(),0)))), id=menuId)
        menuId += 1
        subMenu.Append(menuId, "Move to mouse")
        parent.Bind(wx.EVT_MENU,
                lambda e, window = window: window.SetPosition(wx.GetMousePosition()), id=menuId)
        menuId += 1
        # Some windows have very long titles (e.g. the Macro Stage View),
        # so just take the first 50 characters.
        if version.LooseVersion(wx.__version__) < version.LooseVersion('4'):
            menu.AppendMenu(menuId, str(window.GetTitle())[:50], subMenu)
        else:
            menu.AppendSubMenu(subMenu, str(window.GetTitle())[:50])
        menuId += 1

    # Add item to launch valueLogViewer.
    from subprocess import Popen
    from sys import platform
    from cockpit.util import valueLogger
    from cockpit.util import csv_plotter
    menu.Append(menuId, "Launch ValueLogViewer")
    logs = valueLogger.ValueLogger.getLogFiles()
    if not logs:
        menu.Enable(menuId, False)
    else:
        shell = platform == 'win32'
        args = ['python', csv_plotter.__file__] + logs
        parent.Bind(wx.EVT_MENU,
                    lambda e: Popen(args, shell=shell),
                    id = menuId)
    menuId += 1

    menu.AppendSeparator()
    for i, window in enumerate(otherWindows):
        if not window.GetTitle() or not window.IsShown():
            # Sometimes we get bogus top-level windows; no idea why.
            # Just skip them.
            # Also, some windows are hidden rather than destroyed
            # (e.g. the experiment setup window). Skip those, too.
            # \todo Figure out where these windows come from and either get
            # rid of them or fix them so they don't cause trouble here.
            continue
        subMenu = wx.Menu()
        subMenu.Append(menuId, "Raise to top")
        parent.Bind(wx.EVT_MENU,
                    lambda e, window = window: window.Raise(), id=menuId)
        menuId += 1
        subMenu.Append(menuId, "Move to mouse")
        parent.Bind(wx.EVT_MENU,
                    lambda e, window = window: window.SetPosition(wx.GetMousePosition()), id=menuId)
        menuId += 1
        subMenu.Append(menuId, "Move to top-left corner")
        parent.Bind(wx.EVT_MENU,
                lambda e, window = window: window.SetPosition((0, 0))
                    , id=menuId)
        menuId += 1
        # Some windows have very long titles (e.g. the Macro Stage View),
        # so just take the first 50 characters.
        try:
            menu.Append(menuId, str(window.GetTitle())[:50], subMenu)
        except TypeError as e:
            # Sometimes, windows created late (e.g. wx InspectionTool) cause
            # a weird error here: menu.Append throws a type error, insisting
            # it needs a String or Unicode type, despite being passed a String
            # or Unicode type.
            print ("Omitting %s from window - weird wx string/unicode type error." % window.GetTitle())
        menuId += 1

    for d in filter(lambda x: hasattr(x, "showDebugWindow"),
                    chain(depot.getAllHandlers(), depot.getAllDevices())):
        menu.Append(menuId, 'debug  %s  %s' % (d.__class__.__name__, d.name ))
        parent.Bind(wx.EVT_MENU,
                    lambda e, d=d: d.showDebugWindow(),
                    id=menuId)
        menuId += 1

    cockpit.gui.guiUtils.placeMenuAtMouse(parent, menu)

#Function to show/hide the pythion shell window
def showHideShell(parent):
    secondaryWindows = wx.GetApp().secondaryWindows
    for window in secondaryWindows:
        if (window.GetTitle() == 'Python shell'):
            window.Show(not window.IsShown())
            cockpit.util.userConfig.setValue('windowState'+window.GetTitle()
                                             ,window.IsShown())
