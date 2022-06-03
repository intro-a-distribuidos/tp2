from ast import Raise
from socket import socket, AF_INET, SOCK_DGRAM, SOCK_STREAM
from threading import Thread
import logging
import struct
import os
from pathlib import Path

from lib.RDTSocketSR import RDTSocketSR, RDTHEADER


class Packet:
    type = 0
    size = 0
    name = ''

    def __init__(self, type, size, name="".encode()):
        self.type = type
        self.size = size
        self.name = name

    def serialize(self):
        return struct.pack("i i {}s".format(len(self.name)),
                           self.type, self.size, self.name)

    @classmethod
    def fromSerializedPacket(cls, serializedPacket):
        packet = struct.unpack("i i", serializedPacket[:8])
        packet = (*packet, serializedPacket[8:])
        return cls(*packet)


SERVER_PORT = 12000


class FileTransfer:
    RECEIVE = 0
    SEND = 1
    ERROR = 2
    OK = 3
    BUSY_FILE = 4
    MSS = 1500

    PAYLOAD = MSS - RDTHEADER
    CONFIG_LEN = 209

    #   Esta funcion lee los paquetes que llegan por el socket y
    #   los escriben en el file enviado por parametro. Si el file
    #   existe lo sobreescribe.

    @classmethod
    def recv_file(self, connSocket, addr, file_name):
        output_file = Path(file_name)
        output_file.parent.mkdir(exist_ok=True, parents=True)
        f = open(file_name, "wb")
        bytes = b'a'

        while bytes != b'':
            bytes = connSocket.recv()

            if (bytes != b''):
                packet = Packet.fromSerializedPacket(bytes)
                if (packet.type == self.ERROR):
                    # TODO cambiar este nombre poco descriptivo...
                    raise RuntimeError
            f.write(bytes)  # TODO: Chequear si es escribe bien.

        f.close()
        logging.debug("{} termino de recibir los archivos".format(addr))
        return

    @classmethod
    def send_ofile(self, connSocket, addr, f):
        # TODO quitar de acá el MSS
        file_bytes = f.read(self.MSS)
        while file_bytes != b'':

            bytes_sent = connSocket.send(file_bytes)

            if bytes_sent == b'':
                logging.info(
                    "Socket({}:{}) closed before the transfer was completed".format(*addr))
                return
            file_bytes = f.read(self.MSS)
        logging.info(
                    "Socket({}:{}) transfer completed successfully".format(*addr))


    # Esta funcion lee de un file y envia de a MSS bytes por el socket
    @classmethod
    def send_file(self, connSocket, addr, file_name):
        try:
            f = open(file_name, 'rb')
        except:
            logging.debug("Cannot open the file \"{}\"".format(file_name))
            packet = Packet(self.ERROR, 0, file_name.encode()).serialize()
            connSocket.send(packet)
            return

        self.send_ofile(connSocket, addr, f)
        f.close()
        return

        # Función auxiliar que arma un packet (request) y se lo manda al
        # servidor
    @classmethod
    def request(cls, socket, type, file_name, file_size):
        packet = Packet(type, file_size, file_name.encode()).serialize()
        socket.send(packet)
        return

    # Un socket cliente que ya haya hecho el connect a un servidor llama a
    # esta función para avisarle que quiere hacer un upload
    def request_upload(self, clientSocket, file_name, file_size):
        self.request(clientSocket, self.SEND, file_name, file_size)
        return

    # Un socket cliente que ya haya hecho el connect a un servidor llama a
    # esta función para avisarle que quiere hacer un download
    def request_download(self, clientSocket, file_name):
        self.request(clientSocket, self.RECEIVE, file_name)
        return
