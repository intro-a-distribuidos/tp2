from socket import socket, AF_INET, SOCK_DGRAM, SOCK_STREAM 
from threading import Thread
import logging
import struct
import os


class file_transfer:
    dir_path = "server_files"
    UPLOAD = 0
    DOWNLOAD = 1
    MSS = 1500 

   
    def start_server(self):
        #Creamos server y lo ponemos a escuchar
        server_socket = socket(AF_INET,SOCK_STREAM)
        server_socket.bind('',12000)
        server_socket.listen()
        #Creamos directorio
        try:
            os.mkdir(self.dir_path)
        except:
            pass

        while True:
            connSocket , addr = server_socket.accept()
            connThread = Thread(target=self.client_handle,args=(connSocket,addr))
            connThread.daemon = True #Cierra con el thread principal
            logging.debug("Iniciando conexion... addr:{}".format(addr))
            connThread.start()
            #TODO: Salir elegantemente

        return

    def client_handle(self,connSocket, addr):
        CONFIG_LEN = 209
        config_msg = []
        bytes_totales_recibidos = 0
     
        while bytes_totales_recibidos < CONFIG_LEN: 
            bytes_recibidos = connSocket.recv(CONFIG_LEN)
            config_msg.append(bytes_recibidos)
            bytes_totales_recibidos += len(bytes_recibidos)

        op = struct.unpack("c",config_msg[0])
        file_size = struct.unpack("q",config_msg[1:9])
        file_name = config_msg[9:]

        if op == self.UPLOAD:
            logging.debug("Operación es RECEIVE")
            self.upload_file(connSocket,file_name,file_size)
        elif op == self.DOWNLOAD:
            logging.debug("Operación es SEND")
            self.download_file(connSocket,file_name)
        else:
            logging.debug("Mensaje inválido")
            connSocket.close()
            raise RuntimeError("Operación no tiene un valor válido")
        return

    def upload_file(self,connSocket,file_name,file_size):
        #Creamos el file, si ya existe lo sobreescribimos. 
        file_path = self.dir_path + "/" + file_name
        f = open(file_path,"wb")

        SIZE = file_size
        bytes_totales_recibidos = 0
     
        logging.debug("Iniciando upload")
        while bytes_totales_recibidos < SIZE: 
            bytes_recibidos = connSocket.recv(self.MSS)
            
            #Se cerró el socket antes de terminar el upload
            if bytes_recibidos == b'':
                logging.debug("Se cerró el socket antes de terminar el upload, Socket ID:{}".format(connSocket))
                connSocket.close()
                f.close()
                os.remove(file_path)
                return
            
            f.write(bytes_recibidos)
            bytes_totales_recibidos += len(bytes_recibidos)

        logging.debug("Terminado el upload de: {}".format(file_name))
        f.close()
        connSocket.close()
        return

    def download_file(self,connSocket,file_name):

        bytes_totales_enviados = 0
        file_path = self.dir_path + "/" + file_name
        
        #Intentamos abrir el archivo para descargar
        try:
            f = open(file_path,"rb")
        except:
            logging.debug("No existe el file {} para descargar".format(file_name))
            print("No existe el file:" + file_name)
            return

        SIZE = os.path.getsize(file_path)
     
        logging.debug("Iniciando download")
        while bytes_totales_enviados < SIZE: 

            bytes_leidos = f.read(self.MSS)
            bytes_enviados = self.send_MSS(bytes_leidos,connSocket)
            
            #Se cerró el socket antes de terminar el upload
            if bytes_enviados == b'':
                logging.debug("Se cerró el socket antes de terminar el download, Socket ID:{}".format(connSocket))
                connSocket.close()
                f.close()
                return

            
            bytes_totales_enviados += len(bytes_enviados)

        f.close()
        connSocket.close()
        return


    # Funcion auxiliar para download file
    # Manda un MSS al cliente
    def send_MSS(self,msg,connSocket):
        bytes_enviados_totales = 0
        while bytes_enviados_totales < self.MSS:
            bytes_enviados = connSocket.send(msg)
            if bytes_enviados == b'':
                return bytes_enviados
            bytes_enviados_totales += bytes_enviados

        return bytes_enviados
    