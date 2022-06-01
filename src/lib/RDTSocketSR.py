import time
import logging
import random

from src.lib.exceptions import TimeOutException
from threading import Lock, Thread, Timer
from socket import socket, AF_INET, SOCK_DGRAM, SHUT_RD, timeout
from src.lib.RDTPacket import RDTPacket
from sys import getsizeof


MSS = 1500
WINDOWSIZE = 2
INPUT_BUFFER_SIZE = 4
RESEND_TIME = 0.5
RDTHEADER = 11

class RDTSocketSR:
    ##############################
    #         COMMON API         #
    ##############################
    def __init__(self):
        self.socket = socket(AF_INET, SOCK_DGRAM)
        self.seqNum = random.randint(0, 1000)
        logging.info("Initial sequence number: {}".format(self.seqNum))

    # https://stackoverflow.com/questions/1365265/on-localhost-how-do-i-pick-a-free-port-number
    srcIP = ''  # Default source addr
    srcPort = 0  # Default source port
    destIP = None
    destPort = None

    seqNum = 0
    ackNum = 0
    socket = None  # Underlying UDP socket

    def getDestinationAddress(self):
        return (self.destIP, self.destPort)

    def matchDestAddr(self, addr):
        return addr == (self.destIP, self.destPort)

    def matchesACK(self, packet, ackNum):
        return packet.seqNum + len(packet.data) == ackNum


    #####################################
    #         LISTEN/ACCEPT API         #
    #####################################
    mainSocket = None
    listening = False
    lockUnacceptedConnections = Lock()
    unacceptedConnections = {}          # Waiting for accept socket map

    lockAcceptedConnections = Lock()
    acceptedConnections = {}            # Accepted socket map

    """
        It's used by the server during creation of new socket for a client,
        Assigns the client address (obtained during handshake) on (destIP, destPort)
    """
    def setDestinationAddress(self, address):
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

    """
        It's used by the server.
        Create a thread where it will listen for new connections
    """
    def listen(self, maxQueuedConnections):
        listeningThread = Thread(target=self.listenThread,
                                 args=(maxQueuedConnections,))
        listeningThread.daemon = True  # Closes with the main thread
        self.listening = True
        listeningThread.start()
        logging.debug("Now server is listening...")

    """
        It's used by the server. 
        If receive a SYN message, performs the 2whs with the client,
            creates a new socket and appends it to unacceptedConnections...
    """
    def listenThread(self, maxQueuedConnections):
        # TODO?: si está llena acceptedConnections deberíamos quedarnos en un while
        # esperando que se vacíe, no hacer otra cosa
        while(self.listening):
            data, address = self.socket.recvfrom(MSS)
            packet = RDTPacket.fromSerializedPacket(data)

            if(packet.isSYN() and self.isNewClient(address)):
                logging.info(
                    "Requested connection from [{}:{}]".format(
                        *address))
                if(self.getAmountOfPendingConnections() >= maxQueuedConnections):
                    logging.info(
                        "Requested connection [{}:{}] refused".format(
                            *address))
                    continue  # Descarto las solicitudes de conexiones TODO: enviar mensaje de rechazo

                newConnection = self.createConnection(address, packet.seqNum)

                self.lockUnacceptedConnections.acquire()
                self.unacceptedConnections[newConnection.getDestinationAddress()] = newConnection
                self.lockUnacceptedConnections.release()

                synAckPacket = RDTPacket.makeSYNACKPacket(
                    newConnection.seqNum, newConnection.ackNum, newConnection.srcPort)
                self.socket.sendto(synAckPacket.serialize(), address)

                logging.info(
                    "Sent server sequence number: {} y ACK number {}".format(
                        newConnection.seqNum, newConnection.ackNum))

            elif(packet.isSYN() and not self.isNewClient(address)):
                logging.info(
                    "Requested connection from [{}:{}] already connected".format(
                        *address))
                newConnection = self.getClient(address)
                synAckPacket = RDTPacket.makeSYNACKPacket(
                    newConnection.seqNum, newConnection.ackNum, newConnection.srcPort)
                self.socket.sendto(synAckPacket.serialize(), address)
                logging.info(
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
        logging.debug("Accepted connection")

        addr, connection = self.popUnacceptedConnection()

        self.lockAcceptedConnections.acquire()
        self.acceptedConnections[addr] = connection
        self.lockAcceptedConnections.release()
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

        logging.info("Envío client_isn num: {}".format(self.seqNum))
        self.socket.settimeout(2)  # 2 second timeout
        synAckPacket, addr = (None, None)
        receivedSYNACK = False
        tries = 5

        while(not receivedSYNACK and tries > 0):
            try:
                synPacket = RDTPacket.makeSYNPacket(self.seqNum)
                self._send(synPacket)
                data, addr = self.socket.recvfrom(MSS)
                synAckPacket = RDTPacket.fromSerializedPacket(data)
                receivedSYNACK = synAckPacket.isSYNACK(
                ) and addr[0] == self.destIP
            except timeout:
                tries -= 1
                logging.info("Lost SYNACK, {} tries left".format(tries))
        if(tries == 0):
            logging.info("Error establishing connection")
            raise TimeOutException

        self.ackNum = synAckPacket.seqNum

        # Change the server service port
        self.destPort = int(synAckPacket.data.decode())
        logging.info("Connected to: {}:{}".format(*destAddr))
        self.waitForPackets()
        return True


    #########################
    #   COMMUNICATION API   #
    #########################
    receivingThread = None
    lockInputBuffer = Lock()
    inputBuffer = {}
    lockOutPutWindow = Lock()
    outPutWindow = []

    def updateOutPutWindow(self, ackNum):
        # If is present, change the ACK boolean in OutPutWindow for that element
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
        logging.debug("Waiting for packets...")
        self.socket.settimeout(1)

        while not self.requestedClose:
            try:
                packet = self._recv(MSS)
            except timeout:
                continue  # Checks while condition again

            if packet.isACK():
                logging.debug("Client({}:{}), Received ACK Packet(seqno={}, ackno={}, ack?=yes, l={})".format(self.destIP,self.destPort, packet.seqNum, packet.ackNum, len(packet.data)))
                self.updateOutPutWindow(packet.ackNum)
            elif packet.isFIN():
                logging.debug("Client({}:{}), Received FIN Packet".format(self.destIP,self.destPort))
                self.requestedClose = True
                ackPacket = RDTPacket.makeACKPacket(self.ackNum)
                self._send(ackPacket)
            else:
                if(self.shouldAddToInputBuffer(packet)):
                    logging.debug("Client({}:{}), Received Packet(seqno={}, ackno={}, ack?=no, l={})".format(self.destIP,self.destPort, packet.seqNum, packet.ackNum, len(packet.data)))
                    self.inputBuffer[packet.seqNum] = packet
                    ackPacket = RDTPacket.makeACKPacket(
                        packet.seqNum + len(packet.data))
                    logging.debug("Client({}:{}), Sending Packet(seqno={}, ackno={}, ack?=yes, l={})".format(self.destIP, self.destPort, ackPacket.seqNum, ackPacket.ackNum, len(ackPacket.data)))
                    self._send(ackPacket)
                elif(self.shouldACK(packet)):  # ACK paquetes retransmitidos
                    logging.debug("Client({}:{}), Received retransmited Packet(seqno={}, ackno={}, ack?=no, l={})".format(self.destIP,self.destPort, packet.seqNum, packet.ackNum, len(packet.data)))
                    ackPacket = RDTPacket.makeACKPacket(
                        packet.seqNum + len(packet.data))
                    logging.debug("Client({}:{}), Sending Packet(seqno={}, ackno={}, ack?=yes, l={})".format(self.destIP, self.destPort, ackPacket.seqNum, ackPacket.ackNum, len(ackPacket.data)))
                    self._send(ackPacket)
                else:
                    logging.debug("Client({}:{}), Discarding received Packet(seqno={}, ackno={}, ack?=no, l={})".format(self.destIP,self.destPort, packet.seqNum, packet.ackNum, len(packet.data)))

    """
        Implements the RECV selective repeat protocol
        Returns next expected (in order) packet's payload
    """
    def recvSelectiveRepeat(self, bufsize):
        logging.debug("Waiting for packet {}".format(self.ackNum))
        while(not self.inputBuffer.get(self.ackNum) and not self.requestedClose):
            time.sleep(0.1)

        if(self.requestedClose):
            return b''

        packet = self.inputBuffer.get(self.ackNum)
        del self.inputBuffer[self.ackNum]
        self.ackNum = self.ackNum + len(packet.data)
        return packet.data


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
    def sendSelectiveRepeat(self, bytes):
        if(self.isClosed):
            return 0

        if(self.outPutWindowIsFull()):
            logging.debug("outPutWindow is full, waiting for ACKs")

        while self.outPutWindowIsFull():
            time.sleep(0.2)

        packetSent = RDTPacket(self.seqNum, self.ackNum, False, False, False, bytes)
        logging.debug("Sending Packet(seqno={},ackno={}, ack?=no, l={})".format(packetSent.seqNum, packetSent.ackNum, len(packetSent.data)))
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
    def resend(self, seqNum):
        if(not self.wasACKED(seqNum)):
            tuplePacketAck = self.findPacket(seqNum)
            if(tuplePacketAck is not None and tuplePacketAck[0] is not None):
                logging.debug("Resending Packet(seqno={},ackno={}, ack?=no, l={})".format(tuplePacketAck[0].seqNum, tuplePacketAck[0].ackNum, len(tuplePacketAck[0].data)))
                self._send(tuplePacketAck[0])
                timerThread = Timer(RESEND_TIME, self.resend, (seqNum,))
                timerThread.daemon = True
                timerThread.start()

    ###################
    #   * Close API   #
    ###################

    # WORK IN PROGRESS!!!

    requestedClose = False
    isClosed = False

    """
        Used in close function.
        Sends a FIN packet with Stop and Wait protocol
    """
    def sendFIN(self):
        receivedAck = False
        bytesSent = 0
        tries = 10  # Es temporal, la usamos para evitar ciclos infinitos

        logging.debug(
            "Start sending, destination [{}:{}]".format(
                self.destIP, self.destPort))
        while(not receivedAck and tries > 0):
            try:
                packetSent = RDTPacket.makeFINPacket(self.seqNum, self.ackNum)
                bytesSent = self.socket.sendto(
                    packetSent.serialize(), (self.destIP, self.destPort))

                try:
                    recvPacket = self._recv(MSS)
                except BaseException:
                    return b''

                if(recvPacket.isACK() and (self.seqNum == recvPacket.ackNum)):
                    logging.info("Sent successfully")
                    receivedAck = True
                elif(recvPacket.isACK()):
                    logging.debug(
                        "Invalid ACK num [{}], expected [{}]".format(
                            recvPacket.ackNum,
                            (self.seqNum)))
                    logging.info("Retrying...")
                else:
                    logging.debug(
                        "Unexpected message from {}:{}, expected ACK".format(
                            self.destIP, self.destPort))
            except timeout:
                logging.info("Timeout")
                logging.info("Retrying...")
                tries -= 1
        return bytesSent

    """
        Used in close function
        Waits for FIN from the other part of the connection
        Discards other packets that aren't FIN
    """
    def recvFIN(self):
        receivedSuccessfully = False
        receivedPacket = None
        while(not receivedSuccessfully):
            logging.debug("Waiting for FIN packet [{}]".format(self.ackNum))

            try:
                receivedPacket = self._recv(MSS)
            except BaseException:
                return b''

            receivedSuccessfully = receivedPacket.seqNum == self.ackNum
            # TODO: verificar checksum
            if(receivedSuccessfully):
                self.ackNum += len(receivedPacket.data)
            responsePacket = RDTPacket.makeACKPacket(self.ackNum)
            self._send(responsePacket)

        return receivedPacket.data

    """
        Used in Server Socket
        Closes  
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

    def close(self):
        logging.debug("Try to close, sending FIN")
        if(self.listening):  # Es main server socket
            #TODO: listen close
            self.listening = False
            # Join listen thread
            self.isClosed = True
            # Join the other threads
            # Close unaccepted sockets running
            logging.debug("Closing server socket")
            self.socket.close()
            return

        if(self.requestedClose):
            self.receivingThread.join()
            self.sendFIN()
        else:
            while(self.outPutWindow):
                time.sleep(0.2)
            self.isClosed = True
            self.receivingThread.join()  # Espera al timeout del hilo del recv
            self.sendFIN()
            self.recvFIN()

        # ServerClient socket should be deleted of Server socket list
        if(self.mainSocket is not None):
            self.mainSocket.closeConnectionSocket((self.destIP, self.destPort))

        logging.debug("Closing socket")
        self.socket.close()
        
        #si recibo fin -> send fin 10 tries -> close definitivo

        #sendFIN()
        #waitForFINorACK() timeout 10 tries
        #closeDefinitivo()

        """
            TODO: HACER TEST
            
            Hilo1:
            socketServer = RDTSocketSR()
            bind
            listen
            accept
            recv()
            close()

            Hilo2:
            socketClient = RDTScoketSR()
            connect
            send()
            close()
        """