from socket import socket, AF_INET, SOCK_DGRAM, SOCK_STREAM
from threading import Thread
import logging
import struct
import os

from lib.RDTSocket import RDTSocket


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
    DIR_PATH = "server_files"
    RECEIVE = 0
    SEND = 1
    MSS = 1500
    CONFIG_LEN = 209

    def start_server(self):
        # Creamos server y lo ponemos a escuchar
        """
        server_socket = socket(AF_INET,SOCK_STREAM)
        server_socket.bind(('',12000))
        server_socket.listen()
        """
        serverSocket = RDTSocket()
        serverSocket.bind(('', SERVER_PORT))
        serverSocket.listen(1)
        try:
            os.mkdir(self.dir_path)
        except BaseException:
            pass

        while True:
            connSocket, addr = serverSocket.accept()
            connThread = Thread(
                target=self.client_handle, args=(
                    connSocket, addr))
            connThread.daemon = True
            logging.debug("Iniciando conexion... addr:{}".format(addr))
            connThread.start()
            # TODO: Salir elegantemente
        return

    def client_handle(self, connSocket, addr):

        bytes = connSocket.recvStopAndWait(self.MSS)

        if (bytes == b''):
            logging.debug("El Cliente corto la conexion")
            connSocket.close()
            return

        packet = Packet.fromSerializedPacket(bytes)
        file_size = packet.size
        file_name = packet.name.decode().rstrip("\x00")

        logging.debug(
            "Cliente:{} envio Paquete de config:type->{}, size->{},name->{}".format(
                addr, packet.type, file_size, file_name))

        if packet.type == self.RECEIVE:
            logging.debug(
                "Cliente:{}  quiere recibir(RECEIVE) un archivo".format(addr))
            # Si el cliente quiere recibir un archivo -> Servidor debe enviar
            # self.send_file(connSocket,addr,file_name)

        elif packet.type == self.SEND:  # and packet.size < 4GB
            logging.debug(
                "Cliente:{}  quiere enviar(SEND) un archivo".format(addr))
            # Si el cliente quiere enviar un archivo -> Servidor debe recibir
            self.recv_file(connSocket, addr, self.DIR_PATH + '/' + file_name)

        else:
            logging.debug(
                "Cliente:{} solicito una operacion INVALIDA".format(addr))
            connSocket.close()
            return

        logging.debug(
            "La trasferencia para el cliente {}, realizo con exito".format(addr))
        connSocket.close()
        return

    #   Esta funcion lee los paquetes que llegan por el socket y
    #   los escriben en el file enviado por parametro. Si el file
    #   existe lo sobreescribe.
    def recv_file(self, connSocket, addr, file_name):

        f = open(file_name, "w")
        bytes = b'a'

        while bytes != b'':
            bytes = connSocket.recvStopAndWait(self.MSS)
            f.write(bytes.decode())  # TODO: Chequear si es escribe bien.

        f.close()
        logging.debug("{} termino de recibir los archivos".format(addr))
        return

    #   Esta funcion lee de un file y envia de a MSS bytes por el socket
    def send_file(self, connSocket, addr, file_name):

        try:
            f = open(file_name, 'r')
        except BaseException:
            logging.debug("No existe el file {}".format(file_name))
            # TODO: Enviar un paquete con el typo 2(error)
            return

        file_bytes = f.read(self.MSS)
        while file_bytes != '':

            bytes_sent = connSocket.sendStopAndWait(file_bytes.encode())

            if bytes_sent == b'':
                f.close()
                logging.debug(
                    "Se cerró el socket antes de terminar el enviar, Socket ID:{}".format(connSocket))
                return
            file_bytes = f.read(self.MSS)
        f.close()
        logging.debug("{} termino de enviar los archivos".format(addr))
        return

        # Función auxiliar que arma un packet (request) y se lo manda al
        # servidor
    def request(self, clientSocket, type, file_name, file_size=0):
        packet = Packet(type, file_size, file_name)
        packet = packet.serialize()

        b_enviados = 0
        while b_enviados < len(packet):
            b_enviados += clientSocket.send(packet)
            if b_enviados == b'':
                logging.debug(
                    "Error al enviar el request del socket {}".format(clientSocket))
                break
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
