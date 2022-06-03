import argparse
import logging
import sys
import os

from FileTransfer import FileTransfer, Packet
from threading import Thread, Lock
from lib.RDTSocketSR import RDTSocketSR
from lib.RDTSocketSW import RDTSocketSW
from lib.exceptions import LostConnection

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
        default='server_files',
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
        help='use Selective Repeat as RDT protocol')
    rdt.add_argument(
        '-sw',
        '--stop-and-wait',
        action='store_const',
        dest='rdtType',
        const=RDT_SW,
        default=1,
        metavar='',
        help='use Stop and Wait as RDT protocol')

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
        logging.info("New connection with {}:{}".format(*addr))
        connThread.start()
    return


def client_handle(connSocket, addr):

    bytes = connSocket.recv()

    if (bytes == b''):
        logging.info("Client({}:{}) shut down the connection".format(*addr))
        connSocket.closeReceiver()
        return

    packet = Packet.fromSerializedPacket(bytes)
    file_size = packet.size
    file_name = packet.name.decode()
    logging.info(
        "Client({}:{}) want to {} a file named \"{}\"".format(
            addr[0],
            addr[1],
            'download' if packet.type == 0 else 'upload',
            file_name))


    lockOpenFiles.acquire()
    if file_name in openFiles:
        logging.info("Client({}:{}) want to use a busy file, sending error".format(*addr))
        FileTransfer.request(connSocket,FileTransfer.BUSY_FILE,file_name,0)
        lockOpenFiles.release()
        connSocket.closeReceiver()
        return
    try:
        file = open(args.storage + '/' + file_name, 'rb' if packet.type == FileTransfer.RECEIVE else 'wb')
    except:
        logging.debug("Client({}:{}) Cannot open the file \"{}\"".format(addr[0], addr[1], args.storage + '/' + file_name))
        FileTransfer.request(connSocket,FileTransfer.ERROR, file_name, 0)
        lockOpenFiles.release()
        connSocket.closeReceiver()
        return

    openFiles.append(file_name)
    logging.info("Client({}:{}) beginning transaction".format(*addr))
    FileTransfer.request(connSocket,FileTransfer.OK,file_name,0)
    lockOpenFiles.release()

    if packet.type == FileTransfer.RECEIVE:
        # If the client want to receive a file, then the server send packets
        connections.append((connSocket,FileTransfer.SEND))
        try:
            FileTransfer.send_file(connSocket, file)
            connSocket.closeSender()
            logging.info("Client({}:{}) download completed".format(*addr))
        except LostConnection:
            logging.info("Client({}:{}) Lost connection".format(*addr))
            connSocket.closeReceiver()

    elif packet.type == FileTransfer.SEND:  # and packet.size < 4GB
        # If the client want to send a file, then the server receive packets
        connections.append((connSocket,FileTransfer.RECEIVE))
        try:
            FileTransfer.recv_file(connSocket, file)
            logging.info("Client({}:{}) upload completed".format(*addr))
        except LostConnection:
            logging.info("Client({}:{}) Lost connection, removing incompleted file")
            os.remove(args.storage + '/' + file_name)
        connSocket.closeReceiver()

    else:
        logging.info("Client({}:{}) sent an invalid operation")
        file.close()
        connSocket.closeReceiver()
        return

    file.close()
    lockOpenFiles.acquire()
    openFiles.remove(file_name)
    lockOpenFiles.release()
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
except BaseException: # KeyboardInterrupt, SystemExit...
    print("")
    logging.info("Server: Goodbye!!!")
    for conn,type in connections:
        try:
            if type == FileTransfer.SEND:
                conn.closeReceiver()
            else:
                conn.closeReceiver()
        except BaseException: # KeyboardInterrupt, SystemExit...
            print("")
            exit()
    serverSocket.closeServer()
except:
    serverSocket.closeServer()
    exit()