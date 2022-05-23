from TCPSocket import TCPSocket
import logging
import time

logging.basicConfig(level=logging.DEBUG, filename="server.log",
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y/%m/%d %I:%M:%S %p')

SERVER_PORT = 12000

serverSocket = TCPSocket()
serverSocket.bind(('', SERVER_PORT))
serverSocket.listen(1)
logging.debug("Server listening on port {0}".format(SERVER_PORT))
connectionSocket, addr = serverSocket.accept()
print("socket accepted with addr:", addr)

connectionSocket.close()
serverSocket.close()