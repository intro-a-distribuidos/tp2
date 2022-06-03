import argparse
import pathlib
from socket import AF_INET, SOCK_STREAM
from FileTransfer import FileTransfer, Packet
import logging
from lib.exceptions import NameNotFoundException
import sys
from lib.RDTSocketSR import RDTSocketSR
from lib.RDTSocketSW import RDTSocketSW
import time

RDT_SR = 1
RDT_SW = 2

def getArgs():
    parser = argparse.ArgumentParser()
    parser._action_groups.pop()

    optionals = parser.add_argument_group('optional arguments')
    optionals.add_argument(
        '-H',
        '--host',
        type=str,
        metavar='',
        default='127.0.0.1',
        help='server IP address')
    optionals.add_argument(
        '-p',
        '--port',
        type=int,
        default=5050,
        metavar='',
        help='server port')
    optionals.add_argument(
        '-d',
        '--dst',
        type=pathlib.Path,
        metavar='',
        help='destination file path')
    optionals.add_argument(
        '-n',
        '--name',
        type=str,
        metavar='',
        help='file name')

    optionals.add_argument(
        '-v',
        '--verbose',
        action='store_const',
        dest='verboseLevel',
        const=3,
        default=2,
        metavar='',
        help='increase output verbosity')
    optionals.add_argument(
        '-q',
        '--quiet',
        action='store_const',
        dest='verboseLevel',
        const=1,
        default=2,
        metavar='',
        help='decrease output verbosity')
    

    rdt = optionals.add_mutually_exclusive_group()
    rdt.add_argument(
        '-sr',
        '--selective-repeat',
        action='store_const',
        dest='rdtType',
        const=RDT_SR,
        default=1,
        metavar='',
        help='use Selective Repeat how RDT method')
    rdt.add_argument(
        '-sw',
        '--stop-and-wait',
        action='store_const',
        dest='rdtType',
        const=RDT_SW,
        default=1,
        metavar='',
        help='use Stop and Wait how RDT method')

    return parser.parse_args()


args = getArgs()

logging.basicConfig(level=logging.DEBUG,  # filename="client.log",
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y/%m/%d %I:%M:%S %p',
                    stream=sys.stdout)

###############################################################
#   Esto es un ejemplo de como funcionaria bajar un archivo   #
#   del directorio del servidor.                              #
###############################################################


# Me creo que socket que me intento conectar con el servidor
if  args.rdtType == RDT_SR:
    client_socket = RDTSocketSR()
else:
    client_socket = RDTSocketSW()
client_socket.connect((args.host, args.port))


# Envio el primer mensaje de configuracion al servidor
# Packet(
#        type: 0 ---> Le estoy pidiendo un archivo
#        size: 0 ---> Deberia enviarle el tamanio del archivo (TODO)
#        name: Pruebas ---> El nombre que tiene que tener la copia del archivo
#       )
packet = Packet(0, 0, args.name.encode()).serialize()
messaje = packet  # + bytearray(1500 - len(packet)) #padding
client_socket.send(messaje)

packet = Packet.fromSerializedPacket(client_socket.recv())

if packet.type == FileTransfer.BUSY_FILE:
    logging.info("The file you are trying to access is currently busy")
    client_socket.closeReceiver()
# Por ultimo llamo al FileTransfer y le pide que:
# Envie el archivo src/test por cliente_socket
try:
    startTime = time.time_ns()
    FileTransfer.recv_file(client_socket, '1', args.dst)
    finishTime = time.time_ns()

    elapsedTime = (finishTime - startTime) / 1000000 # Convert ns to ms
    logging.debug("Finished downloading the file in {:.0f}ms".format(elapsedTime))
except NameNotFoundException:
    logging.debug("El archivo solicitado no existe")
client_socket.closeReceiver()
# El '1' deberia ser ser tu addr en princio
# solo la utilizo para debugging (TODO)
