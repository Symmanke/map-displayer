"""
Map Displayer is a scene-based toolset for displaying Encounter Maps on a
second screen for Tabletop RPGs
Copyright 2019, 2020 Eric Symmank

This file is part of Map Displayer.

Map Displayer is free software: you can redistribute it
and/or modify it under the terms of the GNU General Public License as
published by the Free Software Foundation, either version 3 of the License,
or (at your option) any later version.

Map Displayer is distributed in the hope that it will be
useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Map Displayer.
If not, see <https://www.gnu.org/licenses/>.
"""

from PyQt5.QtWidgets import (QApplication, QWidget, QListWidget, QGridLayout,
                             QPushButton, QLineEdit, QFileDialog, QLabel,
                             QListWidgetItem, QVBoxLayout, QHBoxLayout,
                             QScrollArea, QComboBox, QSpinBox, QStackedWidget,
                             QDialog, QMainWindow, QAction)
from PyQt5.QtGui import (QPixmap, QPainter, QPalette,
                         QImage, QPen, QBrush, QColor)
from PyQt5 import QtCore
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
import json
import sys
import os

from MDSceneData import (MDSession, SceneDarkness, SceneImage, MDScene,
                         SceneLightCircle)


class CommonValues:
    intervalTime = 25
    DisplayHeight = 1080
    DisplayWidth = 1920
    PPI = 72
    SceneObjectTypes = ("Images", "Darkness", "Light")
    SceneObjectTypeImage = "Images"
    SceneObjectTypeDark = "Darkness"
    SceneObjectTypeLight = "Light"


