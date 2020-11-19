# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RegionGrower
                                 A QGIS plugin
 Grows Regions
                              -------------------
        begin                : 2019-07-04
        git sha              : $Format:%H$
        copyright            : (C) 2019 by Greg Oakes
        email                : gro5@aber.ac.uk
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QFileInfo
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.gui import QgsMapToolEmitPoint, QgsMapTool, QgsMapCanvas,QgsMessageBar,QgsMapToolPan

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .region_grow_dialog import RegionGrowerDialog
import os.path
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QFileDialog, QApplication
from PyQt5.QtCore import Qt, pyqtSignal, QVariant
from qgis.core import *
from qgis.core import QgsMessageLog,Qgis
from qgis.core import QgsRasterLayer,QgsVectorLayer,QgsFeature
from qgis.core import QgsProject,QgsVectorFileWriter,QgsCoordinateReferenceSystem,QgsSpatialIndex
import qgis.utils
from qgis.utils import iface

import processing
import numpy as np
import osgeo
from osgeo import gdal
import math
from math import sqrt
from math import ceil
import glob
from osgeo import osr
import shutil
import sys
import math
import zipfile
import glob
import time
import json
from sys import platform

from random import randrange

def getPxlLAB(x,y,imageArray):

    listBands = [0,1,2]
    listCol = []
    for band in listBands:
        value = imageArray[x,y,band]
        print(value)
        listCol.append(value)

    return listCol

def transformToLAB(colorBand3):
    #### Using D65 White Reference ####

    xWhiteRef = 95.047
    YWhiteRef = 100
    ZWhiteRef = 108.883

    listBands = [0,1,2]
    vBand = []
    for band in listBands:
        #colour band is a np array of colour values
        colorBand = colorBand3[:,:,band]

        colorBand = np.divide(colorBand,255)

        print(colorBand.shape)

        vBand.append(np.multiply(np.where(colorBand>0.04045,np.power(np.divide(np.add(colorBand, 0.055), 1.055), 2.4),np.divide(colorBand,12.92)),100))


    #### Perform Transformation of RGB colour into XYZ Space ####

    X = np.add(np.add(np.multiply(vBand[0],0.4124),np.multiply(vBand[1], 0.3576)),np.multiply(vBand[2],0.1805))

    Y = np.add(np.add(np.multiply(vBand[0],0.2126),np.multiply(vBand[1],0.7152)),np.multiply(vBand[2],0.0722))

    Z = np.add(np.add(np.multiply(vBand[0],0.0193),np.multiply(vBand[1],0.1192)),np.multiply(vBand[2],0.9505))



    divX = np.divide(X,xWhiteRef)
    divY = np.divide(Y,YWhiteRef)
    divZ = np.divide(Z,ZWhiteRef)

    e= 0.008856
    k = 903.3

    fx = np.where(divX>e,np.cbrt(divX),((np.multiply(divX,k))+16)/116)
    fy = np.where(divY>e,np.cbrt(divY),((np.multiply(divY,k))+16)/116)
    fz= np.where(divZ>e,np.cbrt(divZ),((np.multiply(divZ,k))+16)/116)

    L = np.subtract(np.multiply(fy,116),16)

    a = np.multiply(np.subtract(fx,fy),500)

    b = np.multiply(np.subtract(fy,fz),200)

    return np.stack([L,a,b],axis = 2)


def GenerateNeighbourhood(colourImage,neighbourhood,kxy):

        if neighbourhood> kxy[1]:
            difference = neighbourhood-kxy[1]

            candiatePixels = colourImage[(kxy[1] - kxy[1]):(kxy[1] + (neighbourhood)),
                             (kxy[0] - neighbourhood):(kxy[0] + (neighbourhood)), :]

        else:

            candiatePixels = colourImage[(kxy[1]-neighbourhood):(kxy[1]+(neighbourhood)),(kxy[0]-neighbourhood):(kxy[0]+(neighbourhood)),:]


        return candiatePixels

def geoFindIndex(geoTransform,x,y):

    tX = geoTransform[0]
    ty = geoTransform[3]
    xDist = geoTransform[1]
    yDist = geoTransform[5]

    return int((x-tX)/xDist), int((y-ty)/yDist)

def indexToGeo(geoTransform,x,y):

    tX = geoTransform[0]
    ty = geoTransform[3]
    xDist = geoTransform[1]
    yDist = geoTransform[5]
    X = (tX+(x*xDist))
    Y = (ty+(y*yDist))
    
    geoLoc = (X,Y)
    
    return geoLoc

