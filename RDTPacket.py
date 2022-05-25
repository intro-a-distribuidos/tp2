import struct


class RDTPacket:
    seqNum = 0
    ackNum = 0

    # Flags
    ack = False
    syn = False

    #rwnd = None
    #checksum = None
    data = "".encode()

    def __init__(self, seqNum, ackNum, syn, ack, data="".encode()):
        self.seqNum = seqNum
        self.ackNum = ackNum
        self.syn = syn
        self.ack = ack
        self.data = data

    # https://stackoverflow.com/questions/3753589/packing-and-unpacking-variable-length-array-string-using-the-struct-module-in-py
    @classmethod
    def fromSerializedPacket(cls, serializedPacket):
        packet = struct.unpack("i i ? ?", serializedPacket[:10]) 
        packet = (*packet, serializedPacket[10:]) 
        return cls(*packet)

    @classmethod
    def makeSYNPacket(cls, seqNum):
        return cls(seqNum, 0, True, False)

    @classmethod
    def makeACKPacket(cls, ackNum): 
        return cls(0, ackNum, False, True)

    @classmethod
    def makeSYNACKPacket(cls, seqNum, ackNum, newServerPort):
        return cls(seqNum, ackNum, True, True, str(newServerPort).encode())

    def serialize(self):
        return struct.pack("i i ? ? {}s".format(len(self.data)), self.seqNum, self.ackNum, self.syn, self.ack, self.data)

    def isSYN(self):
        return self.syn

    def isACK(self):
        return self.ack

    def isSYNACK(self):
        return self.isSYN() and self.isACK()
