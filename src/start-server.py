import argparse
import pathlib
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

logging.basicConfig(level=logging.DEBUG, filename="server.log",
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y/%m/%d %I:%M:%S %p')

serverSocket = RDTsocket()
serverSocket.bind((args.host, args.port))
serverSocket.listen(1)
logging.debug("Server listening on port {0}".format(args.port))
connectionSocket, addr = serverSocket.accept()
print("socket accepted with addr:", addr)

connectionSocket.close()
serverSocket.close()