class MDMain(QMainWindow):
    def __init__(self, session=None):
        super(MDMain, self).__init__()

        menuBar = self.menuBar()

        newAction = QAction("New", self)
        openAction = QAction("Open", self)
        openAction.triggered.connect(self.openSession)
        saveAction = QAction("Save", self)
        saveAction.triggered.connect(self.saveAsSession)
        saveAsAction = QAction("Save As", self)
        saveAsAction.triggered.connect(self.saveAsSession)
        importSceneAction = QAction("Import", self)

        self.statusBar()

        fileMenu = menuBar.addMenu("File")
        fileMenu.addAction(newAction)
        fileMenu.addAction(openAction)
        fileMenu.addAction(saveAction)
        fileMenu.addAction(saveAsAction)
        fileMenu.addAction(importSceneAction)
        menuBar.setNativeMenuBar(False)

        self.mapWindow = None
        self.session = MDSession() if session is None else session
        self.sceneEditor = MDSceneEditor(self.session.getScene(0))
        self.sceneList = MDSceneList()
        self.sceneList.updateList(self.session.getScenes())
        self.sceneList.addingScene.connect(self.addSceneToSession)
        self.sceneList.currentSceneUpdated.connect(self.updateCurrentScene)
        self.imageList = MDImageObjectList()
        self.imageList.imageSelected.connect(self.addImageToScene)

        displayButtons = QWidget()
        buttonLayout = QHBoxLayout()
        self.displayCurrentScene = QPushButton("Display Scene")
        self.displayCurrentScene.clicked.connect(self.displayScene)
        self.transitionCurrentScene = QPushButton("Transition Scene")
        self.transitionCurrentScene.clicked.connect(self.transitionScene)
        self.hideCurrentScene = QPushButton("Hide Scene")
        self.hideCurrentScene.clicked.connect(self.hideScene)
        buttonLayout.addWidget(self.hideCurrentScene)
        buttonLayout.addWidget(self.displayCurrentScene)
        buttonLayout.addWidget(self.transitionCurrentScene)
        displayButtons.setLayout(buttonLayout)

        layout = QGridLayout()
        layout.addWidget(self.sceneEditor, 0, 0, 2, 1)
        layout.addWidget(self.sceneList, 0, 1)
        layout.addWidget(self.imageList, 1, 1)
        layout.addWidget(displayButtons, 2, 0, 1, 2)

        centralWidget = QWidget()
        centralWidget.setLayout(layout)
        self.setCentralWidget(centralWidget)
        self.setWindowTitle("New Session")

        self.keyBindings = {
            Qt.Key_S | Qt.ControlModifier: (self.saveAsSession,),
            Qt.Key_S | Qt.ControlModifier | Qt.ShiftModifier:
            (self.saveAsSession,),
            Qt.Key_O | Qt.ControlModifier: (self.openSession,),
        }

    def keyPressEvent(self, event):
        key = event.key() | int(event.modifiers())
        if key in self.keyBindings:
            command = self.keyBindings[key]
            if len(command) == 1:
                command[0]()
            else:
                command[0](command[1])

    def updateCurrentScene(self, index):
        cs = self.session.getScene(index)
        self.sceneEditor.setCurrentScene(cs)

    def addSceneToSession(self, sceneName):
        newScene = MDScene(sceneName)
        self.session.addScene(newScene)
        self.sceneEditor.setCurrentScene(newScene)
        self.sceneList.updateList(self.session.getScenes(), 0)

    def addImageToScene(self, index):
        si = self.imageList.getSceneImage(index)
        self.sceneEditor.addtoScene(si)

    def switchImage(self):
        cr = self.imageList.currentRow()
        if cr >= 0:
            img = self.images[cr][1]
            self.mapWindow.setImage(img, MDTween(1, 0, 1000))

    def setImage(self):
        pathToOpen = QFileDialog.getOpenFileName(self, 'Open File',
                                                 '', "Image (*.png)")
        if pathToOpen is not None and pathToOpen[0]:
            img = QPixmap(pathToOpen[0])
            # self.mapWindow.setImage(img)
            self.images.append((pathToOpen[0], img))
            self.updateUI()

    def updateUI(self):
        self.imageList.clear()
        for img in self.images:
            self.imageList.addItem(QListWidgetItem(img.getName()))

    def displayScene(self):
        if self.mapWindow is None:
            self.mapWindow = MapWindow()
            self.mapWindow.show()

        cs = self.sceneEditor.getCurrentScene()

        if cs is not None:
            # Generate image
            csImage = self.generateSceneImage(cs)
            self.mapWindow.updateScene(csImage)

    def transitionScene(self):
        if self.mapWindow is None:
            self.mapWindow = MapWindow()
            self.mapWindow.show()

        cs = self.sceneEditor.getCurrentScene()

        if cs is not None:
            # Generate image
            csImage = self.generateSceneImage(cs)
            self.mapWindow.transitionScene(csImage)

    def hideScene(self):
        if self.mapWindow is None:
            self.mapWindow = MapWindow()
            self.mapWindow.show()
        self.mapWindow.hideScene()

    def generateSceneImage(self, cs):
        sceneImg = QPixmap(CommonValues.DisplayWidth,
                           CommonValues.DisplayHeight)
        sceneImg.fill(Qt.transparent)
        imgFog = QImage(CommonValues.DisplayWidth, CommonValues.DisplayHeight,
                        QImage.Format_ARGB32)
        imgFog.fill(Qt.transparent)
        fogPainter = QPainter(imgFog)
        painter = QPainter(sceneImg)
        curSOS = cs.getSceneObjects()

        for so in curSOS["images"]:
            if not so.isHidden():
                img = so.getImage()
                d = so.getDimensions()
                if img is not None:
                    print("Drawing Image!")
                    print(d)
                    painter.drawPixmap(
                        d[0] * CommonValues.PPI,
                        d[1] * CommonValues.PPI, img)

        for so in curSOS["darkness"]:
            if not so.isHidden():
                d = so.getDimensions()
                fogPainter.setBrush(Qt.black)
                fogPainter.setPen(Qt.black)
                fogPainter.drawRect(
                    d[0] * CommonValues.PPI, d[1] * CommonValues.PPI,
                    d[2] * CommonValues.PPI, d[3] * CommonValues.PPI)

        for so in curSOS["light"]:
            if not so.isHidden():
                pass

        fogPainter.end()

        painter.drawImage(0, 0, imgFog)
        painter.end()
        return sceneImg

    def saveAsSession(self):
        filePath = QFileDialog.getSaveFileName(
            self, 'Save File', '', "Map Displayer Session (*.mds)")
        if filePath is not None:
            # self.mapEditor.setFilePath(filePath)
            session = self.session
            # Grab name from FilePath
            fp = filePath[0]
            if "/" in fp:
                fp = fp.split("/")[-1]
            if fp.endswith(".mds"):
                fp = fp[:-4]
            session.setName(fp)
            sessionJS = session.getJSON()
            self.saveJSONToFile(sessionJS, filePath[0])
            # update the string
            # self.mapEditor.markEdited(False)
            self.setWindowTitle(filePath[0])

    def openSession(self):
        pathToOpen = QFileDialog.getOpenFileName(
            self, 'Open File', '', "Map Displayer Session (*.mds)")
        if pathToOpen is not None and pathToOpen[0]:
            session = self.loadSessionFromFile(pathToOpen[0])
            if session is not None:
                self.session = session
                self.sceneEditor.setCurrentScene(self.session.getScene(0))
                self.sceneList.updateList(self.session.getScenes(), 0)
                self.setWindowTitle(pathToOpen[0])

    def saveJSONToFile(cls, jsObj,  path, ext=""):
        text = json.dumps(jsObj)
        f = open(cls.resourcePath(path+ext), "w+")
        f.write(text)
        f.close()

    def loadSessionFromFile(cls, path):
        f = open(path, "r")
        if f.mode == "r":
            contents = f.read()
            jsContents = None
            try:
                jsContents = json.loads(contents)
            except Exception:
                # using the base exception class for now
                # Send an alert that the JSON contents cannot be read
                pass
            f.close()
            if jsContents is None:
                return None

            return MDSession.createFromJSON(jsContents)
        return None

    def resourcePath(self, relative_path):
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath('.'), relative_path)


