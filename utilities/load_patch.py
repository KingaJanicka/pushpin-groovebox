import sys
import struct
import xml.dom.minidom
import json

configFile = open("../patch.json")
config = json.load(configFile)

def load_patch_xml(patch):
    with open(patch, mode='rb') as patchFile:
        patchContent = patchFile.read()

    fxpHeader = struct.unpack(">4si4siiii28si", patchContent[:60])
    (chunkmagic, byteSize, fxMagic, version, fxId, fxVersion, numPrograms, prgName, chunkSize) = fxpHeader
    # print("Header Values: {0}".format(fxpHeader))


    patchHeader = struct.unpack("<4siiiiiii", patchContent[60:92])
    xmlsize = patchHeader[1]
    # print("Patch Header Values: {0}".format(patchHeader))
    xmlct = patchContent[92:(92 + xmlsize)].decode('utf-8')

    dom = xml.dom.minidom.parseString(xmlct)
    
    state = {}
    
    for k, v in enumerate(config['patch']):
        if (k == 'meta'):
            state[k] = dom.getElementsByTagName('meta')[0].attributes.items()
        
        else:
            state[k] = []
            parent = dom.getElementsByTagName(k)[0]
            for node in parent.childNodes:
                item = node.attributes.items()
                try:
                    item['address'] = v[node.nodeName]['osc']
                except:
                    pass
                state[k].append(item)
                
    return state
                
    # pretty_xml_as_string = dom.toprettyxml()
    # print(pretty_xml_as_string)

    # osc = 0
    # scene = "A"
    # for i in patchHeader[2:]:
    #     if(i != 0):
    #         print("{0} osc{1} wt data size {2}".format(osc, scene, i))
    #     else:
    #         print("{0} osc{1} no wt".format(osc, scene))
    #     osc = osc + 1
    #     if(osc == 3):
    #         osc = 0
    #         scene = "B"