def gdalSave(refImg=None,listOutArray='',fileName='',form='GTIFF',rasterTL=None,pxlW=None,pxlH=None,espgCode=None):

    if refImg != None:

        ds = gdal.Open(refImg)
        refArray = (np.array(ds.GetRasterBand(1).ReadAsArray()))
        refImg = ds
        arrayshape = refArray.shape
        x_pixels = arrayshape[1]
        y_pixels = arrayshape[0]
        print(x_pixels, y_pixels)
        GeoT = refImg.GetGeoTransform()
        Projection = osr.SpatialReference()
        Projection.ImportFromWkt(refImg.GetProjectionRef())
        driver = gdal.GetDriverByName(form)
        numBands = len(listOutArray)
        print(numBands)
        dataset = driver.Create(fileName, x_pixels, y_pixels, numBands, gdal.GDT_Float32)
        dataset.SetGeoTransform(GeoT)
        dataset.SetProjection(Projection.ExportToWkt())
        counter = 1
        for array in listOutArray:
            dataset.GetRasterBand(counter).WriteArray(array)
            counter += 1
        dataset.FlushCache()

        ds = None
        refImg = None

    else:

        array = listOutArray[0]
        cols = array.shape[1]
        rows = array.shape[0]
        originX = rasterTL[0]
        originY = rasterTL[1]
        numBands = len(listOutArray)
        print(numBands)
        driver = gdal.GetDriverByName('GTIFF')
        outRaster = driver.Create(fileName, cols, rows, numBands, gdal.GDT_Byte)
        outRaster.SetGeoTransform((originX, pxlW, 0, originY, 0, pxlH))

        counter = 1
        for ar in listOutArray:
            outRaster.GetRasterBand(counter).WriteArray(ar)
            counter += 1

        outRasterSRS = osr.SpatialReference()
        outRasterSRS.ImportFromEPSG(int(espgCode))
        outRaster.SetProjection(outRasterSRS.ExportToWkt())
        outRaster.FlushCache()

def getUTMZone(lon, lat):
    global espgCode
    utm_band = str((math.floor((lon + 180) / 6 ) % 60) + 1)
    if len(utm_band) == 1:
        utm_band = '0'+utm_band
    if lat >= 0:
        espgCode = '326' + utm_band
    else:
        espgCode = '327' + utm_band
    return espgCode

class NewMapTool(QgsMapToolEmitPoint):

    # Define the custom signal this map tool will have
    # Always needs to be implemented as a class attributes like this
    canvasClicked = pyqtSignal(float,float)

    def __init__(self, canvas):
        QgsMapTool.__init__(self, iface.mapCanvas())


    def canvasReleaseEvent(self, event):
        point_canvas_crs = event.mapPoint()
        print(point_canvas_crs)
        iface.messageBar().pushMessage("Region Grower Plugin", "Process Starting", level=Qgis.Info,
                                       duration=2)
        # you need to specifically emit the right signal signature
        self.canvasClicked[float,float].emit(point_canvas_crs.x(),point_canvas_crs.y())