class MDTextEditWindow(QWidget):

    acceptedEdit = pyqtSignal()
    cancelledEdit = pyqtSignal()

    def __init__(self, str):
        super(MDTextEditWindow, self).__init__()
        self.nameText = QLineEdit(str)
        self.acceptBtn = QPushButton("OK")
        self.acceptBtn.clicked.connect(self.acceptEdit)
        self.cancelBtn = QPushButton("Cancel")
        self.cancelBtn.clicked.connect(self.cancelEdit)
        layout = QGridLayout()
        layout.addWidget(self.nameText, 0, 0, 1, 2)
        layout.addWidget(self.acceptBtn, 1, 0)
        layout.addWidget(self.cancelBtn, 1, 1)
        self.setLayout(layout)

    def acceptEdit(self):
        self.acceptedEdit.emit()

    def cancelEdit(self):
        self.cancelledEdit.emit()

    def getName(self):
        return self.nameText.text()


class MDSceneEditor(QWidget):
    def __init__(self, scene=None):
        self.currentScene = MDScene() if scene is None else scene
        self.currentScene.sceneUpdated.connect(self.updateUI)
        self.connectSceneObjects()

        self.selectedSO = ("", -1)
        super(MDSceneEditor, self).__init__()
        nameWidget = QWidget()
        self.nameLabel = QLabel(self.currentScene.getName())
        self.nameEditBtn = QPushButton("Edit")
        self.nameEditBtn.clicked.connect(self.openNameEdit)
        self.nameDialog = None
        self.nameEditor = None

        nameLayout = QHBoxLayout()
        nameLayout.addWidget(self.nameLabel)
        nameLayout.addWidget(self.nameEditBtn)
        nameWidget.setLayout(nameLayout)

        self.objectList = MDSceneObjectList()
        self.objectList.updateList(self.currentScene.getSceneObjects())
        self.objectList.selectedSceneObject.connect(self.updateSO)
        self.objectList.addingSceneObject.connect(self.addSONoImage)
        self.scenePreviewWindow = MapScenePreview(self.currentScene)

        self.propertyStack = QStackedWidget(self)
        self.imageProperty = MDSceneImagePropertyView()
        self.darknessProperty = MDSceneDarknessPropertyView()
        self.lightProperty = MDSceneRLightPropertyView()

        self.propertyStack.addWidget(QWidget())
        self.propertyStack.addWidget(self.imageProperty)
        self.propertyStack.addWidget(self.darknessProperty)
        self.propertyStack.addWidget(self.lightProperty)

        objectBar = QWidget()
        objectLayout = QVBoxLayout()
        objectLayout.addWidget(self.objectList)
        objectLayout.addWidget(self.propertyStack)
        objectBar.setLayout(objectLayout)

        scrollArea = QScrollArea()
        scrollArea.setWidget(self.scenePreviewWindow)
        scrollArea.setBackgroundRole(QPalette.Dark)
        scrollArea.setAlignment(Qt.AlignCenter)
        scrollArea.setMinimumWidth(int(CommonValues.DisplayWidth/2))
        scrollArea.setMinimumHeight(int(CommonValues.DisplayHeight/2))

        centerArea = QWidget()
        centerLayout = QVBoxLayout()
        centerLayout.addWidget(nameWidget)
        centerLayout.addWidget(scrollArea)
        centerArea.setLayout(centerLayout)

        layout = QHBoxLayout()
        layout.addWidget(objectBar)
        layout.addWidget(centerArea)
        self.setLayout(layout)

    def connectSceneObjects(self):
        self.currentScene.sceneUpdated.connect(self.updateUI)
        sos = self.currentScene.getSceneObjects()
        for sKey in sos:
            for so in sos[sKey]:
                so.objectUpdated.connect(self.updateUI)

    def setCurrentScene(self, cs):
        self.currentScene = cs
        self.connectSceneObjects()
        self.scenePreviewWindow.setCurrentScene(cs)
        self.updateSO(-1, -1)
        self.updateUI()

    def getCurrentScene(self):
        return self.currentScene

    def addtoScene(self, so):
        if so is not None:
            self.currentScene.addSceneObject(so)
            so.objectUpdated.connect(self.updateUI)
            self.updateUI()

    def updateUI(self):
        sos = self.currentScene.getSceneObjects()
        self.nameLabel.setText(self.currentScene.getName())
        self.objectList.updateList(sos, self.selectedSO)
        self.scenePreviewWindow.repaint()

    def updateSO(self, type, index):
        print("SO UPDATE: {}, {}".format(type, index))
        typeStr = ""
        if type > -1:
            typeStr = ("images", "darkness", "light")[type]
            self.selectedSO = (typeStr, index)
            if index > -1:
                # print(index)
                so = self.currentScene.getSceneObject(typeStr, index)
                if isinstance(so, SceneImage):
                    self.propertyStack.setCurrentIndex(1)
                    self.imageProperty.setSceneObject(so)

                elif isinstance(so, SceneDarkness):
                    self.propertyStack.setCurrentIndex(2)
                    self.darknessProperty.setSceneObject(so)
                elif isinstance(so, SceneLightCircle):
                    self.propertyStack.setCurrentIndex(3)
                    self.lightProperty.setSceneObject(so)
                self.scenePreviewWindow.setSelectedSO(so)
        else:
            self.propertyStack.setCurrentIndex(0)

    def addSONoImage(self, type):
        so = None
        if type == 0:
            so = SceneDarkness("darkness", 0, 0, 1, 1)
        else:
            so = SceneLightCircle("light", 0, 0, 6, 6)
        self.addtoScene(so)

    def openNameEdit(self):
        nameStr = self.currentScene.getName()

        self.nameDialog = QDialog()
        layout = QVBoxLayout()

        self.nameEditor = MDTextEditWindow(nameStr)
        self.nameEditor.acceptedEdit.connect(self.applyNameEdit)
        self.nameEditor.cancelledEdit.connect(self.cancelNameEdit)

        layout.addWidget(self.nameEditor)
        self.nameDialog.setLayout(layout)
        self.nameDialog.exec_()

    def applyNameEdit(self):
        self.currentScene.setName(self.nameEditor.getName())

        self.nameDialog.close()
        self.nameDialog = None
        self.nameEditor = None

    def cancelNameEdit(self):
        self.nameDialog.close()
        self.nameDialog = None
        self.nameEditor = None


