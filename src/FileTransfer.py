from ast import Raise
from socket import socket, AF_INET, SOCK_DGRAM, SOCK_STREAM
from threading import Thread
import logging
import struct
import os
from pathlib import Path

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

    #   This function receive packets and write payload in the file
    #   sent as argument.
    @classmethod
    def recv_file(self, connSocket, file):
        bytes = b'a'

        while bytes != b'':
            bytes = connSocket.recv()

            if (bytes != b''):
                packet = Packet.fromSerializedPacket(bytes)
                if (packet.type == self.ERROR):
                    # TODO cambiar este nombre poco descriptivo...
                    raise RuntimeError # TODO TODO TODO TODO TODO
                file.write(packet.name)  # TODO: Chequear si es escribe bien.
        return

    @classmethod
    def send_file(self, connSocket, file):
        # TODO quitar de acá el MSS
        file_bytes = file.read(self.MSS)
        while file_bytes != b'':
            packet = Packet(self.OK, 0, file_bytes)
            bytes_sent = connSocket.send(packet.serialize())

            if bytes_sent == b'':
                return
            file_bytes = file.read(self.MSS)

    # Función auxiliar que arma un packet (request) y se lo manda al
    # servidor
    @classmethod
    def request(cls, socket, type, file_name, file_size):
        packet = Packet(type, file_size, file_name.encode()).serialize()
        socket.send(packet)
        return