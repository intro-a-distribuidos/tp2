import argparse
from socket import socket, AF_INET, SOCK_STREAM
from FileTransfer import FileTransfer, Packet
import logging
from lib.exceptions import ServerUnreachable, LostConnection
import sys
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
        default='file',
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
try:
    f = open(args.src, 'rb')
except:
    logging.debug("Cannot open the file \"{}\"".format(args.src))
    exit(-1)
try:
    if args.rdtType == RDT_SR:
        client_socket = RDTSocketSR()
    else:
        client_socket = RDTSocketSW()

    client_socket.connect((args.host, args.port))

    # we want to upload a file
    queryPacket = Packet(FileTransfer.SEND, 0, args.name.encode()).serialize()
    client_socket.send(queryPacket)

    # server responses if the query was accepted
    responsePacket = Packet.fromSerializedPacket(client_socket.recv())

    if responsePacket.type == FileTransfer.OK:
        FileTransfer.send_ofile(client_socket, (1,1), f)
    else: # responsePacket.type == FileTransfer.BUSY_FILE:
        logging.info("The file you are trying to access is currently busy")
        f.close()
        client_socket.closeReceiver()
        exit()
except ServerUnreachable:
    f.close()
    client_socket.closeReceiver()
    logging.info("Server unreachable...")
    exit()
except LostConnection:
    f.close()
    client_socket.closeReceiver()
    logging.info("Lost connection...")
    exit()
except:
    f.close()
    client_socket.closeReceiver()
    logging.info("Good bye...")
    exit()

f.close()
client_socket.closeSender()