class MDSceneList(QWidget):
    currentSceneUpdated = pyqtSignal(int)
    addingScene = pyqtSignal(str)

    def __init__(self):
        super(MDSceneList, self).__init__()
        self.nameDialog = None
        self.nameEditor = None

        layout = QVBoxLayout()
        self.sceneList = QListWidget()
        self.sceneList.itemClicked.connect(self.updateCurrentScene)
        self.addSceneBtn = QPushButton("Add Scene")
        self.addSceneBtn.clicked.connect(self.addScene)
        self.removeSceneBtn = QPushButton("Remove Scene")
        self.removeSceneBtn.setEnabled(False)
        layout.addWidget(QLabel("List of Scenes"))
        layout.addWidget(self.sceneList)
        layout.addWidget(self.addSceneBtn)
        layout.addWidget(self.removeSceneBtn)
        self.setLayout(layout)

    def updateList(self, list, currentRow=0, displayedScene=None):
        self.sceneList.clear()

        for scene in list:
            nameText = ""
            if scene is displayedScene:
                nameText = "(D) "
            nameText += scene.getName()
            self.sceneList.addItem(QListWidgetItem(nameText))
        self.sceneList.setCurrentRow(currentRow)

    def updateCurrentScene(self):
        self.currentSceneUpdated.emit(self.sceneList.currentRow())

    def addScene(self):
        self.nameDialog = QDialog()
        layout = QVBoxLayout()

        self.nameEditor = MDTextEditWindow("New Scene")
        self.nameEditor.acceptedEdit.connect(self.applySceneAdd)
        self.nameEditor.cancelledEdit.connect(self.cancelSceneAdd)

        layout.addWidget(self.nameEditor)
        self.nameDialog.setLayout(layout)
        self.nameDialog.exec_()

    def applySceneAdd(self):
        self.addingScene.emit(self.nameEditor.getName())
        # self.sceneObject.setName(self.nameEditor.getName())

        self.nameDialog.close()
        self.nameDialog = None
        self.nameEditor = None

    def cancelSceneAdd(self):
        self.nameDialog.close()
        self.nameDialog = None
        self.nameEditor = None


