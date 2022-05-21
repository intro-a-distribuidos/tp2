import time
import logging
from threading import Thread
from socket import socket, AF_INET, SOCK_DGRAM

MSS = 1200

class RDTsocket:
    # https://stackoverflow.com/questions/1365265/on-localhost-how-do-i-pick-a-free-port-number
    srcIP = ''  # Default source addr
    srcPort = 0  # Default source port
    destIP = None
    destPort = None

    socket = None  # Underlying UDP socket
    listening = False
    acceptedConnections = []

    def __init__(self):
        self.socket = socket(AF_INET, SOCK_DGRAM)

    def setDestinationAddress(self, address):
        self.destIP = address[0]
        self.destPort = address[1]

    def getDestinationAddress(self):
        return (self.destIP, self.destPort)

    def connect(self, destAddr):
        self.destIP, self.destPort = destAddr
        self.send("SYN".encode())
        data, addr = self.recv(MSS)
        if(data.decode() == "SYN ACK"):
            print("SYN ACK received")
            self.send("ACK".encode())
        else:
            print("Error establishing connection")
        logging.info("Connected to: {}:{}".format(destAddr[0], destAddr[1])) 

    def bind(self, address):
        # TODO: The socket must not already be bound. 
        ip, port = address
        self.srcIP = ip
        self.srcPort = port
        self.socket.bind(address) 

    def listen(self, maxQueuedConnections):
        self.listening = True

    def twhsIsSYN(self, data):
        return data.decode() == "SYN"

    def twhsIsACK(self, data):
        return data.decode() == "ACK"

    def twhsSendSYNACK(self, address):
        self.socket.sendto("SYN ACK".encode(), address)

    def listen_thread(self, maxQueuedConnections):
        unconfirmedConnections = []
        # si está llena acceptedConnections deberíamos quedarnos en un while esperando que se vacíe, no hacer otra cosa
        while(self.listening):
            data, address = self.socket.recvfrom(MSS)
            if(self.twhsIsSYN(data) and address not in unconfirmedConnections): # TODO: not in acceptedConnections, y si hay espacio en las conexiones
                self.twhsSendSYNACK(address)
                unconfirmedConnections.append(address)
                print("Requested connection from:", address[0], ":", address[1])
            elif(self.twhsIsACK(data) and address in unconfirmedConnections): # TODO: not in acceptedConnections
                unconfirmedConnections.remove(address)
                print("Three way handshake completed with client:", address[0], ":", address[1])
                if(len(self.acceptedConnections) < maxQueuedConnections):
                    self.acceptedConnections.append(self.createConnection(address))
                    # TODO: self.awakeAccept()

    def createConnection(self, address):
        newConnection = RDTsocket()
        # TODO: falta bind.
        newConnection.setDestinationAddress(address)
        return newConnection

    def accept(self):
        logging.debug("Waiting for new connections")
        while((not self.acceptedConnections)):
            time.sleep(10) # TODO self.spleep(), que no ejecute nada hasta tener la lista no vacía.
        logging.debug("Accepted connection")
        connection = self.acceptedConnections.pop(0)
        addr = connection.getDestinationAddress()
        return (connection, addr)

    def recv(self, bufsize):
        logging.info("Receiving...")
        return self.socket.recvfrom(bufsize)

    def send(self, bytes):
        logging.info("Sending...")
        return self.socket.sendto(bytes, (self.destIP, self.destPort))

    def close(self):
        self.listening = False
        self.socket.close()

    """
    def recv(buffer):
        received = False
        while(!received):
            data, address = socket.recvfrom(2000)
            if(coincide con cliente):
                received = True
                return data, address
            # pass
    """
