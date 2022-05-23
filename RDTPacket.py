
"""
    Esta clase es un borrador, creo que no tiene sentido crear una clase por paquete.
"""

class RDTPacket:
    seqNum = None
    ackNum = None

    #Flags
    cwr = None
    ece = None
    ack = None
    rst = None
    syn = None
    fin = None

    rwnd = None
    checksum = None

    def __init__(self, seqNum, ackNum, cwr, ece, ack, rst, syn, fin, rwnd):
    
    def checksum(self):
        
    def serialize(self):

    def deserialize(self):