class MDSceneObjectList(QWidget):

    selectedSceneObject = pyqtSignal(int, int)
    addingSceneObject = pyqtSignal(int)

    def __init__(self):
        super(MDSceneObjectList, self).__init__()
        self.numObjects = []
        self.objectList = QListWidget()
        self.objectList.itemClicked.connect(self.updateCurrentSO)
        self.objectTypeBox = QComboBox()
        self.objectTypeBox.addItem("Darkness")
        self.objectTypeBox.addItem("Light (Radius)")
        self.addObjectBtn = QPushButton("Add Object")
        self.addObjectBtn.clicked.connect(self.createSceneObject)

        self.delObjectBtn = QPushButton("Delete Object")
        self.delObjectBtn.clicked.connect(self.deleteSelectedObject)
        self.delObjectBtn.setEnabled(False)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("List of Objects"))
        layout.addWidget(self.objectList)
        layout.addWidget(self.objectTypeBox)
        layout.addWidget(self.addObjectBtn)
        layout.addWidget(self.delObjectBtn)
        self.setLayout(layout)

    def updateList(self, list, indTup=("", -1)):
        self.objectList.clear()
        self.numObjects.clear()

        self.objectList.addItem(QListWidgetItem("-----Images-----"))
        self.addSOsToList(list["images"])
        self.objectList.addItem(QListWidgetItem("----Darkness----"))
        self.addSOsToList(list["darkness"])
        self.objectList.addItem(QListWidgetItem("------Light------"))
        self.addSOsToList(list["light"])

        self.numObjects.append(len(list["images"]))
        self.numObjects.append(len(list["darkness"]))
        self.numObjects.append(len(list["light"]))
        # print(index)
        index = -1
        ln = 1
        types = ["images", "darkness", "light"]
        type = indTup[0]
        for i in range(3):
            if types[i] == type:
                index = ln + indTup[1] + 1
                print("FOUND: {}, {}".format(indTup, index))
                break
            ln += self.numObjects[i]

        self.objectList.setCurrentRow(index)

    def addSOsToList(self, list):
        for obj in list:
            nameText = ""
            if obj.isHidden():
                nameText = "(H) "
            nameText += obj.getName()
            self.objectList.addItem(QListWidgetItem(nameText))

    def updateCurrentSO(self):
        print("Updating SO")
        cr = self.objectList.currentRow()
        emitData = (-1, -1)
        for i in range(3):
            if cr <= self.numObjects[i]:
                if cr == 0:
                    emitData = (-1, -1)
                else:
                    emitData = (i, cr-1)
                break
            cr -= (self.numObjects[i]+1)
        self.selectedSceneObject.emit(emitData[0], emitData[1])

    def createSceneObject(self):
        cr = self.objectTypeBox.currentIndex()
        self.addingSceneObject.emit(cr)

    def deleteSelectedObject(self):
        pass

    def updateUI(self):
        pass


class MDSceneObjectPropertyView(QWidget):
    def __init__(self):
        super(MDSceneObjectPropertyView, self).__init__()
        self.nameLabel = QLabel("TESTING")
        self.nameBtn = QPushButton("EDIT")
        self.nameBtn.clicked.connect(self.openNameEdit)

        self.nameWidget = QWidget()
        nameLayout = QHBoxLayout()
        nameLayout.addWidget(self.nameLabel)
        nameLayout.addWidget(self.nameBtn)
        self.nameWidget.setLayout(nameLayout)

        self.xBox = QSpinBox()
        self.xBox.valueChanged.connect(self.updateModelPosition)
        self.yBox = QSpinBox()
        self.yBox.valueChanged.connect(self.updateModelPosition)

        self.hideShowBtn = QPushButton("Hide")
        self.hideShowBtn.clicked.connect(self.toggleHidden)
        self.sceneObject = None

        self.nameDialog = None
        self.nameEditor = None

    def setSceneObject(self, so):
        self.sceneObject = so
        self.updateUI()

    def updateModelPosition(self):
        self.sceneObject.setPos(self.xBox.value(),
                                self.yBox.value())

    def updateUI(self):
        print("TODO")

    def toggleHidden(self):
        self.sceneObject.toggleHidden()
        hsText = "Show" if self.sceneObject.isHidden() else "Hide"
        self.hideShowBtn.setText(hsText)
        self.hideShowBtn.repaint()

    def openNameEdit(self):
        nameStr = self.sceneObject.getName()

        self.nameDialog = QDialog()
        layout = QVBoxLayout()

        self.nameEditor = MDTextEditWindow(nameStr)
        self.nameEditor.acceptedEdit.connect(self.applyNameEdit)
        self.nameEditor.cancelledEdit.connect(self.cancelNameEdit)

        layout.addWidget(self.nameEditor)
        self.nameDialog.setLayout(layout)
        self.nameDialog.exec_()

    def applyNameEdit(self):
        self.sceneObject.setName(self.nameEditor.getName())

        self.nameDialog.close()
        self.nameDialog = None
        self.nameEditor = None

    def cancelNameEdit(self):
        self.nameDialog.close()
        self.nameDialog = None
        self.nameEditor = None


class MDSceneImagePropertyView(MDSceneObjectPropertyView):
    def __init__(self):
        super(MDSceneImagePropertyView, self).__init__()
        self.cw = QPushButton("CW")
        self.ccw = QPushButton("CCW")

        layout = QGridLayout()
        layout.addWidget(self.nameWidget, 0, 0, 1, 2)
        layout.addWidget(QLabel("X:"), 1, 0)
        layout.addWidget(self.xBox, 1, 1)
        layout.addWidget(QLabel("Y:"), 2, 0)
        layout.addWidget(self.yBox, 2, 1)
        layout.addWidget(self.cw, 3, 0)
        layout.addWidget(self.ccw, 3, 1)
        layout.addWidget(self.hideShowBtn, 4, 0, 1, 2)
        self.setLayout(layout)

    def updateUI(self):
        p = self.sceneObject.getPos()
        self.xBox.setValue(p[0])
        self.yBox.setValue(p[1])


