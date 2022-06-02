import time
import logging
import random

from lib.exceptions import LostConnetion, TimeOutException, ServerUnreachable
from threading import Lock, Thread, Timer
from socket import socket, AF_INET, SOCK_DGRAM, SHUT_RD, timeout
from lib.RDTPacket import RDTPacket
from sys import getsizeof


MSS = 1500
WINDOWSIZE = 2
INPUT_BUFFER_SIZE = 4  # UDP buffer size = 65535, 44 MSS
RESEND_TIME = 0.5
RDTHEADER = 11
NRETRIES = 20  # see doc


class RDTSocketSR:
    ##############################
    #         COMMON API         #
    ##############################
    def __init__(self):
        self.socket = socket(AF_INET, SOCK_DGRAM)
        self.seqNum = random.randint(0, 1000)
        logging.debug(
            "Configuring new Socket. Initial sequence number: {}".format(
                self.seqNum))

        # https://stackoverflow.com/questions/1365265/on-localhost-how-do-i-pick-a-free-port-number
        self.srcIP = ''  # Default source addr
        self.srcPort = 0  # Default source port
        self.destIP = None
        self.destPort = None

        self.ackNum = 0

        self.lostConnection = False

        self.mainSocket = None
        self.listening = False
        self.listeningThread = None
        self.lockUnacceptedConnections = Lock()
        self.unacceptedConnections = {}          # Waiting for accept socket map

        self.lockAcceptedConnections = Lock()
        self.acceptedConnections = {}            # Accepted socket map

        self.receivingThread = None
        self.lockInputBuffer = Lock()
        self.inputBuffer = {}
        self.lockOutPutWindow = Lock()
        self.outPutWindow = []

        self.receivedFINACK = False
        self.requestedClose = False
        self.isClosed = False

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
        self.listening = True
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

        while(self.listening):
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
                synPacket = RDTPacket.makeSYNPacket(self.seqNum)
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

        self.ackNum = synAckPacket.seqNum
        logging.debug(
            "Received {} as first sequence number".format(
                self.ackNum))

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
        self.outPutWindow = [
            (x[0], x[1] or self.matchesACK(
                x[0], ackNum)) for x in self.outPutWindow]

        # Remove all cumulative ACKed packets from outPutWindow
        while(self.outPutWindow and self.outPutWindow[0][1]):
            self.outPutWindow.pop(0)

    """
        Checks if a packet should be added to input buffer.
        If it's the inmmediate expected packet ignores other conditions
    """

    def shouldAddToInputBuffer(self, packet):
        alreadyInBuffer = self.inputBuffer.get(packet.seqNum) is not None
        isInputBufferFull = len(self.inputBuffer) >= INPUT_BUFFER_SIZE
        isExpectedPacket = self.ackNum == packet.seqNum
        isOldPacket = self.ackNum >= packet.seqNum + len(packet.data)
        return isExpectedPacket or (
            not isInputBufferFull and not alreadyInBuffer and not isOldPacket)

    """
        Checks if a packet should by ACKed
    """

    def shouldACK(self, packet):
        isOldPacket = self.ackNum >= packet.seqNum + len(packet.data)
        isInBuffer = self.inputBuffer.get(packet.seqNum)

        return isOldPacket or isInBuffer

    """
        Finds the packet in outPutWindow that matchs that seqNum and returns
            the tuple (packet, wasACKed boolean)
    """

    def findPacket(self, seqNum):
        for tuplePacketAck in self.outPutWindow:
            if(tuplePacketAck[0].seqNum == seqNum):
                return tuplePacketAck
        return None

    """
        Checks if a sent packet's sequence number was ACKed
    """

    def wasACKED(self, seqNum):
        tuplePacketAck = self.findPacket(seqNum)
        if tuplePacketAck is not None:
            return tuplePacketAck[1]
        if(self.outPutWindow):
            return seqNum < self.outPutWindow[0][0].seqNum
        return seqNum < self.ackNum

    def outPutWindowIsFull(self):
        return len(self.outPutWindow) == WINDOWSIZE

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
            data, addr = self.socket.recvfrom(bufsize + RDTHEADER)
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

        while not self.requestedClose:
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
                    self.seqNum, self.ackNum)
                logging.debug(
                    "Connection({}:{}), Sending FINACK Packet".format(
                        self.destIP, self.destPort))
                self._send(finAckPacket)
                self.requestedClose = True
                self.socket.close()
            elif packet.isFINACK():
                logging.debug(
                    "Connection({}:{}), Received FINACK Packet".format(
                        self.destIP, self.destPort))
                self.receivedFINACK = True
            else:
                if(self.shouldAddToInputBuffer(packet)):
                    logging.debug("Connection({}:{}), Received Packet(seqno={}, ackno={}, l={})".format(
                        self.destIP, self.destPort, packet.seqNum, packet.ackNum, len(packet.data)))
                    self.inputBuffer[packet.seqNum] = packet
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
        if(not self.inputBuffer.get(self.ackNum) and not self.requestedClose):
            logging.debug(
                "Connection({}:{}), packet {} not received yet, waiting... ".format(
                    self.destIP, self.destPort, self.ackNum))
        while(not self.inputBuffer.get(self.ackNum) and not self.requestedClose):
            time.sleep(0.1)

        if(self.inputBuffer.get(self.ackNum)):
            logging.debug(
                "Connection({}:{}), packet {} received successfully".format(
                    self.destIP, self.destPort, self.ackNum))
            packet = self.inputBuffer.get(self.ackNum)
            del self.inputBuffer[self.ackNum]
            self.ackNum = self.ackNum + len(packet.data)
            return packet.data

        if(self.requestedClose):
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
        return self.socket.sendto(
            packet.serialize(), (self.destIP, self.destPort))

    """
        Implements the SEND selective repeat protocol.
        Starts a resend-timer for every packet sent, calls 'resend' function
            after timer's timeout
        Returns the amount of bytes 'sent'.
    """

    def send(self, bytes):
        if(self.isClosed):
            return 0

        if(self.outPutWindowIsFull()):
            logging.debug(
                "Connection({}:{}), outPutWindow is full, waiting for ACKs".format(
                    self.destIP, self.destPort))

        while self.outPutWindowIsFull():
            # TODO
            time.sleep(0.2)

        if(self.lostConnection):
            logging.debug(
                "Connection({}:{}), Assuming lost connection, cannot send anymore.".format(
                    self.destIP, self.destPort))
            raise LostConnetion

        packetSent = RDTPacket(
            self.seqNum,
            self.ackNum,
            False,
            False,
            False,
            bytes)
        logging.debug(
            "Connection({}:{}), Sending Packet(seqno={}, ackno={}, l={})".format(
                self.destIP, self.destPort, packetSent.seqNum, packetSent.ackNum, len(
                    packetSent.data)))
        self._send(packetSent)
        self.outPutWindow.append((packetSent, False))  # TODO: Usar lock()
        timerThread = Timer(RESEND_TIME, self.resend, (packetSent.seqNum,))
        timerThread.daemon = True
        timerThread.start()
        self.seqNum += len(bytes)
        return len(bytes)

    """
        Implements the selective repeat retransmission
        Will be executed after some time, checking if an ACK was
            received for the corresponding packet.
            If not, then resends the packet and restars the timer
    """

    def resend(self, seqNum, tries=NRETRIES):
        if(self.isClosed or self.receivedFINACK):
            return
        if(tries <= 0):
            self.lostConnection = True
            self.outPutWindow = []
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
        while(tries > 0 and not self.receivedFINACK):
            packetFIN = RDTPacket.makeFINPacket(self.seqNum, self.ackNum)
            logging.debug(
                "Connection({}:{}), sending FIN Packet(seqno={}, ackno={}, l={}), tries left={}".format(
                    self.destIP, self.destPort, packetFIN.seqNum, packetFIN.ackNum, len(
                        packetFIN.data), tries))
            self._send(packetFIN)
            tries -= 1

            # Es como el timer... no es taaan horrible
            time.sleep(1)
        if(self.receivedFINACK):
            logging.debug(
                "Connection({}:{}) correctly closed...".format(
                    self.destIP, self.destPort))
        else:
            logging.debug(
                "Connection({}:{}) cannot close correctly, assuming other side currently closed...".format(
                    self.destIP, self.destPort))

    def closeSender(self):
        logging.info("Closing socket...")

        if(self.outPutWindow):
            logging.debug(
                "Connection({}:{}), waiting to send correctly every packet".format(
                    self.destIP, self.destPort))
        while(self.outPutWindow):
            # TODO idem 100pre
            time.sleep(0.2)

        if(not self.lostConnection):
            logging.debug(
                "Connection({}:{}), correctly sent all packets".format(
                    self.destIP, self.destPort))
            self.sendFIN()
        else:
            logging.debug(
                "Connection({}:{}), assuming lost connection".format(
                    self.destIP, self.destPort))
        self.isClosed = True

        # ServerClient socket should be deleted of Server socket list
        if(self.mainSocket is not None):
            self.mainSocket.closeConnectionSocket((self.destIP, self.destPort))
        logging.debug(
            "Connecion({}:{}) ending receiving-thread".format(self.destIP, self.destPort))
        self.requestedClose = True
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
        self.requestedClose = True
        self.receivingThread.join()

        logging.debug(
            "Connecion({}:{}), closing UDP-Socket".format(self.destIP, self.destPort))
        self.socket.close()
        logging.info("Socket closed...")

    def closeServer(self):
        logging.info("Closing server socket...")
        self.listening = False
        self.isClosed = True
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
