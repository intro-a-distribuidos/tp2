import argparse
from socket import socket, AF_INET, SOCK_STREAM
from FileTransfer import FileTransfer, Packet
import logging

import sys
from lib.RDTSocketSR import RDTSocketSR


def getArgs():
    parser = argparse.ArgumentParser()
    parser._action_groups.pop()

    optionals = parser.add_argument_group('optional arguments')
    optionals.add_argument(
        '-H',
        '--host',
        type=str,
        metavar='',
        default='',
        help='server IP address')
    optionals.add_argument(
        '-p',
        '--port',
        type=int,
        metavar='',
        default=5050,
        help='server port')
    optionals.add_argument(
        '-s',
        '--src',
        type=str,
        metavar='',
        default='',
        help='source file path')
    optionals.add_argument(
        '-n',
        '--name',
        type=str,
        metavar='',
        default='file',
        help='file name')

    group = optionals.add_mutually_exclusive_group()
    group.add_argument(
        '-v',
        '--verbose',
        action='store_const',
        dest='verboseLevel',
        const=3,
        default=2,
        metavar='',
        help='increase output verbosity')
    group.add_argument(
        '-q',
        '--quiet',
        action='store_const',
        dest='verboseLevel',
        const=1,
        default=2,
        metavar='',
        help='decrease output verbosity')

    return parser.parse_args()


args = getArgs()

logging.basicConfig(level=logging.DEBUG,  # filename="client.log",
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y/%m/%d %I:%M:%S %p',
                    stream=sys.stdout)

###############################################################
#   Esto es un ejemplo de como funcionaria subir un archivo   #
#   al directorio del servidor.                               #
###############################################################


# Me creo que socket que me intento conectar con el servidor
client_socket = RDTSocketSR()
client_socket.connect(('127.0.0.1', 12000))


# Envio el primer mensaje de configuracion al servidor
# Packet(
#        type: 1 ---> Le estoy avisando que voy a enviarle un archivo
#        size: 0 ---> Deberia enviarle el tamanio del archivo (TODO)
#        name: Pruebas ---> El nombre que tiene que tener la copia del archivo
#       )
packet = Packet(
    1,
    0,
    'HisLorem.txt'.encode()).serialize()
messaje = packet  # + bytearray(1500 - len(packet)) #padding
client_socket.sendSelectiveRepeat(messaje)

# Por ultimo llamo al FileTransfer y le pide que:
# Envie el archivo src/test por cliente_socket

FileTransfer = FileTransfer()
FileTransfer.send_file(
    client_socket,
    '1',
    'client_files/test')
client_socket.close()
# El '1' deberia ser ser tu addr en princio
# solo la utilizo para debugging (TODO)
