import time
import logging
import random

from lib.exceptions import TimeOutException
from threading import Lock, Thread, Timer
from socket import socket, AF_INET, SOCK_DGRAM, SHUT_RD, timeout
from lib.RDTPacket import RDTPacket
from sys import getsizeof


MSS = 1500
WINDOWSIZE = 2
INPUT_BUFFER_SIZE = 4
RESEND_TIME = 0.5

class RDTSocketSR:
    RDTHEADER = 11
    mainSocket = None
    listenSocket = None

    receivingThread = None

    lockInputBuffer = Lock()
    inputBuffer = {}
    lockOutPutWindow = Lock()
    outPutWindow = []

    # https://stackoverflow.com/questions/1365265/on-localhost-how-do-i-pick-a-free-port-number
    srcIP = ''  # Default source addr
    srcPort = 0  # Default source port
    destIP = None
    destPort = None

    seqNum = 0
    ackNum = 0
    socket = None  # Underlying UDP socket
    listening = False

    lockUnacceptedConnections = Lock()
    unacceptedConnections = {}          # Mapa de sockets en espera

    lockAcceptedConnections = Lock()
    acceptedConnections = {}            # Mapa de sockets aceptados

    requestedClose = False
    isClosed = False

    def __init__(self):
        self.socket = socket(AF_INET, SOCK_DGRAM)
        self.seqNum = random.randint(0, 1000)
        logging.info("Initial sequence number: {}".format(self.seqNum))

    def getsockname(self):
        self.srcIP, self.srcPort = self.socket.getsockname()
        return(self.srcIP, self.srcPort)

    """
        Se usa cuando se crea un socket en el servidor,
        se asigna la dirección del cliente al socket (obtiene la direccion del cliente durante el saludo)
    """

    def setDestinationAddress(self, address):
        self.destIP = address[0]
        self.destPort = address[1]

    """
        Matchea la address de destino con el address recibido
    """

    def matchDestAddr(self, addr):
        return addr == (self.destIP, self.destPort)

    """
        Se ejecuta del lado del cliente,
        realiza el three way handshake con el servidor
    """

    def matchesACK(self, packet, ackNum):
        return packet.seqNum + len(packet.data) == ackNum

    def updateOutPutWindow(self, ackNum):
        self.outPutWindow = [
            (x[0], x[1] or self.matchesACK(
                x[0], ackNum)) for x in self.outPutWindow]

        while(self.outPutWindow and self.outPutWindow[0][1]):
            self.outPutWindow.pop(0)

    def shouldAddToInputBuffer(self, packet):
        alreadyInBuffer = self.inputBuffer.get(packet.seqNum) is not None
        isExpectedPacket = self.ackNum == packet.seqNum
        isInputBufferFull = len(self.inputBuffer) >= INPUT_BUFFER_SIZE
        isOldPacket = self.ackNum >= packet.seqNum + len(packet.data)
        return isExpectedPacket or (
            not isInputBufferFull and not alreadyInBuffer and not isOldPacket)

    def shouldACK(self, packet):
        isOldPacket = self.ackNum >= packet.seqNum + len(packet.data)
        isInBuffer = self.inputBuffer.get(packet.seqNum)

        return isOldPacket or isInBuffer

    def waitForPackets(self):
        self.receivingThread = Thread(target=self.waitForPacketsThread)
        self.receivingThread.daemon = True  # Closes with the main thread
        self.receivingThread.start()
        return

    def waitForPacketsThread(self):
        logging.debug("Waiting for packets...")
        self.socket.settimeout(1)

        while not self.requestedClose:
            try:
                packet = self._recv(MSS)
            except timeout:
                continue  # Se chequea la condicion del while nuevamente

            if packet.isACK():
                logging.debug("Client({}:{}), Received ACK Packet(seqno={}, ackno={}, ack?=yes, l={})".format(self.destIP,self.destPort, packet.seqNum, packet.ackNum, len(packet.data)))
                self.updateOutPutWindow(packet.ackNum)
            elif packet.isFIN():
                logging.debug("Client({}:{}), Received FIN Packet".format(self.destIP,self.destPort))
                self.requestedClose = True
                finAckPacket = RDTPacket.makeFINACKPacket()
                self._send(finAckPacket)
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
            
        return

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
        # El cliente ahora apunta al socket especifico de la conexión en vez de
        # al listen
        self.destPort = int(synAckPacket.data.decode())
        logging.info("Connected to: {}:{}".format(*destAddr))
        self.waitForPackets()
        return True
    """
        Se utiliza para asignarle una dirección especifica al socket (generalmente al socket del listen del servidor),
        también se usa cuando se crea un socket para el cliente en el servidor
    """

    def bind(self, address):
        ip, port = address
        self.srcIP = ip
        self.srcPort = port
        self.socket.bind(address)
        self.srcPort = self.socket.getsockname()[1]

    """
        Se ejecuta del lado del servidor,
        crea un hilo donde se queda escuchando a nuevos clientes.
    """

    def listen(self, maxQueuedConnections):
        listeningThread = Thread(target=self.listenThread,
                                 args=(maxQueuedConnections,))
        listeningThread.daemon = True  # Closes with the main thread
        self.listening = True
        listeningThread.start()
        logging.debug("Now server is listening...")

    def isNewClient(self, address):
        self.lockUnacceptedConnections.acquire()
        unaccepted = address in self.unacceptedConnections
        self.lockUnacceptedConnections.release()

        self.lockAcceptedConnections.acquire()
        accepted = address in self.acceptedConnections
        self.lockAcceptedConnections.release()

        return not unaccepted and not accepted

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
        Se ejecuta del lado del servidor,
        realiza el two way handshake con el cliente y crea un socket nuevo para la conexión.

        Si recibe un mensaje "SYN" crea un socket en unacceptedConnections,
    """

    def listenThread(self, maxQueuedConnections):
        # si está llena acceptedConnections deberíamos quedarnos en un while
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
                self.unacceptedConnections[newConnection.getDestinationAddress(
                )] = newConnection
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
        Lo ejecuta el servidor para crear un socket nuevo para la comunicación con el cliente
    """

    def createConnection(self, clientAddress, initialAckNum):
        newConnection = RDTSocketSR()
        newConnection.bind(('', 0))
        newConnection.socket.settimeout(2)  # 2 second timeout
        newConnection.setDestinationAddress(clientAddress)
        newConnection.ackNum = initialAckNum
        newConnection.mainSocket = self
        newConnection.waitForPackets()
        return newConnection

    def getDestinationAddress(self):
        return (self.destIP, self.destPort)

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

    def popUnacceptedConnection(self):
        self.lockUnacceptedConnections.acquire()
        # Obtengo primer key value pair en el diccionario
        addr, connection = next(iter(self.unacceptedConnections.items()))
        del self.unacceptedConnections[addr]
        self.lockUnacceptedConnections.release()
        return (addr, connection)

    """
        Poppea el primer socket de la lista unacceptedConnections[],
        si la lista está vacía, bloquea el hilo de ejecución hasta que haya un socket disponible.
    """

    def accept(self):
        logging.debug("Waiting for new connections")

        while(self.unacceptedConnectionsIsEmpty()):
            time.sleep(0.2)
        logging.debug("Accepted connection")

        addr, connection = self.popUnacceptedConnection()

        self.lockAcceptedConnections.acquire()
        self.acceptedConnections[addr] = connection
        self.lockAcceptedConnections.release()
        return (connection, addr)

    def _recv(self, bufsize):
        receivedSuccessfully = False
        data, addr = (None, None)
        while(not receivedSuccessfully):
            data, addr = self.socket.recvfrom(bufsize + self.RDTHEADER)
            receivedSuccessfully = self.matchDestAddr(addr)
        return RDTPacket.fromSerializedPacket(data)

    def _send(self, packet):
        return self.socket.sendto(
            packet.serialize(), (self.destIP, self.destPort))

    """
        WORK IN PROGRESS
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

    def findPacket(self, seqNum):
        for tuplePacketAck in self.outPutWindow:
            if(tuplePacketAck[0].seqNum == seqNum):
                return tuplePacketAck
        return None

    def resend(self, seqNum):
        if(not self.wasACKED(seqNum)):
            tuplePacketAck = self.findPacket(seqNum)
            if(tuplePacketAck is not None and tuplePacketAck[0] is not None):
                logging.debug("Resending Packet(seqno={},ackno={}, ack?=no, l={})".format(tuplePacketAck[0].seqNum, tuplePacketAck[0].ackNum, len(tuplePacketAck[0].data)))
                self._send(tuplePacketAck[0])
                timerThread = Timer(RESEND_TIME, self.resend, (seqNum,))
                timerThread.daemon = True
                timerThread.start()

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

    def sendFIN(self):
        receivedAck = False
        bytesSent = 0
        tries = 10  # Es temporal, la usamos para evitar ciclos infinitos

        logging.debug(
            "Start sending, destination [{}:{}]".format(
                self.destIP, self.destPort))
        while(not receivedAck and tries > 0):
            try:
                packetSent = RDTPacket.makeFINPacket()
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
        if(self.listening):  # Es main server socket
            #TODO: listen close
            self.listening = False
            self.isClosed = True
            self.socket.close()
            return

        if(self.requestedClose):
            self.receivingThread.join()
            self.sendFIN()
        else:
            while(self.outPutWindow):
                time.sleep(0.2)
            self.requestedClose = True
            self.receivingThread.join()  # Espera al timeout del hilo del recv
            self.sendFIN()
            self.recvFIN()

        if(self.mainSocket is not None):
            self.mainSocket.closeConnectionSocket((self.destIP, self.destPort))

        self.isClosed = True
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