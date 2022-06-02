import argparse
import pathlib
import logging
import sys
import os
from FileTransfer import FileTransfer, Packet
from threading import Thread
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
        help='service IP address')
    optionals.add_argument(
        '-p',
        '--port',
        type=int,
        default=5050,
        metavar='',
        help='server port')
    optionals.add_argument(
        '-s',
        '--storage',
        type=pathlib.Path,
        metavar='',
        default='tmp',
        help='storage dir path')

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

SERVER_PORT = 12000
DIR_PATH = "server_files"


def start_server():
    serverSocket = RDTSocketSR()
    serverSocket.bind(('', SERVER_PORT))
    serverSocket.listen(1)
    try:
        os.mkdir(DIR_PATH)
    except BaseException:
        pass

    while True:
        connSocket, addr = serverSocket.accept()
        connThread = Thread(
            target=client_handle, args=(
                connSocket, addr))
        connThread.daemon = True
        logging.debug("Iniciando conexion... addr:{}".format(addr))
        connThread.start()
    return


def client_handle(connSocket, addr):

    bytes = connSocket.recvSelectiveRepeat()

    if (bytes == b''):
        logging.debug("El Cliente corto la conexion")
        connSocket.closeReceiver()
        return

    packet = Packet.fromSerializedPacket(bytes)
    file_size = packet.size
    file_name = packet.name.decode().rstrip("\x00")

    logging.debug(
        "Cliente:{} envio Paquete de config:type->{}, size->{},name->{}".format(
            addr,
            packet.type,
            file_size,
            file_name))

    if packet.type == FileTransfer.RECEIVE:
        logging.debug(
            "Cliente:{}  quiere recibir(RECEIVE) un archivo".format(addr))
        # Si el cliente quiere recibir un archivo -> Servidor debe enviar
        FileTransfer.send_file(connSocket, addr, DIR_PATH + '/' + file_name)
        connSocket.closeSender()

    elif packet.type == FileTransfer.SEND:  # and packet.size < 4GB
        logging.debug(
            "Cliente:{}  quiere enviar(SEND) un archivo".format(addr))
        # Si el cliente quiere enviar un archivo -> Servidor debe recibir
        FileTransfer.recv_file(connSocket, addr, DIR_PATH + '/' + file_name)
        connSocket.closeReceiver()

    else:
        logging.debug(
            "Cliente:{} solicito una operacion INVALIDA".format(addr))
        connSocket.closeReceiver()
        return

    logging.debug(
        "La trasferencia para el cliente {}, realizo con exito".format(addr))
    return


logging.basicConfig(level=logging.DEBUG,  # filename="server.log",
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y/%m/%d %I:%M:%S %p',
                    stream=sys.stdout)

try:
    start_server()
except KeyboardInterrupt:
    print("")
