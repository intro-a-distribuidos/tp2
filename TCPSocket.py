import time
import logging
from threading import Thread
from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR

MSS = 1200


class TCPSocket:
    # https://stackoverflow.com/questions/1365265/on-localhost-how-do-i-pick-a-free-port-number
    srcIP = ''  # Default source addr
    srcPort = 0  # Default source port
    destIP = None
    destPort = None

    socket = None  # Underlying UDP socket
    listening = False
    unconfirmedConnections = {}  # Conexiones que no completaron el twh
    unacceptedConnections = {}  # Mapa de sockets en espera

    def __init__(self):
        self.socket = socket(AF_INET, SOCK_DGRAM)

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
        self.send("SYN".encode())
        data, addr = self.recv(MSS)  # receive SYN ACK

        if(data.decode().startswith("SYN ACK") and addr[0] == self.destIP):
            print(data.decode())
            self.send("ACK".encode())
            self.destPort = int(data.decode()[7:])  # El cliente ahora apunta al socket especifico de la conexión en vez de al listen
        else:
            print("Error establishing connection")
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
            if(self.twhIsSYN(data) and address not in self.unconfirmedConnections):
                if(self.getAmountOfPendingConnections() >= maxQueuedConnections):  
                    continue  #Descarto las solicitudes de conexiones
                newConnection = self.createConnection(address)
                self.unconfirmedConnections[newConnection.getDestinationAddress()] = newConnection
                self.socket.sendto(("SYN ACK" + str(newConnection.srcPort)).encode(), address)
                print("Requested connection from:", address[0], ":", address[1])
            elif(self.twhIsACK(data) and address in self.unconfirmedConnections):
                clientSocket = self.unconfirmedConnections[address]
                self.unacceptedConnections[address] = clientSocket
                del self.unconfirmedConnections[address]
                print("Three way handshake completed with client:", address[0], ":", address[1])
                # TODO: self.awakeAccept()

    """
        Lo ejecuta el servidor para crear un socket nuevo para la comunicación con el cliente
    """
    def createConnection(self, address):
        newConnection = TCPSocket()
        newConnection.bind(('', 0))
        newConnection.setDestinationAddress(address)
        return newConnection

    def twhIsSYN(self, data):
        return data.decode() == "SYN"

    def twhIsACK(self, data):
        return data.decode() == "ACK"

    def getDestinationAddress(self):
        return (self.destIP, self.destPort)

    def getAmountOfPendingConnections(self):
        return len(self.unconfirmedConnections) + len(self.unacceptedConnections)

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
        del self.unacceptedConnections[addr]
        return (connection, addr)

    def recv(self, bufsize):
        logging.info("Receiving...")
        print("Receiving...")
        return self.socket.recvfrom(bufsize)

    def send(self, bytes):
        logging.info("Sending...")
        return self.socket.sendto(bytes, (self.destIP, self.destPort))

    def close(self):
        self.listening = False
        self.socket.close()

    """
    Borrador:

    def recv(buffer):
        received = False
        while(!received):
            data, address = socket.recvfrom(2000)
            if(coincide con cliente):
                received = True
                return data, address
            # pass
    """