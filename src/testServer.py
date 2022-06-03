from lib.RDTSocketSR import RDTSocketSR
import logging
import sys
from time import sleep

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y/%m/%d %I:%M:%S %p',
                    stream=sys.stdout)

serverSocket = RDTSocketSR()
serverSocket.bind(('', 12000))
serverSocket.listen(1)

connSocket, addr = serverSocket.accept()

while True:  # de 1 a 12
    bytes = connSocket.recv()  # 1
    if(bytes != b''):
        print(bytes.decode())
    else:
        break

connSocket.closeReceiver()
serverSocket.closeServer()
