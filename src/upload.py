import argparse
from socket import socket, AF_INET, SOCK_DGRAM
from lib.rdtsocket import RDTsocket
import logging

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

logging.basicConfig(level=logging.DEBUG, filename="client.log",
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y/%m/%d %I:%M:%S %p')

clientSocket = RDTsocket()
clientSocket.connect((args.host, args.port))
clientSocket.close()
