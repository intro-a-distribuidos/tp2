from ast import Raise
from socket import socket, AF_INET, SOCK_DGRAM, SOCK_STREAM
from threading import Thread
import logging
import struct
import os
from pathlib import Path

from lib.exceptions import NameNotFoundException
from lib.RDTSocketSR import RDTSocketSR, RDT_HEADER_LENGTH


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

    PAYLOAD = MSS - RDT_HEADER_LENGTH
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
                    raise NameNotFoundException
            f.write(bytes)  # TODO: Chequear si es escribe bien.

        f.close()
        logging.debug("{} termino de recibir los archivos".format(addr))
        return

    #   Esta funcion lee de un file y envia de a MSS bytes por el socket
    @classmethod
    def send_file(self, connSocket, addr, file_name):

        try:
            f = open(file_name, 'rb')
        except BaseException:
            logging.debug("No existe el file {}".format(file_name))
            # TODO: Enviar un paquete con el typo 2(error)
            packet = Packet(self.ERROR, 0, file_name.encode()).serialize()
            connSocket.send(packet)
            return

        file_bytes = f.read(self.MSS)
        while file_bytes != b'':

            bytes_sent = connSocket.send(file_bytes)

            if bytes_sent == b'':
                f.close()
                logging.debug(
                    "Se cerró elb socket antes de terminar el enviar, Socket ID:{}".format(connSocket))
                return
            file_bytes = f.read(self.MSS)
        f.close()
        logging.debug("{} termino de enviar los archivos".format(addr))
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
