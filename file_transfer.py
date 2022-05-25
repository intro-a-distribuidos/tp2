from socket import socket, AF_INET, SOCK_DGRAM, SOCK_STREAM 
from threading import Thread
import logging
import struct


class file_transfer:
    #path = path donde vamos a dejar los files

   
    def start_server(self):
        #Creamos server y lo ponemos a escuchar
        server_socket = socket(AF_INET,SOCK_STREAM)
        server_socket.bind('',12000)
        server_socket.listen()

        while True:
            connSocket , addr = server_socket.accept()
            connThread = Thread(target=self.client_handle,args=(connSocket,addr))
            connThread.daemon = True #Cierra con el thread principal
            logging.debug("Iniciando conexion... addr:{}".format(addr))
            connThread.start()
            #TODO: Salir elegantemente

        return

    def client_handle(self,connSocket, addr):
        # receive: tuki
        # decode
        # llamar a receive_file o a send_file
        CONFIG_LEN = 205
        config_msg = []
        bytes_totales_recibidos = 0
     
        while bytes_totales_recibidos < CONFIG_LEN: 
            bytes_recibidos = connSocket.recv(CONFIG_LEN)
            config_msg.append(bytes_recibidos)
            bytes_totales_recibidos += len(bytes_recibidos)

        op = struct.unpack("c",config_msg[0])
        file_len = struct.unpack("i",config_msg[1:5])
        file_name = config_msg[5:]

        return

    def receive_file(self):
        return

    def send_file(self):
        return
    