class MDSceneDarknessPropertyView(MDSceneObjectPropertyView):
    def __init__(self):
        super(MDSceneDarknessPropertyView, self).__init__()
        self.wBox = QSpinBox()
        self.wBox.valueChanged.connect(self.updateWidth)
        self.hBox = QSpinBox()
        self.hBox.valueChanged.connect(self.updateHeight)

        layout = QGridLayout()
        layout.addWidget(self.nameWidget, 0, 0, 1, 2)
        layout.addWidget(QLabel("X:"), 1, 0)
        layout.addWidget(self.xBox, 1, 1)
        layout.addWidget(QLabel("Y:"), 2, 0)
        layout.addWidget(self.yBox, 2, 1)
        layout.addWidget(QLabel("W:"), 3, 0)
        layout.addWidget(self.wBox, 3, 1)
        layout.addWidget(QLabel("H:"), 4, 0)
        layout.addWidget(self.hBox, 4, 1)
        layout.addWidget(self.hideShowBtn, 5, 0, 1, 2)
        self.setLayout(layout)

    def updateWidth(self, w):
        self.sceneObject.setWidth(w)

    def updateHeight(self, h):
        self.sceneObject.setHeight(h)

    def updateUI(self):
        d = self.sceneObject.getDimensions()
        self.xBox.setValue(d[0])
        self.yBox.setValue(d[1])
        self.wBox.setValue(d[2])
        self.hBox.setValue(d[3])


class MDSceneRLightPropertyView(MDSceneObjectPropertyView):
    def __init__(self):
        super(MDSceneRLightPropertyView, self).__init__()
        self.brightRadius = QSpinBox()
        self.brightRadius.valueChanged.connect(self.updateBR)
        self.dimRadius = QSpinBox()
        self.dimRadius.valueChanged.connect(self.updateDR)

        layout = QGridLayout()
        layout.addWidget(self.nameLabel, 0, 0, 1, 2)
        layout.addWidget(QLabel("X:"), 1, 0)
        layout.addWidget(self.xBox, 1, 1)
        layout.addWidget(QLabel("Y:"), 2, 0)
        layout.addWidget(self.yBox, 2, 1)
        layout.addWidget(QLabel("Bright:"), 3, 0)
        layout.addWidget(self.brightRadius, 3, 1)
        layout.addWidget(QLabel("Dim:"), 4, 0)
        layout.addWidget(self.dimRadius, 4, 1)
        layout.addWidget(self.hideShowBtn, 5, 0, 1, 2)
        self.setLayout(layout)

    def updateBR(self, br):
        self.sceneObject.setBrightRadius(br)

    def updateDR(self, dr):
        self.sceneObject.setDimRadius(dr)

    def updateUI(self):
        p = self.sceneObject.getPos()
        self.xBox.setValue(p[0])
        self.yBox.setValue(p[1])
        self.brightRadius.setValue(self.sceneObject.getBrightRadius())
        self.dimRadius.setValue(self.sceneObject.getDimRadus())


class MDImageObjectList(QWidget):

    imageSelected = pyqtSignal(int)

    def __init__(self):
        super(MDImageObjectList, self).__init__()
        self.imageList = QListWidget()
        siBtn = QPushButton("Upload Image")
        siBtn.pressed.connect(self.setImage)
        selImgBtn = QPushButton("Add Image to Scene")
        selImgBtn.pressed.connect(self.addImageToScene)
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Images:"))
        layout.addWidget(self.imageList)
        layout.addWidget(siBtn)
        layout.addWidget(selImgBtn)
        self.setLayout(layout)
        self.mapWindow = None
        self.images = []

    def addImageToScene(self):
        self.imageSelected.emit(self.imageList.currentRow())

    def setImage(self):
        pathToOpen = QFileDialog.getOpenFileName(self, 'Open File',
                                                 '', "Image (*.png)")
        if pathToOpen is not None and pathToOpen[0]:
            pathName = pathToOpen[0]
            if "/" in pathName:
                pathName = pathName.split("/")[-1]
            imgSO = SceneImage(pathName, pathToOpen[0])
            self.images.append(imgSO)
            self.updateUI()

    def updateUI(self):
        self.imageList.clear()
        for img in self.images:
            self.imageList.addItem(QListWidgetItem(img.getName()))

    def getSceneImage(self, index):
        if len(self.images) > index:
            return self.images[index]
        return None


