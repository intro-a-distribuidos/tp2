import time
import logging
import random

from .exceptions import LostConnection, ServerUnreachable
from threading import Lock, Thread
from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR, timeout
from .RDTPacket import RDTPacket, RDT_HEADER_LENGTH
from sys import getsizeof


MSS = 1500
NRETRIES = 17
RESEND_TIME = 0.5
RECEIVE_TIMEOUT = NRETRIES * RESEND_TIME

class RDTSocketSW:
    def __init__(self):
        self.mainSocket = None
        self.socket = socket(AF_INET, SOCK_DGRAM) #Underlying UDP socket
        self.seqNum = random.randint(0, 1000)
        self.ackNum = 0

        # https://stackoverflow.com/questions/1365265/on-localhost-how-do-i-pick-a-free-port-number
        self.srcIP = ''  # Default source addr
        self.srcPort = 0  # Default source port
        self.destIP = None
        self.destPort = None

        
        self.listening = False
        self.listeningThread = None
        self.lockUnacceptedConnections = Lock()
        self.unacceptedConnections = {}          # Mapa de sockets en espera

        self.lockAcceptedConnections = Lock()
        self.acceptedConnections = {}            # Mapa de sockets aceptados
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

    def connect(self, destAddr):
        self.destIP, self.destPort = destAddr

        logging.info("Envío client_isn num: {}".format(self.seqNum))
        self.socket.settimeout(RECEIVE_TIMEOUT)
        synAckPacket, addr = (None, None)
        receivedSYNACK = False
        tries = NRETRIES

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
            raise ServerUnreachable

        self.ackNum = synAckPacket.seqNum
        # El cliente ahora apunta al socket especifico de la conexión en vez de
        # al listen
        self.destPort = int(synAckPacket.data.decode())
        logging.info("Connected to: {}:{}".format(*destAddr))
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
        self.listeningThread = Thread(target=self.listenThread,
                                 args=(maxQueuedConnections,))
        self.listeningThread.daemon = True  # Closes with the main thread
        self.listening = True
        self.listeningThread.start()
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
                    continue

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
        Lo ejecuta el servidor para crear un socket nuevo para la comunicación con el cliente
    """

    def createConnection(self, clientAddress, initialAckNum):
        newConnection = RDTSocketSW()
        newConnection.bind(('', 0))
        newConnection.socket.settimeout(RECEIVE_TIMEOUT)
        newConnection.setDestinationAddress(clientAddress)
        newConnection.ackNum = initialAckNum
        newConnection.mainSocket = self
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
        logging.info("Receiving...")
        receivedSuccessfully = False
        data, addr = (None, None)
        while(not receivedSuccessfully):
            data, addr = self.socket.recvfrom(bufsize + RDT_HEADER_LENGTH)
            receivedSuccessfully = self.matchDestAddr(addr)
        return RDTPacket.fromSerializedPacket(data)

    def _send(self, packet):
        logging.info("Sending...")
        return self.socket.sendto(
            packet.serialize(), (self.destIP, self.destPort))

    """
        WORK IN PROGRESS
    """

    def send(self, bytes):
        receivedAck = False
        bytesSent = 0
        tries = NRETRIES

        logging.debug(
            "Start sending, destination [{}:{}]".format(
                self.destIP, self.destPort))
        while(not receivedAck and tries > 0):
            try:
                logging.debug(
                    "Sending SEQNO [{}], ACKNO [{}]".format(
                        self.seqNum, self.ackNum))
                packetSent = RDTPacket(
                    self.seqNum, self.ackNum, None, False, False, False, bytes)
                bytesSent = self.socket.sendto(
                    packetSent.serialize(), (self.destIP, self.destPort))

                recvPacket = self._recv(MSS)

                if(recvPacket.isACK() and ((self.seqNum + len(bytes)) == recvPacket.ackNum)):
                    logging.info("Sent successfully")
                    self.seqNum += len(bytes)
                    receivedAck = True
                elif(recvPacket.isACK()):
                    logging.debug(
                        "Invalid ACK num [{}], expected [{}]".format(
                            recvPacket.ackNum,
                            (self.seqNum + len(bytes))))
                    logging.info("Retrying...")
                else:
                    logging.debug(
                        "Unexpected message from {}:{}, excepted ACK".format(
                            self.destIP, self.destPort))
            except timeout:
                logging.info("Timeout")
                logging.info("Retrying...")
                tries -= 1
            if(tries == 0):
                raise LostConnection
        return bytesSent

    def recv(self):
        logging.info("Receiving...")
        receivedSuccessfully = False
        receivedPacket = None
        tries = NRETRIES
        logging.debug("Waiting for packet [{}]".format(self.ackNum))
        while(not receivedSuccessfully):
            try:
                receivedPacket = self._recv(MSS)
            except timeout:
                tries -= 1
                if(tries < 0):
                    raise LostConnection
                else:
                    continue

            receivedSuccessfully = receivedPacket.seqNum == self.ackNum
            isCorrupt = receivedPacket.checksum != receivedPacket.calculateChecksum()
            if(receivedSuccessfully and not isCorrupt):
                self.ackNum += len(receivedPacket.data)
            responsePacket = RDTPacket.makeACKPacket(self.ackNum)
            self._send(responsePacket)

            if(receivedPacket.isFIN()):
                logging.info("Received FIN packet")
                return b''
        return receivedPacket.data

    def sendFIN(self):
        receivedAck = False
        bytesSent = 0
        tries = NRETRIES

        logging.debug(
            "Start sending, destination [{}:{}]".format(
                self.destIP, self.destPort))
        while(not receivedAck and tries > 0):
            try:
                logging.debug(
                    "Sending SEQNO [{}], ACKNO [{}]".format(
                        self.seqNum, self.ackNum))
                finPacket = RDTPacket.makeFINPacket()
                
                bytesSent = self.socket.sendto(
                    finPacket.serialize(), (self.destIP, self.destPort))

                try:
                    recvPacket = self._recv(MSS)
                except LostConnection:
                    return 0

                if(recvPacket.isACK() and (self.seqNum == recvPacket.ackNum)):
                    logging.info("Sent successfully")
                    receivedAck = True
                else:
                    logging.debug(
                        "Unexpected message from {}:{}, excepted ACK".format(
                            self.destIP, self.destPort))
            except timeout:
                logging.info("Timeout")
                logging.info("Retrying...")
                tries -= 1
            if(tries == 0):
                raise LostConnection
        return bytesSent

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
        if(self.mainSocket is not None):
            self.mainSocket.closeConnectionSocket((self.destIP, self.destPort))

        self.listening = False
        self.socket.close()

    def closeSender(self):
        self.sendFIN()
        if(self.mainSocket is not None):
            self.mainSocket.closeConnectionSocket((self.destIP, self.destPort))
        self.socket.close()
        logging.info("Socket closed...")

    def closeReceiver(self):
        if(self.mainSocket is not None):
            self.mainSocket.closeConnectionSocket((self.destIP, self.destPort))
        self.socket.close()
        logging.info("Socket closed...")

    def closeServer(self):
        self.listening = False
        if(self.listeningThread):
            self.listeningThread.join()

        for _, conn in self.unacceptedConnections.items():
            conn.socket.close()
            self.socket.close()
