import time
import logging
import random
from threading import Thread
from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR, timeout
from RDTPacket import RDTPacket
from sys import getsizeof

MSS = 1500


class RDTSocket:
    # https://stackoverflow.com/questions/1365265/on-localhost-how-do-i-pick-a-free-port-number
    srcIP = ''  # Default source addr
    srcPort = 0  # Default source port
    destIP = None
    destPort = None

    seqNum = 0
    ackNum = 0
    socket = None  # Underlying UDP socket
    listening = False
    unacceptedConnections = {}  # Mapa de sockets en espera
    acceptedConnections = {}

    def __init__(self):
        self.socket = socket(AF_INET, SOCK_DGRAM)
        self.seqNum = random.randint(0, 1000)
        logging.info("Initial sequence number: {}".format(self.seqNum))

    """
        Se usa cuando se crea un socket en el servidor, 
        se asigna la dirección del cliente al socket (obtiene la direccion del cliente durante el saludo)
    """
    def setDestinationAddress(self, address):
        self.destIP = address[0]
        self.destPort = address[1]

    """
        Se ejecuta del lado del cliente,
        realiza el three way handshake con el servidor
    """
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
                self.send(synPacket.serialize())
                synAckPacket, addr = self.recv(MSS)  # receive SYN ACK
                receivedSYNACK = synAckPacket.isSYNACK() and addr[0] == self.destIP
            except timeout:
                logging.info("Lost SYNACK, {} tries left".format(tries))
                tries -= 1
        if(tries == 0):
            logging.info("Error establishing connection")
            return

        self.ackNum = synAckPacket.seqNum
        self.destPort = int(synAckPacket.data.decode())  # El cliente ahora apunta al socket especifico de la conexión en vez de al listen
        logging.info("Connected to: {}:{}".format(destAddr[0], destAddr[1])) 

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
        logging.debug("Listening...")
        listeningThread.start()
        logging.debug("Finished listening")

    def isNewClient(self, address):
        return (address not in self.unacceptedConnections) and (address not in self.acceptedConnections)

    def getClient(self, clientAddress):
        client = self.unacceptedConnections.get(clientAddress)
        if(client is None):
            client = self.acceptedConnections.get(clientAddress)

        return client

    """
        Se ejecuta del lado del servidor,
        realiza el three way handshake con el cliente y crea un socket nuevo para la conexión.

        Si recibe un mensaje "SYN" crea un socket en unconfirmedConnections,
        Si recibe un mensaje "ACK", elimina el socket de unconfirmedConnections y lo agrega a unacceptedConnections.
    """
    def listenThread(self, maxQueuedConnections):
        # si está llena acceptedConnections deberíamos quedarnos en un while esperando que se vacíe, no hacer otra cosa
        while(self.listening):
            data, address = self.socket.recvfrom(MSS)
            packet = RDTPacket.fromSerializedPacket(data)

            if(packet.isSYN() and self.isNewClient(address)):
                if(self.getAmountOfPendingConnections() >= maxQueuedConnections):
                    continue  # Descarto las solicitudes de conexiones TODO: enviar mensaje de rechazo
                newConnection = self.createConnection(address, packet.seqNum)
                self.unacceptedConnections[newConnection.getDestinationAddress()] = newConnection
                synAckPacket = RDTPacket.makeSYNACKPacket(newConnection.seqNum, newConnection.ackNum, newConnection.srcPort)
                self.socket.sendto(synAckPacket.serialize(), address)
                logging.info("Sent server sequence number: {} y ACK number {}".format(newConnection.seqNum, newConnection.ackNum))
                logging.info("Requested connection from:", address[0], ":", address[1])
            elif(packet.isSYN() and not self.isNewClient(address)):
                newConnection = self.getClient(address)
                synAckPacket = RDTPacket.makeSYNACKPacket(newConnection.seqNum, newConnection.ackNum, newConnection.srcPort)
                self.socket.sendto(synAckPacket.serialize(), address)
                logging.info("Resending SYNACK server sequence number: {} y ACK number {}".format(newConnection.seqNum, newConnection.ackNum))
                logging.info("Requested connection from:", address[0], ":", address[1])

    """
        Lo ejecuta el servidor para crear un socket nuevo para la comunicación con el cliente
    """
    def createConnection(self, clientAddress, initialAckNum):
        newConnection = RDTSocket()
        newConnection.bind(('', 0))
        newConnection.socket.settimeout(2)  # 2 second timeout
        newConnection.setDestinationAddress(clientAddress)
        newConnection.ackNum = initialAckNum
        return newConnection

    def getDestinationAddress(self):
        return (self.destIP, self.destPort)

    def getAmountOfPendingConnections(self):
        return len(self.unacceptedConnections)

    """
        Poppea el primer socket de la lista unacceptedConnections[],
        si la lista está vacía, bloquea el hilo de ejecución hasta que haya un socket disponible.
    """
    def accept(self):
        logging.debug("Waiting for new connections")
        while((not self.unacceptedConnections)):
            time.sleep(0.2)
        logging.debug("Accepted connection")
        addr, connection = next(iter(self.unacceptedConnections.items()))  #Obtengo primer key value pair en el diccionario
        self.acceptedConnections[addr] = connection
        del self.unacceptedConnections[addr]
        return (connection, addr)

    def recv(self, bufsize):
        logging.info("Receiving...")
        serializedPacket, addr = self.socket.recvfrom(bufsize)
        return (RDTPacket.fromSerializedPacket(serializedPacket), addr)

    def send(self, bytes):
        logging.info("Sending...")
        return self.socket.sendto(bytes, (self.destIP, self.destPort))

    """
        WORK IN PROGRESS
    """
    def sendStopAndWait(self, bytes):   
        logging.info("Sending...")
        receivedAck = False
        bytesSent = None
        destAddr = None
        tries = 0  # Es temporal, la usamos para evitar ciclos infinitos

        logging.info("{}:{}".format(self.destIP, self.destPort))
        while(not receivedAck and tries < 10):
            try:
                logging.info("Sending...")
                packetSent = RDTPacket(self.seqNum, self.ackNum, 0, 0, bytes)
                self.socket.sendto(packetSent.serialize(), (self.destIP, self.destPort))
                recvPacket, addr = self.recv(MSS)
                if(recvPacket.isACK() and ((self.seqNum + len(bytes) + 1) == recvPacket.ackNum)):
                    logging.info("Sent successfully")
                    self.seqNum += len(bytes)
                    receivedAck = True
                else:
                    logging.info("Invalid ack num")
                    logging.info("Retrying...")
            except timeout:
                logging.info("Timeout")
                logging.info("Retrying...")
                tries += 1
        return (bytesSent, destAddr)

    def close(self):
        self.listening = False
        self.socket.close()