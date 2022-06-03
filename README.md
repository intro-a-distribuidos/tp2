# Trabajo práctico N°2 File Transfer

### Enunciado
Este trabajo práctico se plantea como objetivo la comprensión y la puesta en práctica de los conceptos y herramientas necesarias para la implementación de un protocolo RDT. Para lograr este objetivo, se deberá desarrollar una aplicación de arquitectura cliente-servidor que implemente la funcionalidad de transferencia de archivos mediante las siguientes operaciones:
* UPLOAD: Transferencia de un archivo del cliente hacia el servidor
* DOWNLOAD: Transferencia de un archivo del servidor hacia el cliente

Dada las diferentes operaciones que pueden realizarse entre el cliente y el servidor, se requiere del diseño e implementación de un protocolo de aplicación básico que especifique los mensajes intercambiados entre los distintos procesos.

### Links útiles

* [Enunciado completo](https://campus.fi.uba.ar/pluginfile.php/311617/mod_folder/content/0/tp_file_transfer_udp_selective_repeat.pdf)
* [Informe en Latex](https://www.overleaf.com/3316582635qsyvscytgbdb)

### start-server.py
Para ejecutar el servidor
```
usage: start-server.py [-h] [-H] [-p] [-s] [-v | -q] [-sr | -sw]

optional arguments:
  -H , --host           service IP address
  -p , --port           server port
  -s , --storage        storage dir path
  -v, --verbose         increase output verbosity
  -q, --quiet           decrease output verbosity
  -sr, --selective-repeat
                        use Selective Repeat as RDT protocol
  -sw, --stop-and-wait  use Stop and Wait as RDT protocol
```
Por defecto el servidor será 127.0.0.1:5050, los archivos se guardarán en 'server_files'. Además, por defecto se ejecuta con Selective Repeat.

### update.py
Para subir un archivo
```
usage: upload.py [-h] [-H] [-p] [-s] [-n] [-v | -q] [-sr | -sw]

optional arguments:
  -H , --host           server IP address
  -p , --port           server port
  -s , --src            source file path
  -n , --name           file name
  -v, --verbose         increase output verbosity
  -q, --quiet           decrease output verbosity
  -sr, --selective-repeat
                        use Selective Repeat as RDT protocol
  -sw, --stop-and-wait  use Stop and Wait as RDT protocol
```
Por defecto el servidor será 127.0.0.1:5050, el archivo que se cargará será 'client_files/default' y será guardado en el servidor como 'default'. Además, por defecto se ejecuta con Selective Repeat.

### download.py
Para descargar un archivo
```
usage: download.py [-h] [-H] [-p] [-d] [-n] [-v] [-q] [-sr | -sw]

optional arguments:
  -H , --host           server IP address
  -p , --port           server port
  -d , --dst            destination file path
  -n , --name           file name
  -v, --verbose         increase output verbosity
  -q, --quiet           decrease output verbosity
  -sr, --selective-repeat
                        use Selective Repeat as RDT protocol
  -sw, --stop-and-wait  use Stop and Wait as RDT protocol
```
Por defecto el servidor será 127.0.0.1:5050, el archivo se descargará en 'client_files/default' y será buscado en el servidor como 'default'. Además, por defecto se ejecuta con Selective Repeat.

### Selective Repeat
En `lib/RDTSocketSR` se encuentran definidas constantes para alterar las ventanas 'WINDOWSIZE=10' y 'INPUT_BUFFER_SIZE=44', al modificarlas se cambiarán los parámetros de la implementación.

### Instalar Comcast
```
# Instalar GO
$ sudo apt install golang

# Instalar comcast

### Forma 1
$ export GO111MODULE=on
$ go get github.com/tylertreat/comcast
$ cd $HOME/go/bin
$ ./comcast --device=lo --packet-loss=50%
...
$ ./comcast --device=lo --stop


### Forma 2
$ cd $HOME/go/src/github.com
$ git clone git@github.com:tylertreat/comcast.git
$ cd tylertreat/comcast
$ go run comcast.go --device=lo --packet-loss=50% 
...
$ go run comcast.go --device=lo --stop
```

### Alternativa a comcast, más divertida
```
sudo iptables -A INPUT -m statistic --mode random --probability 0.3 -j DROP
sudo iptables -A OUTPUT -m statistic --mode random --probability 0.3 -j DROP
sudo iptables --flush
```