class MapScenePreview(QWidget):
    def __init__(self, scene):
        super(MapScenePreview, self).__init__()
        self.currentScene = scene
        self.selectedSO = None
        self.zoom = 50
        self.setMinimumWidth(int(CommonValues.DisplayWidth/2))
        self.setMinimumHeight(int(CommonValues.DisplayHeight/2))

        # Pen for Darkness SceneObject
        self.darkUSPen = QPen()
        self.darkUSPen.setWidth(2)
        self.darkUSPen.setStyle(Qt.SolidLine)
        self.darkUSPen.setColor(QColor(110, 10, 10))

        self.darkSSPen = QPen()
        self.darkSSPen.setWidth(4)
        self.darkSSPen.setStyle(Qt.SolidLine)
        self.darkSSPen.setColor(QColor(170, 10, 10))

        self.darkUHPen = QPen()
        self.darkUHPen.setWidth(2)
        self.darkUHPen.setStyle(Qt.DotLine)
        self.darkUHPen.setColor(QColor(110, 10, 10))

        self.darkSHPen = QPen()
        self.darkSHPen.setWidth(4)
        self.darkSHPen.setStyle(Qt.DotLine)
        self.darkSHPen.setColor(QColor(170, 10, 10))

        # Pen for Dim Light
        self.dimLUSPen = QPen()
        self.dimLUSPen.setWidth(2)
        self.dimLUSPen.setStyle(Qt.SolidLine)
        self.dimLUSPen.setColor(QColor(150, 150, 12))

        self.dimLSSPen = QPen()
        self.dimLSSPen.setWidth(4)
        self.dimLSSPen.setStyle(Qt.SolidLine)
        self.dimLSSPen.setColor(QColor(200, 200, 12))

        self.dimLUHPen = QPen()
        self.dimLUHPen.setWidth(2)
        self.dimLUHPen.setStyle(Qt.DashLine)
        self.dimLUHPen.setColor(QColor(150, 150, 12))

        self.dimLSHPen = QPen()
        self.dimLSHPen.setWidth(4)
        self.dimLSHPen.setStyle(Qt.DashLine)
        self.dimLSHPen.setColor(QColor(200, 200, 12))

        # Pen for Bright Light
        self.brightLUSPen = QPen()
        self.brightLUSPen.setWidth(2)
        self.brightLUSPen.setStyle(Qt.SolidLine)
        self.brightLUSPen.setColor(QColor(60, 150, 20))

        self.brightLSSPen = QPen()
        self.brightLSSPen.setWidth(4)
        self.brightLSSPen.setStyle(Qt.SolidLine)
        self.brightLSSPen.setColor(QColor(60, 200, 20))

        self.brightLUHPen = QPen()
        self.brightLUHPen.setWidth(2)
        self.brightLUHPen.setStyle(Qt.DashLine)
        self.brightLUHPen.setColor(QColor(60, 150, 20))

        self.brightLSHPen = QPen()
        self.brightLSHPen.setWidth(4)
        self.brightLSHPen.setStyle(Qt.DashLine)
        self.brightLSHPen.setColor(QColor(60, 200, 20))

        # self.previewBkg = QPixmap("preview_tiles.png")

    def setCurrentScene(self, scene):
        self.currentScene = scene
        self.repaint()

    def setSelectedSO(self, so):
        self.selectedSO = so
        self.repaint()

    def paintEvent(self, paintEvent):
        if self.currentScene is not None:
            scale = (self.zoom/100)
            scaledStep = CommonValues.PPI * scale
            painter = QPainter(self)
            painter.setPen(Qt.black)
            painter.setBrush(Qt.black)
            # painter.drawPixmap(0, 0, self.previewBkg)
            painter.drawRect(0, 0, int(CommonValues.DisplayWidth*scale),
                             int(CommonValues.DisplayHeight*scale))
            sceneObjects = self.currentScene.getSceneObjects()
            for so in sceneObjects["images"]:
                hidden = so.isHidden()
                selected = so is self.selectedSO

                img = so.getImage()
                d = so.getDimensions()
                if hidden and selected:
                    if img is not None:
                        painter.setOpacity(0.5)
                        painter.drawPixmap(
                            int(d[0]*scaledStep), int(d[1]*scaledStep),
                            img.scaled(int(d[2]*scale), int(d[3]*scale)))
                elif not hidden:
                    if img is not None:
                        painter.drawPixmap(
                            int(d[0]*scaledStep), int(d[1]*scaledStep),
                            img.scaled(int(d[2]*scale), int(d[3]*scale)))
                if selected:
                    painter.setPen(Qt.yellow)
                    painter.setBrush(Qt.NoBrush)
                    painter.setOpacity(1)
                    painter.drawRect(
                        int(d[0]*scaledStep), int(d[1]*scaledStep),
                        int(d[2]*scale), int(d[3]*scale))

            for so in sceneObjects["darkness"]:
                hidden = so.isHidden()
                selected = so is self.selectedSO

                d = so.getDimensions()
                d = (int(d[0] * scaledStep), int(d[1] * scaledStep),
                     int(d[2] * scaledStep), int(d[3] * scaledStep))

                if selected:
                    painter.setBrush(QBrush(QColor(110, 10, 10)))
                    painter.setPen(Qt.NoPen)
                    painter.setOpacity(0.5)
                    painter.drawRect(d[0], d[1], d[2], d[3])
                    if hidden:
                        painter.setPen(self.darkSHPen)
                    else:
                        painter.setPen(self.darkSSPen)
                elif hidden:
                    painter.setPen(self.darkUHPen)
                else:
                    painter.setPen(self.darkUSPen)
                # painter.setPen(self.darkSHPen)
                painter.setBrush(Qt.NoBrush)
                painter.setOpacity(1)
                painter.drawRect(d[0], d[1], d[2], d[3])
                painter.drawLine(d[0], d[1], d[0] + d[2], d[1] + d[3])
                painter.drawLine(d[0], d[1] + d[3], d[0] + d[2], d[1])

            for so in sceneObjects["light"]:
                hidden = so.isHidden()
                selected = so is self.selectedSO

                p = so.getPos()
                br = so.getBrightRadius()
                dr = so.getDimRadus()
                brightPen = None
                dimPen = None
                if hidden:
                    dimPen = self.dimLUHPen
                    brightPen = self.brightLUHPen
                else:
                    dimPen = self.dimLUSPen
                    brightPen = self.brightLUSPen
                if br > 0:
                    painter.setBrush(Qt.NoBrush)
                    painter.setPen(brightPen)
                    painter.drawEllipse(
                        int((p[0]-br)*scaledStep), int((p[1]-br)*scaledStep),
                        int(2*br*scaledStep), int(2*br*scaledStep))
                if dr > 0:
                    dr = dr + br
                    painter.setBrush(Qt.NoBrush)
                    painter.setPen(dimPen)
                    painter.drawEllipse(
                        int((p[0]-dr)*scaledStep), int((p[1]-dr)*scaledStep),
                        int(2*dr*scaledStep), int(2*dr*scaledStep))