class RegionGrower:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'RegionGrower_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Region Grower')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads


    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('RegionGrower', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/region_grow/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'RegionGrow'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Region Grow'),
                action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started

        self.dlg = RegionGrowerDialog()

        # show the dialog
        self.dlg.show()

        #### The Script Starts, Now we need the mouse click operations ####

        self.dlg.nbhood.setText("25")
        self.dlg.thresh.setText("15")

        self.dlg.fileFind.clicked.connect(self.getFile)

        self.dlg.start.clicked.connect(self.start)

        self.dlg.finish.clicked.connect(self.finish)

        self.dlg.undo.clicked.connect(self.undo)

        self.dlg.shpFind.clicked.connect(self.getShp)

    def getFile(self):

        qfd =QFileDialog()
        title = 'Open File'
        path = '~/Documents/'
        f = QFileDialog.getOpenFileName(qfd,title,path)[0]
        QgsMessageLog.logMessage(f)
        print(f)
        self.dlg.fileDisplay.setText(f)
        return f

    def getShp(self):

        qfd =QFileDialog()
        title = 'Open Existing Vector Dataset'
        path = '~/Documents/'
        f = QFileDialog.getOpenFileName(qfd,title,path)[0]
        QgsMessageLog.logMessage(f)
        print(f)
        self.dlg.fileShp.setText(f)
        return f

    def setFile(self):
        qfd = QFileDialog()
        title = 'Save File'
        path = '~/Documents/'
        f = QFileDialog.getOpenFileName(qfd, title, path)[0]
        QgsMessageLog.logMessage(f)
        print(f)
        self.dlg.outVec.setText(f)
        return f

    def finish(self):

        #### Copy outVec GeoJson for ZZap ###

        global espgCode

        imageName = self.dlg.fileDisplay.text()
        saveFile = self.dlg.outVec.text()

        filename = imageName.split('/')[-1]
        outDir = imageName.replace(filename,'')

        scratchPath = imageName.replace(filename, '')
        scratch = scratchPath
        scratch = '{0}tmp/'.format(scratch)

        workspacePath = imageName.replace(filename, '')
        workspace = workspacePath
        workspace = '{0}Workspace/'.format(workspace)

        if os.path.isdir(scratch) == False:
            os.mkdir(scratch)

        #### Dialog Boxes For Reference ####

        # self.dlg.outVec.text() # User Typed File

        # self.dlg.shpExt.currentText() # Existing File

        # self.dlg.fileShp.text() # Selected File


        #### Determine if Using a new File of an Existing File is being used ####

        if self.dlg.outVec.text() != '':
            newFile = True
        else:
            newFile = False


        if newFile == True:

            if str(self.dlg.shpExt.currentText()) == 'Shapefile':

                #### Perform Dissolve based on Class ####

                digitisedLayer = outDir+saveFile+'.geojson'

                dissolvedLayer = scratch+saveFile+'_Dissolved.geojson'

                processing.run("native:dissolve",
                               {'INPUT': digitisedLayer,
                                'FIELD': ['Class'], 'OUTPUT': dissolvedLayer})

                multipartLayer = scratch+saveFile+'_Multipart.geojson'

                processing.run("native:multiparttosingleparts", {
                    'INPUT': dissolvedLayer,
                    'OUTPUT': multipartLayer})

                #### Need to Convert to Shp ####

                outputName = outDir+ saveFile+'.shp'

                outLayer = QgsVectorLayer(multipartLayer)


                QgsVectorFileWriter.writeAsVectorFormat(outLayer, outputName, "UTF-8",driverName = "ESRI Shapefile")

                print("Saved TO SHP")

            elif str(self.dlg.shpExt.currentText()) == 'GeoJSON':

                digitisedLayer = outDir+saveFile+'.geojson'

                dissolvedLayer = scratch+saveFile+'_Dissolved.geojson'

                processing.run("native:dissolve",
                               {'INPUT': digitisedLayer,
                                'FIELD': ['Class'], 'OUTPUT': dissolvedLayer})

                multipartLayer = scratch+saveFile+'_Multipart.geojson'

                processing.run("native:multiparttosingleparts", {
                    'INPUT': dissolvedLayer,
                    'OUTPUT': multipartLayer})

                with open(digitisedLayer) as r:
                    existingData = json.load(r)
                r.close()

                with open(multipartLayer) as r:
                    newData = json.load(r)
                r.close()

                newFeatures = newData.get('features')

                print(type(newFeatures))

                existingData['features'] = newFeatures

                print(type(existingData))

                with open(digitisedLayer, 'w') as k:
                    json.dump(existingData, k)
                k.close()

                outputName = digitisedLayer

        elif newFile == False:

            existingExt = str(self.dlg.fileShp.text()).split('.')[-1]

            if existingExt == 'geojson':

                outputName = str(self.dlg.fileShp.text()).split('.')[0]+'_Modified.'+existingExt

                digitisedLayer = QgsVectorLayer(str(self.dlg.fileShp.text()).split('.')[0]+'.geojson')

                dissolvedLayer = scratch+'Dissolved.geojson'

                processing.run("native:dissolve",
                               {'INPUT': digitisedLayer,
                                'FIELD': ['Class'], 'OUTPUT': dissolvedLayer})

                multipartLayer = scratch+'Multipart.geojson'

                processing.run("native:multiparttosingleparts", {
                    'INPUT': dissolvedLayer,
                    'OUTPUT': multipartLayer})

                outLayer = QgsVectorLayer(multipartLayer)

                QgsVectorFileWriter.writeAsVectorFormat(outLayer, outputName, "System", driverName="GeoJSON")

            else:

                outputName = str(self.dlg.fileShp.text()).split('.')[0] + '_Modified.' + existingExt

                if os.path.exists(str(self.dlg.fileShp.text()).split('.')[0] + '.geojson') == True:

                    digitisedLayer = QgsVectorLayer(str(self.dlg.fileShp.text()).split('.')[0] + '.geojson')

                else:

                    digitisedLayer = QgsVectorLayer(str(self.dlg.fileShp.text()).split('.')[0] + '.shp')

                dissolvedLayer = scratch + 'Dissolved.geojson'

                processing.run("native:dissolve",
                               {'INPUT': digitisedLayer,
                                'FIELD': ['Class'], 'OUTPUT': dissolvedLayer})

                multipartLayer = scratch + 'Multipart.geojson'

                processing.run("native:multiparttosingleparts", {
                    'INPUT': dissolvedLayer,
                    'OUTPUT': multipartLayer})

                outLayer = QgsVectorLayer(multipartLayer)

                QgsVectorFileWriter.writeAsVectorFormat(outLayer, outputName, "UTF-8",driverName = "ESRI Shapefile")

        if os.path.isdir(workspace) == True:
            shutil.rmtree(workspace)

        if platform == "linux" or platform == "linux2" or platform == "darwin":
            shutil.rmtree(scratch)

        layers = iface.mapCanvas().layers()
        activeLayer = iface.activeLayer()
        if activeLayer.type() == QgsMapLayer.VectorLayer:
            QgsProject.instance().removeMapLayers([activeLayer.id()])

        vLayer = QgsVectorLayer(outputName)
        values = vLayer.dataProvider().fields().indexFromName('Class')

        uniqueValues = vLayer.dataProvider().uniqueValues(values)

        categories = []
        for unique_value in uniqueValues:
            # initialize the default symbol for this geometry type
            symbol = QgsSymbol.defaultSymbol(vLayer.geometryType())

            # configure a symbol layer
            layer_style = {}
            layer_style['color'] = colourRamp[unique_value]
            layer_style['outline'] = '#000000'
            symbol_layer = QgsSimpleFillSymbolLayer.create(layer_style)

            # replace default symbol layer with the configured one
            if symbol_layer is not None:
                symbol.changeSymbolLayer(0, symbol_layer)

            # create renderer object
            category = QgsRendererCategory(unique_value, symbol, str(unique_value))
            # entry for the list of category items
            categories.append(category)

        # create renderer object
        renderer = QgsCategorizedSymbolRenderer('Class', categories)

        # assign the created renderer to the layer
        if renderer is not None:
            vLayer.setRenderer(renderer)

        vLayer.triggerRepaint()

        QgsProject.instance().addMapLayer(vLayer)

        self.dlg.start.setEnabled(True)
        self.dlg.fileDisplay.setText('')
        self.dlg.nbhood.setText('')
        self.dlg.thresh.setText('')
        self.dlg.outVec.setText('')

        iface.actionPan().trigger()

        self.dlg.close()

        # QApplication.quit()

    def undo(self):

        imageName = self.dlg.fileDisplay.text()
        saveFile = self.dlg.outVec.text()
        saveFileExt =self.dlg.fileShp.text()

        filename = imageName.split('/')[-1]

        try:

            if saveFile != '':

                outDir = imageName.replace(filename, '')

                outShp = outDir + saveFile + '.geojson'

            else:

                if str(self.dlg.fileShp.text()).split('.')[-1] == 'shp':
                    outShp = str(self.dlg.fileShp.text()).split('.')[0]+'.geojson'

            with open(outShp) as r:
                mergeData = json.load(r)
            r.close()

            currentFeatures = mergeData.get('features')

            del currentFeatures[-1]

            mergeData['features'] = currentFeatures

            with open(outShp, 'w') as k:
                json.dump(mergeData, k)
            k.close()

            layers = iface.mapCanvas().layers()
            activeLayer = iface.activeLayer()
            if activeLayer.type() == QgsMapLayer.VectorLayer:
                QgsProject.instance().removeMapLayers([activeLayer.id()])

            undoLyr = QgsVectorLayer(outShp)
            values = undoLyr.dataProvider().fields().indexFromName('Class')

            uniqueValues = undoLyr.dataProvider().uniqueValues(values)

            categories = []
            for unique_value in uniqueValues:
                # initialize the default symbol for this geometry type
                symbol = QgsSymbol.defaultSymbol(undoLyr.geometryType())

                # configure a symbol layer
                layer_style = {}
                layer_style['color'] = colourRamp[unique_value]
                layer_style['outline'] = '#000000'
                symbol_layer = QgsSimpleFillSymbolLayer.create(layer_style)

                # replace default symbol layer with the configured one
                if symbol_layer is not None:
                    symbol.changeSymbolLayer(0, symbol_layer)

                # create renderer object
                category = QgsRendererCategory(unique_value, symbol, str(unique_value))
                # entry for the list of category items
                categories.append(category)

            # create renderer object
            renderer = QgsCategorizedSymbolRenderer('Class', categories)

            # assign the created renderer to the layer
            if renderer is not None:
                undoLyr.setRenderer(renderer)

            undoLyr.triggerRepaint()

            QgsProject.instance().addMapLayer(undoLyr)

        except:

            iface.messageBar().pushMessage("Region Grower Plugin", "You Havent Created Any New Features", level=Qgis.Critical,
                                           duration=2)

    def start(self):

        self.dlg.start.setEnabled(False)
        # self.dlg.resume.setEnabled(False)

        iface.messageBar().pushMessage("Region Grower Plugin", "Preparing Datasets...", level=Qgis.Info,
                                       duration=2)

        imageName = self.dlg.fileDisplay.text()
        neighbourhood = self.dlg.nbhood.text()
        threshold = self.dlg.thresh.text()

        saveFile = self.dlg.outVec.text()

        filename = imageName.split('/')[-1]
        outDir = imageName.replace(filename,'')

        #### Generate a Colour Ramp for Classified Output Diplay ####

        global colourRamp

        colourRamp = []

        for i in range(0,256):

            colourRamp.append('%d, %d, %d' % (randrange(0, 256), randrange(0, 256), randrange(0, 256)))

        #### Get ESPGCODE for UTM ####

        rasterLyr = QgsRasterLayer(imageName,"Data")
        rasterLyr.isValid()
        crs = rasterLyr.crs().authid().split(':')[1]
        if crs.startswith('32'):

            QgsProject.instance().addMapLayer(rasterLyr)
            global espgCode
            espgCode = crs
        else:
            #### Get UTM zone ####

            src = gdal.Open(imageName)
            ulx, xres, xskew, uly, yskew, yres = src.GetGeoTransform()
            Cx = ulx + ((src.RasterXSize/2) * xres)
            Cy = uly + ((src.RasterYSize/2) * yres)
            espgCode = getUTMZone(Cx, Cy)
            src= None
            self.dlg.fileDisplay.setText(imageName.replace('.tif','_UTM.tif'))
            processing.run("gdal:warpreproject",
                           {'INPUT': rasterLyr, 'SOURCE_CRS': None,
                            'TARGET_CRS': QgsCoordinateReferenceSystem('EPSG:{0}'.format(espgCode)), 'RESAMPLING': 0, 'NODATA': None,
                            'TARGET_RESOLUTION': None, 'OPTIONS': '', 'DATA_TYPE': 0, 'TARGET_EXTENT': None,
                            'TARGET_EXTENT_CRS': None, 'MULTITHREADING': False, 'EXTRA': '',
                            'OUTPUT': imageName.replace('.tif','_UTM.tif')})
            rasterLyr = None
            imageName = imageName.replace('.tif','_UTM.tif')
            rasterLyr = QgsRasterLayer(imageName,"Data")
            QgsProject.instance().addMapLayer(rasterLyr)


        if self.dlg.outVec.text() != '':
            newFile = True
        else:
            newFile = False


        if newFile==False:

            resVecF = self.dlg.fileShp.text()

            resVec = QgsVectorLayer(resVecF)

            values = resVec.dataProvider().fields().indexFromName('Class')

            uniqueValues = resVec.dataProvider().uniqueValues(values)

            categories = []
            for unique_value in uniqueValues:
                # initialize the default symbol for this geometry type
                symbol = QgsSymbol.defaultSymbol(resVec.geometryType())

                # configure a symbol layer
                layer_style = {}
                layer_style['color'] = colourRamp[unique_value]
                layer_style['outline'] = '#000000'
                symbol_layer = QgsSimpleFillSymbolLayer.create(layer_style)

                # replace default symbol layer with the configured one
                if symbol_layer is not None:
                    symbol.changeSymbolLayer(0, symbol_layer)

                # create renderer object
                category = QgsRendererCategory(unique_value, symbol, str(unique_value))
                # entry for the list of category items
                categories.append(category)

            # create renderer object
            renderer = QgsCategorizedSymbolRenderer('Class', categories)

            # assign the created renderer to the layer
            if renderer is not None:
                resVec.setRenderer(renderer)

            resVec.triggerRepaint()

            QgsProject.instance().addMapLayer(resVec)

        #### One time convert the image from 3 band rgb to 3band lab ####

        filename = imageName.split('/')[-1]
        workspacePath = imageName.replace(filename, '')
        workspace = workspacePath
        workspace = '{0}Workspace/'.format(workspace)

        if os.path.isdir(workspace) == False:

            os.mkdir(workspace)

        labFileName = '{0}{1}'.format(workspace,filename.replace('.tif','_LAB.tif'))

        bands =[]
        for x in range(1, 4):
            ds = gdal.Open(imageName)
            bandArray = np.array(ds.GetRasterBand(x).ReadAsArray())
            bands.append(bandArray)
            ds = None

        color_image = np.stack(bands, axis=2)
        color_image = transformToLAB(color_image)

        listOutArrays=[color_image[:, :, 0],color_image[:, :, 1],color_image[:, :, 2]]

        gdalSave(refImg=imageName,listOutArray=listOutArrays,fileName=labFileName,form='GTIFF',rasterTL=None,pxlW=None,pxlH=None,espgCode=None)

        self.point_tool = NewMapTool(iface.mapCanvas())
        iface.mapCanvas().setMapTool(self.point_tool)

        self.point_tool.canvasClicked[float,float].connect(self.getPointsandDigitise)

    def getPointsandDigitise(self,x,y):

        global colourRamp
        global espgCode

        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()

        time.sleep(0.1)

        vals = (x,y)

        imageName = self.dlg.fileDisplay.text()

        filename = imageName.split('/')[-1]
        workspacePath = imageName.replace(filename, '')
        workspace = workspacePath
        workspace = '{0}Workspace/'.format(workspace)
        outDir = imageName.replace(filename, '')
        imageName=imageName.replace('.tif','_LAB.tif')


        neighbourhood = int(self.dlg.nbhood.text())
        threshold = int(self.dlg.thresh.text())

        if self.dlg.outVec.text() != '':
            newFile = True
        else:
            newFile = False


        if newFile == True:

            saveFile = self.dlg.outVec.text()
            saveFile = outDir + saveFile

            if os.path.exists(saveFile+'.geojson') != True:


                temp = QgsVectorLayer("polygon?crs=epsg:{0}".format(espgCode), "Data", "memory")
                QgsVectorFileWriter.writeAsVectorFormat(temp, saveFile, 'System',
                                                                   QgsCoordinateReferenceSystem(espgCode), 'GeoJSON',
                                                                   bool(True))

                temp = None

                outVec = saveFile + '.geojson'
            else:
                outVec = outDir + self.dlg.outVec.text()+'.geojson'

        elif newFile == False:

            saveFile = self.dlg.fileShp.text()

            #### Perform Check to see if file is GeoJSON ####

            if saveFile.split('.')[-1] == 'shp':
                #### Create GeoJSON file for processing ####

                outVec = saveFile.replace('shp','geojson')

                if os.path.exists(outVec) != True:

                    print(outVec)

                    readlayer = self.dlg.fileShp.text()

                    outLayer = QgsVectorLayer(readlayer)

                    print(outLayer)

                    for feature in outLayer.getFeatures():
                        print(feature)

                    QgsVectorFileWriter.writeAsVectorFormat(outLayer, outVec, 'UTF-8',
                                                            QgsCoordinateReferenceSystem(espgCode), 'GeoJSON')

            else:

                outVec = self.dlg.fileShp.text()

            print("Resuming")

        filename = imageName.split('/')[-1]

        scratchPath = imageName.replace(filename, '')
        workspacePath = imageName.replace(filename, '')
        workspace = workspacePath
        workspace = '{0}Workspace/'.format(workspace)

        imageName = workspace + filename

        if os.path.isdir(workspace) == False:
            os.mkdir(workspace)

        scratch = scratchPath
        scratch = '{0}tmp/'.format(scratch)

        if os.path.isdir(scratch) == False:

            os.mkdir(scratch)

        kxyMap = vals
        file = imageName

        src = gdal.Open(file)
        geoTrans = src.GetGeoTransform()

        kxy = geoFindIndex(geoTrans, kxyMap[0], kxyMap[1])

        pxlNeighbourhood = int(neighbourhood / geoTrans[1])
        if pxlNeighbourhood > kxy[1]:
            print("Will Fall Edge..")
            for i in range(1, neighbourhood + 1):
                value = int(i / geoTrans[1])
                if value < kxy[1]:
                    pxlNeighbourhood = value

        originTop = (kxy[1] - pxlNeighbourhood)

        originLeft = kxy[0] - pxlNeighbourhood
        rasterorigin = indexToGeo(geoTrans, originLeft, originTop)
        src = None

        bands = []

        for x in range(1, 4):
            ds = gdal.Open(file)
            bandArray = np.array(ds.GetRasterBand(x).ReadAsArray())
            bands.append(bandArray)
            ds = None

        color_image = np.stack(bands, axis=2)

        candiatePixels = GenerateNeighbourhood(color_image, pxlNeighbourhood, kxy)

        candiatePixelsLen = len(candiatePixels[0])
        spatialCentre = candiatePixelsLen / 2

        #### There is now a centroid pixel kxy and a neghbourhood of pixels around the centroid from whcih candiates will be selected ####

        #### There will now be a spatial and spectral distance calculation made and a total distance calculation found ####

        #### plot k centroid in 3 dimensional colour space ####

        kCentroidColour = getPxlLAB(kxy[1], kxy[0], color_image)

        print('Centroid Colour',kCentroidColour)

        spatialDist = np.empty_like(candiatePixels)[:, :, 0]

        spatialDist = np.indices(spatialDist.shape)
        coGrid = np.stack(spatialDist)
        yCo = coGrid[0, :, :]
        xCo = coGrid[1, :, :]
        var1 = np.subtract(spatialCentre, xCo)
        var2 = np.subtract(spatialCentre, yCo)
        power1 = np.power(var1, 2)
        power2 = np.power(var2, 2)
        length = np.add(power1, power2)
        spatialDist = np.sqrt(length)
        spatialDist = np.sqrt(spatialDist)


        var1 = np.subtract(kCentroidColour[0], candiatePixels[:, :, 0])
        var2 = np.subtract(kCentroidColour[1], candiatePixels[:, :, 1])
        var3 = np.subtract(kCentroidColour[2], candiatePixels[:, :, 2])
        power1 = np.power(var1, 2)
        power2 = np.power(var2, 2)
        power3 = np.power(var3, 2)
        length = np.add(power1, np.add(power2, power3))
        colorDist = np.sqrt(length)

        totalDistanceGrid = np.add(spatialDist, colorDist)

        binaryGrid = np.where(totalDistanceGrid > threshold, np.nan, 1)

        outRast = '{0}TempRast.tif'.format(scratch)
        tmpVec = '{0}TempVec.geojson'.format(scratch)

        src = gdal.Open(file)
        geoTrans = src.GetGeoTransform()
        rtnX = geoTrans[1]
        rtnY = geoTrans[5]
        src = None

        gdalSave(refImg=None, listOutArray=[binaryGrid], fileName=outRast, form='GTIFF', rasterTL=rasterorigin, pxlW=rtnX, pxlH=rtnY, espgCode=espgCode)

        rastLayer = QgsRasterLayer(outRast)

        provider = rastLayer.dataProvider()

        provider.setNoDataValue(1, 0)

        rastLayer.triggerRepaint()

        xmin = vals[0] - 1
        xmax = vals[0] + 1

        ymin = vals[1] - 1
        ymax = vals[1] + 1

        tL = QgsPointXY(xmin, ymin)
        bR = QgsPointXY(xmax, ymax)

        rec = QgsRectangle(tL, bR)

        processing.run("gdal:polygonize", {'INPUT': rastLayer, 'BAND': 1, 'FIELD': 'DN', 'EIGHT_CONNECTEDNESS': False,
                                           'OUTPUT': tmpVec})

        processingVec = tmpVec

        processingVecInt = tmpVec.replace('.geojson', '_int.geojson')

        layer = QgsVectorLayer(tmpVec, "tmp Layer", 'ogr')

        with edit(layer):
            # build a request to filter the features based on an attribute
            request = QgsFeatureRequest().setFilterExpression('"DN" != 1')

            # # we don't need attributes or geometry, skip them to minimize overhead.
            # # these lines are not strictly required but improve performance
            request.setSubsetOfAttributes([])
            request.setFlags(QgsFeatureRequest.NoGeometry)

            for f in layer.getFeatures(request):
                layer.deleteFeature(f.id())

        provider = layer.dataProvider()

        spIndex = QgsSpatialIndex()
        feat = QgsFeature()
        fit = provider.getFeatures()

        while fit.nextFeature(feat):
            spIndex.insertFeature(feat)

        pt = QgsPointXY(vals[0], vals[1])

        nearestIds = spIndex.intersects(rec)

        featureId = nearestIds[0]
        fit2 = layer.getFeatures(QgsFeatureRequest().setFilterFid(featureId))

        ftr = QgsFeature()


        layer.select(featureId)


        QgsVectorFileWriter.writeAsVectorFormat(layer, processingVecInt, 'System',
                                                QgsCoordinateReferenceSystem(espgCode),
                                                'GeoJSON', bool(True))


        tLayer = QgsVectorLayer(processingVecInt)
        processingVecIntBuff = processingVecInt.replace('.geojson', '_Buff.geojson')


        try:
            bufferDistance = float(self.dlg.bufferDistance.text())
        except:
            bufferDistance = 0


        if self.dlg.trainingData.isChecked() == True:
            processing.run("native:buffer",
                           {'INPUT': tLayer, 'DISTANCE': bufferDistance,
                            'SEGMENTS': 5, 'END_CAP_STYLE': 0, 'JOIN_STYLE': 0, 'MITER_LIMIT': 2, 'DISSOLVE': True,
                            'OUTPUT': processingVecIntBuff})
        else:
            processing.run("native:buffer",
                           {'INPUT': tLayer, 'DISTANCE': -0.05,
                            'SEGMENTS': 5, 'END_CAP_STYLE': 0, 'JOIN_STYLE': 0, 'MITER_LIMIT': 2, 'DISSOLVE': True,
                            'OUTPUT': processingVecIntBuff})

        #### Fill Holes pxlSize*4 ####

        holeAreaSize = rtnX*4
        processingVecIntBuffFill=processingVecIntBuff.replace('.geojson','_FillHoles.geojson')

        processing.run("native:deleteholes",
                       {'INPUT': processingVecIntBuff, 'MIN_AREA': holeAreaSize,
                        'OUTPUT': processingVecIntBuffFill})

        processingVecIntBuffFillFix = processingVecIntBuff.replace('.geojson', '_Fix.geojson')

        processing.run("native:fixgeometries",
                       {'INPUT': processingVecIntBuffFill,
                        'OUTPUT': processingVecIntBuffFillFix})

        with open(processingVecIntBuffFillFix) as f:
            buffData = json.load(f)
        f.close()

        featuresToMerge = buffData.get('features')

        featuresToMerge[0]['properties']['Class'] = int(self.dlg.classValue.text())
        featuresToMerge[0]['properties'].pop('DN')

        with open(outVec) as r:
            mergeData = json.load(r)
        r.close()

        currentFeatures = mergeData.get('features')


        if len(currentFeatures) == 0:
            mergeData['features'] = featuresToMerge
        else:
            newFeaturesList = currentFeatures+featuresToMerge
            mergeData['features'] = newFeaturesList

        with open(outVec, 'w') as k:
            json.dump(mergeData, k)
        k.close()

        layer = None


        layers = iface.mapCanvas().layers()
        activeLayer = iface.activeLayer()
        if activeLayer.type() == QgsMapLayer.VectorLayer:
            QgsProject.instance().removeMapLayers([activeLayer.id()])

        vLayer = QgsVectorLayer(outVec)
        values = vLayer.dataProvider().fields().indexFromName('Class')

        uniqueValues = vLayer.dataProvider().uniqueValues(values)

        categories = []
        for unique_value in uniqueValues:
            symbol = QgsSymbol.defaultSymbol(vLayer.geometryType())
            layer_style = {}
            layer_style['color'] = colourRamp[unique_value]
            layer_style['outline'] = '#000000'
            symbol_layer = QgsSimpleFillSymbolLayer.create(layer_style)
            if symbol_layer is not None:
                symbol.changeSymbolLayer(0, symbol_layer)

            category = QgsRendererCategory(unique_value, symbol, str(unique_value))
            categories.append(category)

        renderer = QgsCategorizedSymbolRenderer('Class', categories)
        if renderer is not None:
            vLayer.setRenderer(renderer)
        vLayer.triggerRepaint()
        QgsProject.instance().addMapLayer(vLayer)
        if platform == "linux" or platform == "linux2" or platform == "darwin":
            shutil.rmtree(scratch)

        QApplication.restoreOverrideCursor()
        QApplication.processEvents()

        iface.messageBar().pushMessage("Region Grower Plugin", "Process Successful", level=Qgis.Success,
                                       duration=1)

        iface.mapCanvas().setMapTool(self.point_tool)
