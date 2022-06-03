import struct
import math

RDT_HEADER_LENGTH = 15


class RDTPacket:
    seqNum = 0
    ackNum = 0

    # Flags
    ack = False
    syn = False
    fin = False

    #rwnd = None
    #checksum = None
    data = "".encode()

    def __init__(self, seqNum, ackNum, checksum, syn, ack, fin, data="".encode()):
        self.seqNum = seqNum
        self.ackNum = ackNum
        self.syn = syn
        self.ack = ack
        self.fin = fin
        self.data = data
        if(checksum is None):
            self.checksum = self.calculateChecksum()
        else:
            self.checksum = checksum

    # https://stackoverflow.com/questions/3753589/packing-and-unpacking-variable-length-array-string-using-the-struct-module-in-py
    @classmethod
    def fromSerializedPacket(cls, serializedPacket):
        packet = struct.unpack("i i i ? ? ? ", serializedPacket[:RDT_HEADER_LENGTH])
        packet = (*packet, serializedPacket[RDT_HEADER_LENGTH:])
        return cls(*packet)

    @classmethod
    def makeSYNPacket(cls, seqNum):
        return cls(seqNum, 0, None, True, False, False)

    @classmethod
    def makeACKPacket(cls, ackNum):
        return cls(0, ackNum, None, False, True, False)

    @classmethod
    def makeSYNACKPacket(cls, seqNum, ackNum, newServerPort):
        return cls(
            seqNum,
            ackNum,
            None,
            True,
            True,
            False,
            str(newServerPort).encode())

    @classmethod
    def makeFINPacket(cls, seqNum=0, ackNum=0):
        return cls(seqNum, ackNum, None, False, False, True)

    @classmethod
    def makeFINACKPacket(cls, seqNum=0, ackNum=0):
        return cls(seqNum, ackNum, None, False, True, True)

    def serialize(self):
        return struct.pack("i i i ? ? ?  {}s".format(len(
            self.data)), self.seqNum, self.ackNum, self.checksum, self.syn, self.ack, self.fin, self.data)

    def carryAroundAdd(self, a, b):
        c = a + b
        return (c & 0xffff) + (c >> 16)

    def calculateChecksum(self):
        checksum = 0
        serializedFields = struct.pack("i i ? ? ? {}s".format(len(
            self.data)), self.seqNum, self.ackNum, self.syn, self.ack, self.fin, self.data)

        if(len(serializedFields) % 2 != 0):  # Agrego 1 byte de padding si el numero de bytes es impar 
            serializedFields += struct.pack("B", 0) 

        if(len(serializedFields) % 2 == 0):  # Divido en numeros de 16 bits
            serializedFields = struct.unpack("%dH" % math.floor(len(serializedFields)/2), serializedFields)

        for i in range(0, len(serializedFields)):
            # Si los ultimos 16 bytes tenian padding de 1 byte, shifteo
            if(i == len(serializedFields)-1 and serializedFields[i] < 0x100):
                serializedFields[i] << 8
            w = checksum + serializedFields[i]
            checksum = self.carryAroundAdd(checksum, w)

        return checksum

    def isSYN(self):
        return self.syn

    def isACK(self):
        return self.ack and not self.fin

    def isSYNACK(self):
        return self.syn and self.ack

    def isFIN(self):
        return self.fin and not self.ack

    def isFINACK(self):
        return self.fin and self.ack
