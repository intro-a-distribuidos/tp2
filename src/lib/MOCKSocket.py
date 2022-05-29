from RDTSocketSR import RDTSocketSR
from RDTPacket import RDTPacket
import logging
import sys

MOCKIP = '8.8.8.8'
MOCKPORT = 5050
class MOCKSocket:
    def __init__(self, packets, sendLoseArray):
        self.isClosed = False
        # [RDTPacket(139, 200, ...), RDTPacket(451, 203, ...), ...]
        self.recvpackets = packets

        # Array containing the sent packets
        self.sendpackets = []

        # Array that contains if send_i should be losed
        #   [True, False, True, True]
        self.sendLoseArray = sendLoseArray
        self.iteration = 0

    def recvfrom(self, MSS):
        if(self.isClosed):
            raise RuntimeError
        if(self.recvpackets):
            return (self.recvpackets.pop(0), (MOCKIP, MOCKPORT))
        return (b'', None)
    def makeAck(self, data):
        packet = RDTPacket.fromSerializedPacket(data)
        ackPacket = RDTPacket.makeACKPacket(packet.seqNum + len(packet.data))
        return ackPacket

    def sendto(self, packet, addr):
        if(self.isClosed):
            raise RuntimeError
        if(not self.sendLoseArray[self.iteration]):
            # Ojo con enviar ACKs para ACKs!!!! ojo <<< no está implementado este check aún, HAY QUE
            self.sendpackets.append(packet)
            self.recvpackets.append(self.makeAck(packet).serialize())
        self.iteration += 1
        if(self.iteration >= len(self.sendLoseArray)):
            self.iteration = 0
        return(len(packet))
    def close(self):
        isClosed = True
    def settimeout(self, n):
        return

def simpleTest():
    logging.basicConfig(level=logging.DEBUG,  # filename="server.log",
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y/%m/%d %I:%M:%S %p',
                    stream=sys.stdout)

    packet1 = RDTPacket(30, 24, False, False, data="#1".encode()).serialize()
    packet2 = RDTPacket(32, 24, False, False, data="#2".encode()).serialize()
    packet3 = RDTPacket(36, 24, False, False, data="#4".encode()).serialize()
    packet4 = RDTPacket(34, 24, False, False, data="#3".encode()).serialize()

    packets = [packet1, packet2, packet3, packet4]
    rdtsocket = RDTSocketSR()
    rdtsocket.destIP = MOCKIP
    rdtsocket.destPort = MOCKPORT
    rdtsocket.seqNum = 50
    rdtsocket.ackNum = 30
    rdtsocket.socket = MOCKSocket(packets, [False]) # No se pierden paquetes de ida
    rdtsocket.waitForPackets()

    data1 = rdtsocket.recvSelectiveRepeat(2000)
    data2 = rdtsocket.recvSelectiveRepeat(2000)
    data3 = rdtsocket.recvSelectiveRepeat(2000)
    data4 = rdtsocket.recvSelectiveRepeat(2000)
    print(data1.decode())
    print(data2.decode())
    print(data3.decode())
    print(data4.decode())

simpleTest()