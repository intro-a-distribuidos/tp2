import argparse
import pathlib
from socket import AF_INET, SOCK_STREAM


from pyrsistent import optional


def getArgs():
    parser = argparse.ArgumentParser()
    parser._action_groups.pop()

    

    optionals = parser.add_argument_group('optional arguments')
    optionals.add_argument(
        '-H',
        '--host',
        type=str,
        metavar='',
        help='server IP address')
    optionals.add_argument(
        '-p',
        '--port',
        type=int,
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

    return parser.parse_args()


args = getArgs()

logging.basicConfig(level=logging.DEBUG, filename="client.log",
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y/%m/%d %I:%M:%S %p')
