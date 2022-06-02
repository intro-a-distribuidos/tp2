import argparse
import logging
import sys
import os

from FileTransfer import FileTransfer, Packet
from threading import Thread, Lock
from lib.RDTSocketSR import RDTSocketSR
from lib.RDTSocketSW import RDTSocketSW

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
        type=str,
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

connections = []
openFiles = []
lockOpenFiles = Lock()


def start_server(serverSocket):
    serverSocket.bind((args.host, args.port))
    serverSocket.listen(1)
    try:
        os.makedirs(args.storage)
    except FileExistsError:
        pass
    except:
        raise

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

    bytes = connSocket.recv()

    if (bytes == b''):
        logging.debug("El Cliente corto la conexion")
        connSocket.closeReceiver()
        return

    packet = Packet.fromSerializedPacket(bytes)
    file_size = packet.size
    file_name = packet.name.decode()
    logging.debug(
        "Cliente:{} envio Paquete de config:type->{}, size->{},name->{}".format(
            addr,
            packet.type,
            file_size,
            file_name))


    lockOpenFiles.acquire()
    if file_name in openFiles:
        FileTransfer.request(connSocket,FileTransfer.BUSY_FILE,file_name,0)
        lockOpenFiles.release()
        connSocket.closeReceiver()
        return

    else:
        openFiles.append(file_name)
        FileTransfer.request(connSocket,FileTransfer.OK,file_name,0)
    lockOpenFiles.release()



    if packet.type == FileTransfer.RECEIVE:
        logging.debug(
            "Cliente:{}  quiere recibir(RECEIVE) un archivo".format(addr))
        # Si el cliente quiere recibir un archivo -> Servidor debe enviar
        connections.append((connSocket,FileTransfer.SEND))
        FileTransfer.send_file(connSocket, addr, args.storage + '/' + file_name) 
        connSocket.closeSender()

    elif packet.type == FileTransfer.SEND:  # and packet.size < 4GB
        logging.debug(
            "Cliente:{}  quiere enviar(SEND) un archivo".format(addr))
        # Si el cliente quiere enviar un archivo -> Servidor debe recibir
        connections.append((connSocket,FileTransfer.RECEIVE))
        FileTransfer.recv_file(connSocket, addr, args.storage + '/' + file_name) 
        connSocket.closeReceiver()

    else:
        logging.debug(
            "Cliente:{} solicito una operacion INVALIDA".format(addr))
        connSocket.closeReceiver()
        return

    lockOpenFiles.acquire()
    openFiles.remove(file_name)
    lockOpenFiles.release()

    logging.debug(
        "La trasferencia para el cliente {}, realizo con exito".format(addr))
    return


logging.basicConfig(level=logging.DEBUG, # filename="server.log",
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y/%m/%d %I:%M:%S %p',
                    stream=sys.stdout)

serverSocket = None
try:
    if  args.rdtType == RDT_SR:
        serverSocket = RDTSocketSR()
    else:
        serverSocket = RDTSocketSW()
    logging.info("Server: Welcome!!!")
    start_server(serverSocket)
except KeyboardInterrupt:
    print("")
    logging.info("Server: Goodbye!!!")
    for conn,type in connections:
        try:
            if type == FileTransfer.SEND:
                conn.closeSender()
            else:
                conn.closeReceiver()
        except KeyboardInterrupt:
            print("")
            exit()
    serverSocket.closeServer()
except:
    serverSocket.closeServer()
    exit()