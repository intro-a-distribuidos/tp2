import argparse


def getArgs():
    parser = argparse.ArgumentParser()
    parser._action_groups.pop()

    required = parser.add_argument_group('required arguments')
    required.add_argument(
        '-H',
        '--host',
        type=str,
        required=True,
        metavar='',
        help='server IP address')
    required.add_argument(
        '-p',
        '--port',
        type=int,
        required=True,
        metavar='',
        help='server port')
    required.add_argument(
        '-s',
        '--src',
        type=str,
        required=True,
        metavar='',
        help='source file path')
    required.add_argument(
        '-n',
        '--name',
        type=str,
        required=True,
        metavar='',
        help='file name')

    optionals = parser.add_argument_group('optional arguments')

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
print(args.host)
"""

> python upload -h
usage : upload [ - h ] [ - v | -q ] [ - H ADDR ] [ - p PORT ] [ - s FILEPATH ] [ - n FILENAME ]
< command description >
optional arguments :
-h , -- help show this help message and exit
-v , -- verbose increase output verbosity
-q , -- quiet decrease output verbosity
-H , -- host server IP address
-p , -- port server port
-s , -- src source file path
-n , -- name file name

"""
