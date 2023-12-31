import numpy
from _typeshed import Incomplete
from typing import ClassVar

class SurgeControlGroup:
    def __init__(self, *args, **kwargs) -> None: ...
    def getEntries(self) -> List[SurgePyControlGroupEntry]: ...
    def getId(self) -> int: ...
    def getName(self) -> str: ...

class SurgeControlGroupEntry:
    def __init__(self, *args, **kwargs) -> None: ...
    def getEntry(self) -> int: ...
    def getParams(self) -> List[SurgePyNamedParam]: ...
    def getScene(self) -> int: ...

class SurgeModRouting:
    def __init__(self, *args, **kwargs) -> None: ...
    def getDepth(self) -> float: ...
    def getDest(self) -> SurgeNamedParamId: ...
    def getNormalizedDepth(self) -> float: ...
    def getSource(self) -> SurgeModSource: ...
    def getSourceIndex(self) -> int: ...
    def getSourceScene(self) -> int: ...

class SurgeModSource:
    def __init__(self, *args, **kwargs) -> None: ...
    def getModSource(self) -> int: ...
    def getName(self) -> str: ...

class SurgeNamedParamId:
    def __init__(self, *args, **kwargs) -> None: ...
    def getId(self) -> SurgeSynthesizer_ID: ...
    def getName(self) -> str: ...

class SurgeSynthesizer:
    mpeEnabled: bool
    tuningApplicationMode: Incomplete
    def __init__(self, *args, **kwargs) -> None: ...
    def allNotesOff(self) -> None: ...
    def channelAftertouch(self, channel: int, value: int) -> None: ...
    def channelController(self, channel: int, cc: int, value: int) -> None: ...
    def createMultiBlock(self, blockCapacity: int) -> numpy.ndarray[numpy.float32]: ...
    def createSynthSideId(self, arg0: int) -> SurgeSynthesizer_ID: ...
    def fromSynthSideId(self, arg0: int, arg1: SurgeSynthesizer_ID) -> bool: ...
    def getAllModRoutings(self) -> dict: ...
    def getBlockSize(self) -> int: ...
    def getControlGroup(self, entry: int) -> SurgePyControlGroup: ...
    def getFactoryDataPath(self) -> str: ...
    def getModDepth01(self, targetParameter: SurgePyNamedParam, modulationSource: SurgePyModSource, scene: int = ..., index: int = ...) -> float: ...
    def getModSource(self, modId: int) -> SurgePyModSource: ...
    def getNumInputs(self) -> int: ...
    def getNumOutputs(self) -> int: ...
    def getOutput(self) -> numpy.ndarray[numpy.float32]: ...
    def getParamDef(self, arg0: SurgePyNamedParam) -> float: ...
    def getParamDisplay(self, arg0: SurgePyNamedParam) -> str: ...
    def getParamInfo(self, arg0: SurgePyNamedParam) -> str: ...
    def getParamMax(self, arg0: SurgePyNamedParam) -> float: ...
    def getParamMin(self, arg0: SurgePyNamedParam) -> float: ...
    def getParamVal(self, arg0: SurgePyNamedParam) -> float: ...
    def getParamValType(self, arg0: SurgePyNamedParam) -> str: ...
    def getParameterName(self, arg0: SurgeSynthesizer_ID) -> str: ...
    def getPatch(self) -> dict: ...
    def getSampleRate(self) -> float: ...
    def getUserDataPath(self) -> str: ...
    def isActiveModulation(self, targetParameter: SurgePyNamedParam, modulationSource: SurgePyModSource, scene: int = ..., index: int = ...) -> bool: ...
    def isBipolarModulation(self, modulationSource: SurgePyModSource) -> bool: ...
    def isValidModulation(self, targetParameter: SurgePyNamedParam, modulationSource: SurgePyModSource) -> bool: ...
    def loadKBMFile(self, arg0: str) -> None: ...
    def loadPatch(self, path: str) -> bool: ...
    def loadSCLFile(self, arg0: str) -> None: ...
    def pitchBend(self, channel: int, bend: int) -> None: ...
    def playNote(self, channel: int, midiNote: int, velocity: int, detune: int = ...) -> None: ...
    def polyAftertouch(self, channel: int, key: int, value: int) -> None: ...
    def process(self) -> None: ...
    def processMultiBlock(self, val: numpy.ndarray[numpy.float32], startBlock: int = ..., nBlocks: int = ...) -> None: ...
    def releaseNote(self, channel: int, midiNote: int, releaseVelocity: int = ...) -> None: ...
    def remapToStandardKeyboard(self) -> None: ...
    def retuneToStandardScale(self) -> None: ...
    def retuneToStandardTuning(self) -> None: ...
    def savePatch(self, path: str) -> None: ...
    def setModDepth01(self, targetParameter: SurgePyNamedParam, modulationSource: SurgePyModSource, depth: float, scene: int = ..., index: int = ...) -> None: ...
    def setParamVal(self, param: SurgePyNamedParam, toThis: float) -> None: ...

class SurgeSynthesizer_ID:
    def __init__(self) -> None: ...
    def getSynthSideId(self) -> int: ...

class TuningApplicationMode:
    __members__: ClassVar[dict] = ...  # read-only
    RETUNE_ALL: ClassVar[TuningApplicationMode] = ...
    RETUNE_MIDI_ONLY: ClassVar[TuningApplicationMode] = ...
    __entries: ClassVar[dict] = ...
    def __init__(self, value: int) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...
    def __index__(self) -> int: ...
    def __int__(self) -> int: ...
    def __ne__(self, other: object) -> bool: ...
    @property
    def name(self) -> str: ...
    @property
    def value(self) -> int: ...

def createSurge(sampleRate: float) -> SurgeSynthesizer: ...
def getVersion() -> str: ...