class MapWindow(QWidget):
    def __init__(self):
        super(MapWindow, self).__init__()
        self.setMinimumHeight(CommonValues.DisplayHeight)
        self.setMinimumWidth(CommonValues.DisplayWidth)
        self.animationList = []
        self.finalImage = None
        self.backgroundPM = QPixmap("display_bkg.png")

        # Use QTimer to allow the animation Tweens
        self.timer = QTimer()
        self.timer.timeout.connect(self.updateAnimation)
        self.timer.start(CommonValues.intervalTime)

    def hideScene(self):
        self.animationList.append((None, self.finalImage, MDTween(1, 0, 1000)))
        self.finalImage = None

    def updateScene(self, pm):
        if pm is not None:
            self.animationList.append(
                (self.finalImage, pm, MDTween(0, 1, 1000)))
            self.finalImage = pm

    def transitionScene(self, pm):
        if pm is not None:
            self.animationList.append(
                (None, self.finalImage, MDTween(1, 0, 1000)))
            self.animationList.append(
                (None, pm, MDTween(0, 1, 1000)))
            self.finalImage = pm

    def setImage(self, img, tween=None):
        if tween is None:
            tween = MDTween(1, 1, 0)
        self.animationList.append((None, img, tween))
        self.finalImage = img

    def paintEvent(self, paintEvent):
        painter = QPainter(self)
        painter.setOpacity(1)
        painter.setPen(Qt.black)
        painter.setBrush(Qt.black)
        painter.setOpacity(1)
        painter.drawPixmap(0, 0, self.backgroundPM)
        if len(self.animationList) > 0:
            anPM = self.animationList[0]
            bkgPM = anPM[0]
            if bkgPM is not None:
                painter.drawPixmap(0, 0, bkgPM)

            if anPM[1] is not None:
                painter.setOpacity(anPM[2].getCurrentValue())
                painter.drawPixmap(0, 0, anPM[1])
        elif self.finalImage is not None:
            painter.drawPixmap(0, 0, self.finalImage)

    @QtCore.pyqtSlot()
    def updateAnimation(self):
        if len(self.animationList) > 0:
            # perform tween update
            animation = self.animationList[0]
            if animation[2].completed():
                self.animationList.pop(0)
            else:
                animation[2].update(CommonValues.intervalTime)
            self.repaint()


class MDTween:
    def __init__(self, startValue, endValue, time):
        self.startValue = startValue
        self.endValue = endValue
        self.valueDelta = endValue - startValue
        self.time = time
        self.timeRemaining = time

    def update(self, delta):
        self.timeRemaining -= delta
        return self.getCurrentValue()

    def getCurrentValue(self):
        # Do a linear thing
        return self.startValue + (self.valueDelta *
                                  ((self.time - self.timeRemaining) /
                                   self.time))

    def completed(self):
        return self.timeRemaining <= 0


app = QApplication([])
mainWindow = MDMain()
# previewWindow = QWidget()

mainWindow.show()
# previewWindow.show()

app.exec_()
