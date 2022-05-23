from TCPSocket import TCPSocket
import logging

logging.basicConfig(level=logging.DEBUG, filename="client.log",
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y/%m/%d %I:%M:%S %p')

clientSocket = TCPSocket()
clientSocket.connect(('127.0.0.1', 12000))
print("Conectado al servidor en la dirección: {}:{}".format(clientSocket.destIP, clientSocket.destPort))

clientSocket.close()
