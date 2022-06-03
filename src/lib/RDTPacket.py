import struct

RDT_HEADER_LENGTH = 11


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

    def __init__(self, seqNum, ackNum, syn, ack, fin, data="".encode()):
        self.seqNum = seqNum
        self.ackNum = ackNum
        self.syn = syn
        self.ack = ack
        self.fin = fin
        self.data = data

    # https://stackoverflow.com/questions/3753589/packing-and-unpacking-variable-length-array-string-using-the-struct-module-in-py
    @classmethod
    def fromSerializedPacket(cls, serializedPacket):
        packet = struct.unpack("i i ? ? ?", serializedPacket[:RDT_HEADER_LENGTH])
        packet = (*packet, serializedPacket[RDT_HEADER_LENGTH:])
        return cls(*packet)

    @classmethod
    def makeSYNPacket(cls, seqNum):
        return cls(seqNum, 0, True, False, False)

    @classmethod
    def makeACKPacket(cls, ackNum):
        return cls(0, ackNum, False, True, False)

    @classmethod
    def makeSYNACKPacket(cls, seqNum, ackNum, newServerPort):
        return cls(
            seqNum,
            ackNum,
            True,
            True,
            False,
            str(newServerPort).encode())

    @classmethod
    def makeFINPacket(cls, seqNum=0, ackNum=0):
        return cls(seqNum, ackNum, False, False, True)

    @classmethod
    def makeFINACKPacket(cls, seqNum=0, ackNum=0):
        return cls(seqNum, ackNum, False, True, True)

    def serialize(self):
        return struct.pack("i i ? ? ? {}s".format(len(
            self.data)), self.seqNum, self.ackNum, self.syn, self.ack, self.fin, self.data)

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
