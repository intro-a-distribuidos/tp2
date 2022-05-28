from ast import While
from curses import window
import time
import logging
import random
from turtle import goto

from sqlalchemy import null
from exceptions import TimeOutException
from threading import Lock, Thread, Timer
from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR, timeout
from RDTPacket import RDTPacket
from sys import getsizeof


MSS = 1500
WINDOWSIZE = 1500
class RDTSocketSR:
    RDTHEADER = 10
    mainSocket = None
    listenSocket = None
    inputBuffer = []
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
        self.outPutWindow = map(lambda x : (x[0], x[1] or self.matchesACK(x[0], ackNum)), self.outPutWindow)

        
    def waitForPackets(self):
        
        return

    def waitForPacketsThread(self):
        self.socket.settimeout(None)
        while True:
            packet,addr = self._recv(MSS)
            if (len(self.outPutBuffer) < WINDOWSIZE):
                if packet.isACK():
                    self.updateOutPutWindow(packet.ackNum)
                else:
                    self.inputBuffer.append(packet)
        
        return 

    def connect(self, destAddr):
        self.destIP, self.destPort = destAddr

        logging.info("Envío client_isn num: {}".format(self.seqNum))
        self.socket.settimeout(2)  # 2 second timeout
        synAckPacket, addr = (None, None)
        receivedSYNACK = False
        tries = 3

        while(not receivedSYNACK and tries > 0):
            try:
                synPacket = RDTPacket.makeSYNPacket(self.seqNum)
                self._send(synPacket)
                data, addr = self.socket.recvfrom(MSS)
                synAckPacket = RDTPacket.fromSerializedPacket(data)
                receivedSYNACK = synAckPacket.isSYNACK() and addr[0] == self.destIP
            except timeout:
                tries -= 1
                logging.info("Lost SYNACK, {} tries left".format(tries))
        if(tries == 0):
            logging.info("Error establishing connection")
            raise TimeOutException

        self.ackNum = synAckPacket.seqNum
        self.destPort = int(synAckPacket.data.decode())  # El cliente ahora apunta al socket especifico de la conexión en vez de al listen
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
        # si está llena acceptedConnections deberíamos quedarnos en un while esperando que se vacíe, no hacer otra cosa
        while(self.listening):
            data, address = self.socket.recvfrom(MSS)
            packet = RDTPacket.fromSerializedPacket(data)

            if(packet.isSYN() and self.isNewClient(address)):
                logging.info("Requested connection from [{}:{}]".format(*address))
                if(self.getAmountOfPendingConnections() >= maxQueuedConnections):
                    logging.info("Requested connection [{}:{}] refused".format(*address))
                    continue  # Descarto las solicitudes de conexiones TODO: enviar mensaje de rechazo

                newConnection = self.createConnection(address, packet.seqNum)

                self.lockUnacceptedConnections.acquire()
                self.unacceptedConnections[newConnection.getDestinationAddress()] = newConnection
                self.lockUnacceptedConnections.release()

                synAckPacket = RDTPacket.makeSYNACKPacket(newConnection.seqNum, newConnection.ackNum, newConnection.srcPort)
                self.socket.sendto(synAckPacket.serialize(), address)

                logging.info("Sent server sequence number: {} y ACK number {}".format(newConnection.seqNum, newConnection.ackNum))

            elif(packet.isSYN() and not self.isNewClient(address)):
                logging.info("Requested connection from [{}:{}] already connected".format(*address))
                newConnection = self.getClient(address)
                synAckPacket = RDTPacket.makeSYNACKPacket(newConnection.seqNum, newConnection.ackNum, newConnection.srcPort)
                self.socket.sendto(synAckPacket.serialize(), address)
                logging.info("Resending SYNACK server sequence number: {} y ACK number {}".format(newConnection.seqNum, newConnection.ackNum))
    """
        Lo ejecuta el servidor para crear un socket nuevo para la comunicación con el cliente
    """
    def createConnection(self, clientAddress, initialAckNum):
        newConnection = RDTSocket()
        newConnection.bind(('', 0))
        newConnection.socket.settimeout(2)  # 2 second timeout
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
            data, addr = self.socket.recvfrom(bufsize + self.RDTHEADER)
            receivedSuccessfully = self.matchDestAddr(addr)
        return RDTPacket.fromSerializedPacket(data)

    def _send(self, packet):
        logging.info("Sending...")
        return self.socket.sendto(packet.serialize(), (self.destIP, self.destPort))

    """
        WORK IN PROGRESS
    """
    def wasACKED(self, seqNum):
        if seqNum >= self.seqNum:
            return False
        tuplePacketAck = self.findPacket(seqNum,self.outPutWindow)
        if tuplePacketAck is not None:
            return tuplePacketAck[1]

        return seqNum < self.outPutWindow[0][0] 
       
            
    def outPutWindowIsFull(self):
        return len(self.outPutWindow) == WINDOWSIZE

    def findPacket(self, seqNum,list):
        return next(filter(lambda tuplePacketAck: tuplePacketAck[0].seqNum == seqNum, list))
        
    def resend(self,seqNum):
        if(not self.wasACKED(seqNum)):
            packet,_ = self.findPacket(seqNum,self.outPutWindow)
            if packet is not None:
                self._send(packet)
                timerThread = Timer(2, self.resend, [self,seqNum])
                timerThread.daemon = True 
                timerThread.start()


    def sendSelectiveRepeat(self, bytes):
        
        while self.outPutWindowIsFull():
            time.sleep(0.2)

        packetSent = RDTPacket(self.seqNum, self.ackNum, 0, 0, bytes)
        self._send(packetSent)
        self.outputWindow.append((packetSent,False)) #TODO: Usar lock()
        timerThread = Timer(2, self.resend, [self,packetSent.seqNum])
        timerThread.daemon = True 
        timerThread.start()
        self.seqNum += len(bytes)
    




    def recvStopAndWait(self, bufsize):
        logging.info("Receiving...")
        receivedSuccessfully = False
        receivedPacket = None
        while(not receivedSuccessfully):
            logging.debug("Waiting for packet [{}]".format(self.ackNum))
            
            try:
                receivedPacket = self._recv(bufsize)
            except:
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
        if(self.mainSocket is not None):
            self.mainSocket.closeConnectionSocket((self.destIP, self.destPort))
 
        self.listening = False
        self.socket.close()
