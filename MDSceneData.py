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


from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import (QObject, pyqtSignal)


class MDSession(QObject):
    def __init__(self, name="Untitled", scenes=None):
        super(MDSession, self).__init__()
        self.name = name
        self.scenes = [MDScene()] if scenes is None else scenes

    @classmethod
    def createFromJSON(cls, js):
        scenes = []
        for scene in js["scenes"]:
            scenes.append(MDScene.createFromJSON(scene))
        return cls(js["name"], scenes)

    def getName(self):
        return self.name

    def setName(self, name):
        self.name = name

    def addScene(self, scene):
        self.scenes.append(scene)

    def getScenes(self):
        return self.scenes

    def getScene(self, index):
        return self.scenes[index]

    def getJSON(self):
        sceneJS = []
        for scene in self.scenes:
            sceneJS.append(scene.getJSON())

        return {
            "name": self.name,
            "scenes": sceneJS
        }


class MDScene(QObject):
    sceneUpdated = pyqtSignal()

    def __init__(self, name="My Scene", so=None):
        super(MDScene, self).__init__()
        self.name = name
        if so is None:
            self.sceneObjects = {"images": [],
                                 "darkness": [],
                                 "light": []}
        else:
            self.sceneObjects = so

    @classmethod
    def createFromJSON(cls, js):
        typeDict = {"images": SceneImage,
                    "darkness": SceneDarkness,
                    "light": SceneLightCircle}
        sos = {}
        soJS = js["sceneObjects"]
        for type in soJS:
            if type in typeDict:
                typeClass = typeDict[type]
                typeList = []
                for so in soJS[type]:
                    typeList.append(typeClass.createFromJSON(so))
                sos[type] = typeList

        return cls(js["name"], sos)

    def addSceneObject(self, so):
        if isinstance(so, SceneImage):
            self.sceneObjects["images"].append(so)
        elif isinstance(so, SceneDarkness):
            self.sceneObjects["darkness"].append(so)
        elif isinstance(so, SceneLightCircle):
            self.sceneObjects["light"].append(so)

    def setName(self, name):
        self.name = name
        self.sceneUpdated.emit()

    def getSceneObjects(self):
        return self.sceneObjects

    def getSceneObject(self, type, index):
        return self.sceneObjects[type][index]

    def getName(self):
        return self.name

    def getJSON(self):
        soJS = {}
        for key in self.sceneObjects:
            elemArr = []
            for so in self.sceneObjects[key]:
                elemArr.append(so.getJSON())
            soJS[key] = elemArr
        return {
            "name": self.name,
            "sceneObjects": soJS
        }


class MDSceneObject(QObject):
    objectUpdated = pyqtSignal()

    def __init__(self, name="", x=0, y=0, width=-1, height=-1, hidden=False):
        super(MDSceneObject, self).__init__()
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.hidden = hidden

    def getName(self):
        return self.name

    def getX(self):
        return self.x

    def getY(self):
        return self.y

    def getPos(self):
        return (self.x, self.y)

    def getDimensions(self):
        return (self.x, self.y, self.width, self.height)

    def setName(self, name):
        self.objectUpdated.emit()
        self.name = name

    def setPos(self, x, y):
        self.x = x
        self.y = y
        self.objectUpdated.emit()

    def setHeight(self, height):
        self.height = height
        self.objectUpdated.emit()

    def setWidth(self, width):
        self.width = width
        self.objectUpdated.emit()

    def setDimensions(self, x, y, width, height):
        self.x = x
        self.y = y
        self.height = height,
        self.width = width
        self.objectUpdated.emit()

    def isHidden(self):
        return self.hidden

    def toggleHidden(self):
        self.hidden = not self.hidden
        self.objectUpdated.emit()

    def setHidden(self, hidden):
        self.hidden = hidden
        self.objectUpdated.emit()


class SceneImage(MDSceneObject):
    def __init__(self, name="", filepath="",
                 x=0, y=0, height=-1, width=-1, hidden=False):
        super(SceneImage, self).__init__(name, x, y, height, width, hidden)
        self.filePath = filepath
        if len(filepath) > 0:
            self.image = QPixmap(filepath)
            self.height = height if height != -1 else self.image.height()
            self.width = width if width != -1 else self.image.width()
        else:
            self.height = height
            self.width = width

    @classmethod
    def createFromJSON(cls, js):
        return cls(js["name"], js["filepath"], js["x"], js["y"],
                   js["height"], js["width"])

    def getImage(self):
        return self.image

    @classmethod
    def copySceneImage(cls, model):
        modelCopy = None
        if isinstance(SceneImage, model):
            dim = model.getDimensions()
            modelCopy = cls(model.getName(), model.getFilepath(),
                            dim[0], dim[1], dim[2], dim[3])
        return modelCopy

    def getJSON(self):
        return {
            "type": "image",
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "hidden": self.hidden,
            "filepath": self.filePath
        }


class SceneDarkness(MDSceneObject):
    def __init__(self, name="", x=0, y=0, width=-1, height=-1, hidden=False):
        super(SceneDarkness, self).__init__(name, x, y, width, height, hidden)

    @classmethod
    def createFromJSON(cls, js):
        return cls(js["name"], js["x"], js["y"],
                   js["width"], js["height"])

    def getJSON(self):
        return {
            "type": "darkness",
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "hidden": self.hidden
        }


class SceneLightCircle(MDSceneObject):
    def __init__(self, name="", x=0, y=0,
                 brightRadius=-1, dimRadius=-1, hidden=False):
        totalSize = (brightRadius + dimRadius) * 2
        super(SceneLightCircle, self).__init__(
            name, x, y, totalSize, totalSize, hidden)
        self.brightRadius = brightRadius
        self.dimRadius = dimRadius

    @classmethod
    def createFromJSON(cls, js):
        return cls(js["name"], js["x"], js["y"],
                   js["brightRadius"], js["dimRadius"])

    def getBrightRadius(self):
        return self.brightRadius

    def getDimRadus(self):
        return self.dimRadius

    def updateRadiusHW(self):
        totalSize = (self.brightRadius + self.dimRadius) * 2
        self.height = totalSize
        self.width = totalSize
        self.objectUpdated.emit()

    def setBrightRadius(self, br):
        self.brightRadius = br
        self.updateRadiusHW()

    def setDimRadius(self, dr):
        self.dimRadius = dr
        self.updateRadiusHW()

    def getJSON(self):
        return {
            "type": "light",
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "dimRadius": self.dimRadius,
            "brightRadius": self.brightRadius,
            "hidden": self.hidden
        }
