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
    acceptedConnections = []  # Lista de sockets en espera

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
        listening_thread = Thread(target=self.listen_thread, 
                                  args=(maxQueuedConnections,))
        listening_thread.daemon = True  # Closes with the main thread
        self.listening = True
        logging.debug("Listening...")
        listening_thread.start()
        logging.debug("Finished listening")

    """
        Se ejecuta del lado del servidor,
        realiza el three way handshake con el cliente, crea un socket nuevo para la conexión y lo coloca en la lista acceptedConnections[].
    """
    def listen_thread(self, maxQueuedConnections):
        while(self.listening):
            message, address = self.socket.recvfrom(MSS)
            if(message.decode() == "SYN"):
                print("Requested connection from:", address[0], ":", address[1])
                if(len(self.acceptedConnections) < maxQueuedConnections): #TODO: mover esto más arriba
                    newConnection = self.createConnection(address)
                    self.acceptedConnections.append(newConnection)
                    self.socket.sendto(("SYN ACK" + str(newConnection.srcPort)).encode(), address)
                    message2, address2 = self.socket.recvfrom(MSS)
                    print("Received 2nd msg from:", address[0], ":", address[1])
                    if(message2.decode() == "ACK"):
                        print("Three way handshake completed with client:", address2[0], ":", address2[1])
                else:
                    print("Error while doing TWH")
            else:
                print("Received unwanted message:", message.decode())

    """
        Lo ejecuta el servidor para crear un socket nuevo para la comunicación con el cliente
    """
    def createConnection(self, address):
        newConnection = TCPSocket()
        newConnection.bind(('', 0))
        newConnection.setDestinationAddress(address)
        return newConnection

    def getDestinationAddress(self):
        return (self.destIP, self.destPort)

    """
        Poppea el primer socket de la lista acceptedConnections[],
        si la lista está vacía, bloquea el hilo de ejecución hasta que haya un socket disponible.
    """
    def accept(self):
        logging.debug("Waiting for new connections")
        while((not self.acceptedConnections)):
            time.sleep(0.2)
        logging.debug("Accepted connection")
        connection = self.acceptedConnections.pop(0)
        addr = connection.getDestinationAddress()
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