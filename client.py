from multiprocessing.connection import wait
from timeit import repeat
from RDTSocket import RDTSocket
from RDTPacket import RDTPacket
from exceptions import TimeOutException
import logging
import time
import sys

logging.basicConfig(level=logging.DEBUG, #filename="client.log",
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y/%m/%d %I:%M:%S %p',
                    stream=sys.stdout)

"""
    El servidor manda un paquete con stop and wait, con un timeout de 2 segundos.
    Desde el lado del cliente recibo el paquete y espero 5 segundos antes de mandar el acknowledge.
    Por lo tanto, el servidor deberia reenviar el paquete 2 veces.
"""

clientSocket = RDTSocket()

try:
    clientSocket.connect(('127.0.0.1', 12000))
except TimeOutException:
    logging.info("Cannot connect with Server: TIMEOUT")
    exit()

logging.debug("Client opened in {}:{}".format(*clientSocket.getsockname()))

logging.info("Connecting with Server: {}:{}".format(clientSocket.destIP, clientSocket.destPort))


packet, addr = clientSocket.recv(2000) #TODO: RECV STOP AND WAIT (TENGO QUE SUMAR EL ACK POR LA CANT DE BYTES RECIBIDOS)

time.sleep(5)

logging.info("Packet data length: {}".format(len(packet.data)))

clientSocket.send(RDTPacket.makeACKPacket(clientSocket.ackNum + len(packet.data)).serialize())

logging.info(packet.data.decode())

clientSocket.close()