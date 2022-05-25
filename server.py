from RDTSocket import RDTSocket
from exceptions import TimeOutException
import logging
import time
import sys

logging.basicConfig(level=logging.DEBUG, #filename="server.log",
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y/%m/%d %I:%M:%S %p',
                    stream=sys.stdout)

SERVER_PORT = 12000

serverSocket = RDTSocket()
serverSocket.bind(('', SERVER_PORT))
serverSocket.listen(1)
logging.debug("Server listening on port {0}".format(SERVER_PORT))

connectionSocket, addr = serverSocket.accept()
logging.info("socket accepted with addr:{}".format(addr))
packet, addr = connectionSocket.sendStopAndWait("Hola mundo".encode())  #TEST Stop and wait
connectionSocket.close()

while True:
    logging.debug(str(serverSocket.acceptedConnections))
    connectionSocket, addr = serverSocket.accept()
    logging.info("socket accepted with addr: {}:{}".format(*addr))
    packet, addr = connectionSocket.sendStopAndWait("Hola mundo".encode())  #TEST Stop and wait
    connectionSocket.close()

time.sleep(200)
serverSocket.close()