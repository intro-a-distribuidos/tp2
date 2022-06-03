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
    data = ''

    def __init__(self, type, data="".encode()):
        self.type = type
        self.data = data

    def serialize(self):
        return struct.pack("i {}s".format(len(self.data)),
                           self.type, self.data)

    @classmethod
    def fromSerializedPacket(cls, serializedPacket):
        packet = struct.unpack("i ", serializedPacket[:4])
        packet = (*packet, serializedPacket[4:])
        return cls(*packet)


SERVER_PORT = 12000


class FileTransfer:
    RECEIVE = 0
    SEND = 1
    ERROR = 2
    OK = 3
    BUSY_FILE = 4
    MSS = 1500
    CONFIG_LEN = 209
    HEADER_PACKET = 4
    PAYLOAD = MSS - RDT_HEADER_LENGTH - HEADER_PACKET

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
                    raise RuntimeError  # TODO TODO TODO TODO TODO
                file.write(packet.data)
        return

    @classmethod
    def send_file(self, connSocket, file):
        file_bytes = file.read(self.PAYLOAD)
        while file_bytes != b'':
            packet = Packet(self.OK, file_bytes)
            bytes_sent = connSocket.send(packet.serialize())

            if bytes_sent == b'':
                return
            file_bytes = file.read(self.PAYLOAD)

    #   Send a request for the socket
    @classmethod
    def request(cls, socket, type, data):
        packet = Packet(type, data.encode()).serialize()
        socket.send(packet)
        return
