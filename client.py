from RDTSocket import RDTSocket
from RDTPacket import RDTPacket
import logging
import time

logging.basicConfig(level=logging.DEBUG, filename="client.log",
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y/%m/%d %I:%M:%S %p')

clientSocket = RDTSocket()
clientSocket.connect(('127.0.0.1', 12000))
print("Conectado al servidor en la dirección: {}:{}".format(clientSocket.destIP, clientSocket.destPort))

packet, addr = clientSocket.recv(2000) #TODO: RECV STOP AND WAIT (TENGO QUE SUMAR EL ACK POR LA CANT DE BYTES RECIBIDOS)
print("packet data length: {}".format(len(packet.data)))
time.sleep(5)
clientSocket.send(RDTPacket.makeACKPacket(clientSocket.ackNum + len(packet.data)).serialize())
print(packet.data.decode().rstrip('\x00'))
clientSocket.close()
