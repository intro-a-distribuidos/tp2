import time
import logging
import random

from lib.exceptions import LostConnection, TimeOutException, ServerUnreachable
from threading import Lock, Thread, Timer
from socket import socket, AF_INET, SOCK_DGRAM, SHUT_RD, timeout
from lib.RDTPacket import RDTPacket, RDT_HEADER_LENGTH
from sys import getsizeof


MSS = 1500
WINDOWSIZE = 2
INPUT_BUFFER_SIZE = 4  # UDP buffer size = 65535, 44 MSS
RESEND_TIME = 0.5
NRETRIES = 20  # see doc


class RDTSocketSR:
    ##############################
    #         COMMON API         #
    ##############################
    def __init__(self):
        # https://stackoverflow.com/questions/1365265/on-localhost-how-do-i-pick-a-free-port-number
        self.srcIP = ''  # Default source addr
        self.srcPort = 0  # Default source port
        self.destIP = None
        self.destPort = None

        self.socket = socket(AF_INET, SOCK_DGRAM)

        self.lockSequenceNumber = Lock()
        self.seqNum = random.randint(0, 1000)

        self.lockAcknowledgmentNumber = Lock()
        self.ackNum = 0                          # expected next byte
        logging.debug(
            "Configuring new Socket. Initial sequence number: {}".format(
                self.seqNum))

        # Server variables
        self.lockListening = Lock()
        self.listening = False
        self.listeningThread = None

        self.lockUnacceptedConnections = Lock()
        self.unacceptedConnections = {}          # Waiting for accept socket map
        self.lockAcceptedConnections = Lock()
        self.acceptedConnections = {}            # Accepted socket map

        # Client / ServerClient variables
        self.mainSocket = None                   # None if client, parent if ServerClient

        # True if a resend tries more than NRETRIES times
        self.lockLostConnection = Lock()
        self.lostConnection = False

        self.receivingThread = None

        self.lockInputBuffer = Lock()
        self.inputBuffer = {}                    # Map where will be store the incoming packets
        self.lockOutPutWindow = Lock()
        self.outPutWindow = []                   # Window of packets sent

        self.lockReceivedFINACK = Lock()
        self.receivedFINACK = False

        self.lockRequestedClose = Lock()
        self.requestedClose = False

        self.lockClosed = Lock()
        self.closed = False

    def getSeqNum(self):
        self.lockSequenceNumber.acquire()
        v = self.seqNum
        self.lockSequenceNumber.release()
        return v
    def addToSeqNum(self, n):
        self.lockSequenceNumber.acquire()
        self.seqNum += n
        self.lockSequenceNumber.release()

    def getAckNum(self):
        self.lockAcknowledgmentNumber.acquire()
        v = self.ackNum
        self.lockAcknowledgmentNumber.release()
        return v
    def setAckNum(self, newAckNum):
        self.lockAcknowledgmentNumber.acquire()
        self.ackNum = newAckNum
        self.lockAcknowledgmentNumber.release()
    def addToAckNum(self, n):
        self.lockAcknowledgmentNumber.acquire()
        self.ackNum += n
        self.lockAcknowledgmentNumber.release()        

    def isListening(self):
        self.lockListening.acquire()
        v = self.listening
        self.lockListening.release()
        return v
    def changeFlagListening(self, newListeningValue):
        self.lockListening.acquire()
        self.listening = newListeningValue
        self.lockListening.release()

    def isLostConnection(self):
        self.lockLostConnection.acquire()
        v = self.lostConnection
        self.lockLostConnection.release()
        return v
    def changeFlagLostConnection(self, newLostConnectionValue):
        self.lockLostConnection.acquire()
        self.lostConnection = newLostConnectionValue
        self.lockLostConnection.release()

    def hasReceivedFINACK(self):
        self.lockReceivedFINACK.acquire()
        v = self.receivedFINACK
        self.lockReceivedFINACK.release()
        return v
    def changeFlagReceivedFINACK(self, newReceivedFINACKValue):
        self.lockReceivedFINACK.acquire()
        self.receivedFINACK = newReceivedFINACKValue
        self.lockReceivedFINACK.release()

    def wasRequestedClose(self):
        self.lockRequestedClose.acquire()
        v = self.requestedClose
        self.lockRequestedClose.release()
        return v
    def changeFlagRequestedClose(self, newRequestedCloseValue):
        self.lockRequestedClose.acquire()
        self.requestedClose = newRequestedCloseValue
        self.lockRequestedClose.release()

    def isClosed(self):
        self.lockClosed.acquire()
        v = self.closed
        self.lockClosed.release()
        return v
    def changeFlagClosed(self, newClosedValue):
        self.lockClosed.acquire()
        self.closed = newClosedValue
        self.lockClosed.release()

    def getExpectedInput(self):
        self.lockInputBuffer.acquire()
        v = self.inputBuffer.get(self.getAckNum())
        self.lockInputBuffer.release()
        return v

    def isOutPutWindowEmpty(self):
        self.lockOutPutWindow.acquire()
        ret = len(self.outPutWindow) == 0
        self.lockOutPutWindow.release()
        return ret

    def getDestinationAddress(self):
        return (self.destIP, self.destPort)

    def matchDestAddr(self, addr):
        return addr == (self.destIP, self.destPort)

    def matchesACK(self, packet, ackNum):
        return packet.seqNum + len(packet.data) == ackNum

    #####################################
    #         LISTEN/ACCEPT API         #
    #####################################
    """
        It's used by the server during creation of new socket for a client,
        Assigns the client address (obtained during handshake) on (destIP, destPort)
    """

    def setDestinationAddress(self, address):
        logging.debug(
            "Setting {}:{} as destination address in the new socket".format(
                *address))
        self.destIP = address[0]
        self.destPort = address[1]

    """
        It's used by the server in order to assign an specific address to the socket
    """

    def bind(self, address):
        ip, port = address
        self.srcIP = ip
        self.srcPort = port
        self.socket.bind(address)
        self.srcPort = self.socket.getsockname()[1]
        logging.debug(
            "Binding the socket to {}:{}".format(
                self.srcIP, self.srcPort))

    """
        It's used by the server.
        Create a thread where it will listen for new connections
    """

    def listen(self, maxQueuedConnections):
        self.listeningThread = Thread(target=self.listenThread,
                                      args=(maxQueuedConnections,))
        self.listeningThread.daemon = True  # Closes with the main thread
        self.changeFlagListening(True)
        self.listeningThread.start()
        logging.debug("Now server is listening...")

    """
        It's used by the server.
        If receive a SYN message, performs the 2whs with the client,
            creates a new socket and appends it to unacceptedConnections...
    """

    def listenThread(self, maxQueuedConnections):
        # TODO?: si está llena acceptedConnections deberíamos quedarnos en un while
        # esperando que se vacíe, no hacer otra cosa
        self.socket.settimeout(1)
        data, address = (None, None)

        while(self.isListening()):
            try:
                data, address = self.socket.recvfrom(MSS)
            except timeout:
                continue  # Checks while condition again
            packet = RDTPacket.fromSerializedPacket(data)

            if(packet.isSYN() and self.isNewClient(address)):
                logging.info(
                    "Requested connection from [{}:{}]".format(
                        *address))
                if(self.getAmountOfPendingConnections() >= maxQueuedConnections):
                    logging.info(
                        "Refused connection from [{}:{}] due pending connections overflow".format(
                            *address))
                    continue  # Descarto las solicitudes de conexiones TODO: enviar mensaje de rechazo

                newConnection = self.createConnection(address, packet.seqNum)

                self.lockUnacceptedConnections.acquire()
                self.unacceptedConnections[newConnection.getDestinationAddress(
                )] = newConnection
                self.lockUnacceptedConnections.release()

                synAckPacket = RDTPacket.makeSYNACKPacket(
                    newConnection.seqNum, newConnection.ackNum, newConnection.srcPort)
                self.socket.sendto(synAckPacket.serialize(), address)

                logging.debug(
                    "Sent server Sequence number: {} y ACK number {}".format(
                        newConnection.seqNum, newConnection.ackNum))

            elif(packet.isSYN() and not self.isNewClient(address)):
                logging.debug(
                    "Requested connection from [{}:{}], wich is already connected".format(
                        *address))
                newConnection = self.getClient(address)
                synAckPacket = RDTPacket.makeSYNACKPacket(
                    newConnection.seqNum, newConnection.ackNum, newConnection.srcPort)
                self.socket.sendto(synAckPacket.serialize(), address)
                logging.debug(
                    "Resending SYNACK server sequence number: {} y ACK number {}".format(
                        newConnection.seqNum, newConnection.ackNum))

    """
        It's used by the server.
        Checks if client (address) was connected previously
    """

    def isNewClient(self, address):
        self.lockUnacceptedConnections.acquire()
        unaccepted = address in self.unacceptedConnections
        self.lockUnacceptedConnections.release()

        self.lockAcceptedConnections.acquire()
        accepted = address in self.acceptedConnections
        self.lockAcceptedConnections.release()

        return not unaccepted and not accepted

    """
        It's used by the server.
        Looks for a previously established connection
    """

    def getClient(self, clientAddress):
        self.lockUnacceptedConnections.acquire()
        client = self.unacceptedConnections.get(clientAddress)
        self.lockUnacceptedConnections.release()
        if(client is None):
            self.lockAcceptedConnections.acquire()
            client = self.acceptedConnections.get(clientAddress)
            self.lockAcceptedConnections.release()

        return client

    """
        It's used by the server.
        Creates a new connection in order to handle a new client communication
    """

    def createConnection(self, clientAddress, initialAckNum):
        newConnection = RDTSocketSR()
        newConnection.bind((self.srcIP, 0))
        newConnection.socket.settimeout(2)  # 2 second timeout
        newConnection.setDestinationAddress(clientAddress)
        newConnection.ackNum = initialAckNum
        newConnection.mainSocket = self
        newConnection.waitForPackets()
        return newConnection

    def getAmountOfPendingConnections(self):
        self.lockUnacceptedConnections.acquire()
        n = len(self.unacceptedConnections)
        self.lockUnacceptedConnections.release()
        return n

    def unacceptedConnectionsIsEmpty(self):
        self.lockUnacceptedConnections.acquire()
        isEmpty = not self.unacceptedConnections
        self.lockUnacceptedConnections.release()
        return isEmpty

    """
        It's used by the server.
        Pops an unaccepted connection from 'self.unacceptedConnections' and returns it
    """

    def popUnacceptedConnection(self):
        self.lockUnacceptedConnections.acquire()
        # Obtains the first key value pair in 'unacceptedConnections'
        addr, connection = next(iter(self.unacceptedConnections.items()))
        del self.unacceptedConnections[addr]
        self.lockUnacceptedConnections.release()
        return (addr, connection)

    """
        It's used by the server
        Pops the first socket from the 'unacceptedConnections'
        If list is empty, blocks the thread until there is a socket avaiable
    """

    def accept(self):
        logging.debug("Waiting for new connections")

        while(self.unacceptedConnectionsIsEmpty()):
            # TODO: HORRIBLE!!!!!!!!
            time.sleep(0.2)

        addr, connection = self.popUnacceptedConnection()

        self.lockAcceptedConnections.acquire()
        self.acceptedConnections[addr] = connection
        self.lockAcceptedConnections.release()
        logging.info("Accepted connection {}:{}".format(*addr))
        return (connection, addr)

    ##################
    #   Client API   #
    ##################

    """
        It's used only by the Client.
        Performs the 2whs in Stop and Wait manner, it doesn't use piggyback
    """

    def connect(self, destAddr):
        self.destIP, self.destPort = destAddr

        logging.info(
            "Establishing connection with server {}:{}".format(
                *destAddr))
        self.socket.settimeout(2)  # 2 second timeout
        synAckPacket, addr = (None, None)
        receivedSYNACK = False
        tries = NRETRIES

        while(not receivedSYNACK and tries > 0):
            try:
                synPacket = RDTPacket.makeSYNPacket(self.getSeqNum())
                self._send(synPacket)
                logging.debug(
                    "Sent SYN Packet, waiting for ACK. Tries left={}".format(tries))
                data, addr = self.socket.recvfrom(MSS)
                synAckPacket = RDTPacket.fromSerializedPacket(data)
                receivedSYNACK = synAckPacket.isSYNACK(
                ) and addr[0] == self.destIP
            except timeout:
                tries -= 1
                logging.debug("Assuming Lost SYNACK, retrying".format(tries))
        if(tries == 0):
            logging.info("Error establishing connection")
            logging.debug("Assuming server not reachable")
            raise ServerUnreachable

        logging.info(
            "Connection established with Server {}:{}".format(
                *destAddr))

        self.setAckNum(synAckPacket.seqNum)
        logging.debug(
            "Received {} as first sequence number".format(self.getAckNum()))

        self.destPort = int(synAckPacket.data.decode())
        logging.debug("Changing server port to {}".format(self.destPort))

        self.waitForPackets()
        return True

    #########################
    #   COMMUNICATION API   #
    #########################

    def updateOutPutWindow(self, ackNum):
        # If is present, change the ACK boolean in OutPutWindow for that
        # element
        self.lockOutPutWindow.acquire()
        self.outPutWindow = [
            (x[0], x[1] or self.matchesACK(
                x[0], ackNum)) for x in self.outPutWindow]

        # Remove all cumulative ACKed packets from outPutWindow
        while(self.outPutWindow and self.outPutWindow[0][1]):
            self.outPutWindow.pop(0)
        self.lockOutPutWindow.release()

    """
        Checks if a packet should be added to input buffer.
        If it's the inmmediate expected packet ignores other conditions
    """

    def shouldAddToInputBuffer(self, packet):

        self.lockInputBuffer.acquire()
        alreadyInBuffer = self.inputBuffer.get(packet.seqNum) is not None
        isInputBufferFull = len(self.inputBuffer) >= INPUT_BUFFER_SIZE
        self.lockInputBuffer.release()

        isExpectedPacket = self.getAckNum() == packet.seqNum
        isOldPacket = self.getAckNum() >= packet.seqNum + len(packet.data)
        return isExpectedPacket or (
            not isInputBufferFull and not alreadyInBuffer and not isOldPacket)

    """
        Checks if a packet should by ACKed
    """

    def shouldACK(self, packet):
        isOldPacket = self.getAckNum() >= packet.seqNum + len(packet.data)

        self.lockInputBuffer.acquire()
        isInBuffer = self.inputBuffer.get(packet.seqNum)
        self.lockInputBuffer.release()

        return isOldPacket or isInBuffer

    """
        Finds the packet in outPutWindow that matchs that seqNum and returns
            the tuple (packet, wasACKed boolean)
    """

    def findPacket(self, seqNum):
        self.lockOutPutWindow.acquire()

        for tuplePacketAck in self.outPutWindow:
            if(tuplePacketAck[0].seqNum == seqNum):
                self.lockOutPutWindow.release()
                return tuplePacketAck

        self.lockOutPutWindow.release()
        return None

    """
        Checks if a sent packet's sequence number was ACKed
    """

    def wasACKED(self, seqNum):
        tuplePacketAck = self.findPacket(seqNum)
        if tuplePacketAck is not None:
            return tuplePacketAck[1]

        if(not self.isOutPutWindowEmpty()):
            self.lockOutPutWindow.acquire()
            ret = seqNum < self.outPutWindow[0][0].seqNum
            self.lockOutPutWindow.release()
            return ret

        return seqNum < self.getAckNum()

    def outPutWindowIsFull(self):
        self.lockOutPutWindow.acquire()
        ret = len(self.outPutWindow) == WINDOWSIZE
        self.lockOutPutWindow.release()
        return ret

    #####################
    #   * Receive API   #
    #####################

    """
        Receives using UDP socket
        Returns the first received packet that belongs to the connection
    """

    def _recv(self, bufsize):
        receivedSuccessfully = False
        data, addr = (None, None)
        while(not receivedSuccessfully):
            data, addr = self.socket.recvfrom(bufsize + RDT_HEADER_LENGTH)
            receivedSuccessfully = self.matchDestAddr(addr)
        return RDTPacket.fromSerializedPacket(data)

    """
        It's used by the Client/Client-Server
        Creates a thread with 'waitForPacketsThread' function
        * It's called in connect by Client
        * It's called in createConnection by Client-Server
    """

    def waitForPackets(self):
        logging.info("Now socket is receiving packets...")
        self.receivingThread = Thread(target=self.waitForPacketsThread)
        self.receivingThread.daemon = True  # Closes with the main thread
        self.receivingThread.start()
        return

    """
        It's used by the Client/Client-Server
        Loops receiving every packet that arrives to 'self.socket'
            and handles it.
        * If is FIN then 'interrupt' the connection
        * If is ACK then update outPutWindow
        * Else adds packets to InputBuffer if its necessary and
            sends an ACK, or discards it.
    """

    def waitForPacketsThread(self):
        self.socket.settimeout(1)

        while not self.wasRequestedClose():
            try:
                packet = self._recv(MSS)
            except timeout:
                continue  # Checks while condition again

            if packet.isACK():
                logging.debug(
                    "Connection({}:{}), Received ACK Packet(seqno={}, ackno={}, l={})".format(
                        self.destIP, self.destPort, packet.seqNum, packet.ackNum, len(
                            packet.data)))
                self.updateOutPutWindow(packet.ackNum)
            elif packet.isFIN():
                logging.debug(
                    "Connection({}:{}), Received FIN Packet".format(
                        self.destIP, self.destPort))
                finAckPacket = RDTPacket.makeFINACKPacket(
                    self.getSeqNum(), self.getAckNum())
                logging.debug(
                    "Connection({}:{}), Sending FINACK Packet".format(
                        self.destIP, self.destPort))
                self._send(finAckPacket)
                self.changeFlagRequestedClose(True)
            elif packet.isFINACK():
                logging.debug(
                    "Connection({}:{}), Received FINACK Packet".format(
                        self.destIP, self.destPort))
                self.changeFlagReceivedFINACK(True)
            else:
                if(self.shouldAddToInputBuffer(packet)):
                    logging.debug("Connection({}:{}), Received Packet(seqno={}, ackno={}, l={})".format(
                        self.destIP, self.destPort, packet.seqNum, packet.ackNum, len(packet.data)))

                    self.lockInputBuffer.acquire()
                    self.inputBuffer[packet.seqNum] = packet
                    self.lockInputBuffer.release()

                    ackPacket = RDTPacket.makeACKPacket(
                        packet.seqNum + len(packet.data))
                    logging.debug(
                        "Connection({}:{}), Sending ACK Packet(seqno={}, ackno={}, l={})".format(
                            self.destIP, self.destPort, ackPacket.seqNum, ackPacket.ackNum, len(
                                ackPacket.data)))
                    self._send(ackPacket)
                elif(self.shouldACK(packet)):  # ACK paquetes retransmitidos
                    logging.debug(
                        "Connection({}:{}), Received retransmited Packet(seqno={}, ackno={}, l={})".format(
                            self.destIP, self.destPort, packet.seqNum, packet.ackNum, len(
                                packet.data)))
                    ackPacket = RDTPacket.makeACKPacket(
                        packet.seqNum + len(packet.data))
                    logging.debug(
                        "Connection({}:{}), Sending ACK Packet(seqno={}, ackno={}, l={})".format(
                            self.destIP, self.destPort, ackPacket.seqNum, ackPacket.ackNum, len(
                                ackPacket.data)))
                    self._send(ackPacket)
                else:
                    logging.debug(
                        "Connection({}:{}), Discarding received Packet(seqno={}, ackno={}, l={})".format(
                            self.destIP, self.destPort, packet.seqNum, packet.ackNum, len(
                                packet.data)))
        logging.info("Now socket is not receiving packets anymore...")

    """
        Implements the RECV selective repeat protocol
        Returns next expected (in order) packet's payload
    """

    def recv(self):
        if(not self.getExpectedInput() and not self.wasRequestedClose()):
            logging.debug(
                "Connection({}:{}), packet {} not received yet, waiting... ".format(
                    self.destIP, self.destPort, self.getAckNum()))
        while(not self.getExpectedInput() and not self.wasRequestedClose()):
            time.sleep(0.1)

        expectedPacket = self.getExpectedInput()

        if(expectedPacket):
            isCorrupt = expectedPacket.checksum != expectedPacket.calculateChecksum()
            if(not isCorrupt):
                logging.debug(
                    "Connection({}:{}), packet {} received successfully".format(
                        self.destIP, self.destPort, self.getAckNum()))
                #logging.debug("Received packet checksum: {}".format(expectedPacket.checksum))
                #logging.debug("Calculated packet checksum: {}".format(expectedPacket.calculateChecksum()))
                self.lockInputBuffer.acquire()
                del self.inputBuffer[self.getAckNum()]
                self.lockInputBuffer.release()
                self.addToAckNum(len(expectedPacket.data))
                return expectedPacket.data

        if(self.wasRequestedClose()):
            logging.debug(
                "Connection({}:{}) requested close. Socket cannot receive any more packets".format(
                    self.destIP, self.destPort))
            return b''

    ##################
    #   * Send API   #
    ##################

    """
        Sends a rdtpacket using UDP socket
    """

    def _send(self, packet):
        # TODO lockear al booleano
        if(not self.wasRequestedClose()):
            lenbytessent = self.socket.sendto(packet.serialize(), (self.destIP, self.destPort))
            return lenbytessent

    """
        Implements the SEND selective repeat protocol.
        Starts a resend-timer for every packet sent, calls 'resend' function
            after timer's timeout
        Returns the amount of bytes 'sent'.
    """

    def send(self, bytes):
        if(self.isClosed() or self.hasReceivedFINACK()):
            return 0

        if(self.outPutWindowIsFull()):
            logging.debug(
                "Connection({}:{}), outPutWindow is full, waiting for ACKs".format(
                    self.destIP, self.destPort))

        while self.outPutWindowIsFull():
            # TODO
            time.sleep(0.2)

        if(self.isLostConnection()):
            logging.debug(
                "Connection({}:{}), Assuming lost connection, cannot send anymore.".format(
                    self.destIP, self.destPort))
            raise LostConnection

        packetSent = RDTPacket(
            self.getSeqNum(),
            self.getAckNum(),
            None,
            False,
            False,
            False,
            bytes)
        
        logging.debug("Sent Packet checksum: {}".format(packetSent.checksum))
        logging.debug(
            "Connection({}:{}), Sending Packet(seqno={}, ackno={}, l={})".format(
                self.destIP, self.destPort, packetSent.seqNum, packetSent.ackNum, len(
                    packetSent.data)))

        lenbytessent = self._send(packetSent)
        if(lenbytessent == 0):
            return 0

        self.lockOutPutWindow.acquire()
        self.outPutWindow.append((packetSent, False))
        self.lockOutPutWindow.release()
        timerThread = Timer(RESEND_TIME, self.resend, (packetSent.seqNum,))
        timerThread.daemon = True
        timerThread.start()
        self.addToSeqNum(len(bytes))
        return len(bytes)

    """
        Implements the selective repeat retransmission
        Will be executed after some time, checking if an ACK was
            received for the corresponding packet.
            If not, then resends the packet and restars the timer
    """

    def resend(self, seqNum, tries=NRETRIES):
        if(self.isClosed() or self.hasReceivedFINACK()):
            return
        if(tries <= 0):
            self.changeFlagLostConnection(True)
            self.lockOutPutWindow.acquire()
            self.outPutWindow = []
            self.lockOutPutWindow.release()
            return
        if(not self.wasACKED(seqNum)):
            tuplePacketAck = self.findPacket(seqNum)
            if(tuplePacketAck is not None and tuplePacketAck[0] is not None):
                logging.debug(
                    "Connection({}:{}), Resending Packet(seqno={}, ackno={}, l={}), tries left={}".format(
                        self.destIP, self.destPort, tuplePacketAck[0].seqNum, tuplePacketAck[0].ackNum, len(
                            tuplePacketAck[0].data), tries - 1))
                self._send(tuplePacketAck[0])
                timerThread = Timer(
                    RESEND_TIME, self.resend, (seqNum, tries - 1))
                timerThread.daemon = True
                timerThread.start()

    ###################
    #   * Close API   #
    ###################

    """
        Used in Server Socket
        Removes destinationAddress from the map of unaccepted or
            accepted connections
    """

    def closeConnectionSocket(self, destinationAddress):
        self.lockUnacceptedConnections.acquire()
        if(self.unacceptedConnections.get(destinationAddress) is not None):
            del self.unacceptedConnections[destinationAddress]
        self.lockUnacceptedConnections.release()

        self.lockAcceptedConnections.acquire()
        if(self.acceptedConnections.get(destinationAddress) is not None):
            del self.acceptedConnections[destinationAddress]
        self.lockAcceptedConnections.release()

    def sendFIN(self):
        tries = NRETRIES
        while(tries > 0 and not self.hasReceivedFINACK()):
            packetFIN = RDTPacket.makeFINPacket(self.getSeqNum(), self.getAckNum())
            logging.debug(
                "Connection({}:{}), sending FIN Packet(seqno={}, ackno={}, l={}), tries left={}".format(
                    self.destIP, self.destPort, packetFIN.seqNum, packetFIN.ackNum, len(
                        packetFIN.data), tries))
            self._send(packetFIN)
            tries -= 1

            # Es como el timer... no es taaan horrible
            time.sleep(1)
        if(self.hasReceivedFINACK()):
            logging.debug(
                "Connection({}:{}) correctly closed...".format(
                    self.destIP, self.destPort))
        else:
            logging.debug(
                "Connection({}:{}) cannot close correctly, assuming other side currently closed...".format(
                    self.destIP, self.destPort))

    def closeSender(self):
        logging.info("Closing socket...")

        if(not self.isOutPutWindowEmpty()):
            logging.debug(
                "Connection({}:{}), waiting to send correctly every packet".format(
                    self.destIP, self.destPort))
        while(not self.isOutPutWindowEmpty()):
            # TODO idem 100pre
            time.sleep(0.2)

        if(not self.isLostConnection()):
            logging.debug(
                "Connection({}:{}), correctly sent all packets".format(
                    self.destIP, self.destPort))
            self.sendFIN()
        else:
            logging.debug(
                "Connection({}:{}), assuming lost connection".format(
                    self.destIP, self.destPort))
        self.changeFlagClosed(True)

        # ServerClient socket should be deleted of Server socket list
        if(self.mainSocket is not None):
            self.mainSocket.closeConnectionSocket((self.destIP, self.destPort))
        logging.debug(
            "Connecion({}:{}) ending receiving-thread".format(self.destIP, self.destPort))
        self.changeFlagRequestedClose(True)
        self.receivingThread.join()
        logging.debug(
            "Connecion({}:{}), closing UDP-Socket".format(self.destIP, self.destPort))
        self.socket.close()
        logging.info("Socket closed...")

    def closeReceiver(self):
        logging.info("Closing socket...")
        if(self.mainSocket is not None):
            self.mainSocket.closeConnectionSocket((self.destIP, self.destPort))

        logging.debug(
            "Connecion({}:{}) ending receiving-thread".format(self.destIP, self.destPort))
        self.changeFlagRequestedClose(True)
        self.receivingThread.join()

        logging.debug(
            "Connecion({}:{}), closing UDP-Socket".format(self.destIP, self.destPort))
        self.socket.close()
        logging.info("Socket closed...")

    def closeServer(self):
        logging.info("Closing server socket...")
        self.changeFlagListening(False)
        self.changeFlagClosed(True)
        # Join listen thread
        logging.debug(
            "Server socket, ending listening-thread".format(self.destIP, self.destPort))
        self.listeningThread.join()
        # Close unaccepted sockets running
        logging.debug(
            "Server socket, closing all unaccepted connections".format(
                self.destIP, self.destPort))
        for _, conn in self.unacceptedConnections.items():
            conn.requestedClose = True
            conn.receivingThread.join()
            conn.socket.close()

        logging.debug(
            "Server socket, closing UDP-Socket".format(self.destIP, self.destPort))
        self.socket.close()
        logging.info("Server socket closed...")
