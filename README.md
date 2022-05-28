# Trabajo práctico N°2 File Transfer

### Enunciado
Este trabajo práctico se plantea como objetivo la comprensión y la puesta en práctica de los conceptos y herramientas necesarias para la implementación de un protocolo RDT. Para lograr este objetivo, se deberá desarrollar una aplicación de arquitectura cliente-servidor que implemente la funcionalidad de transferencia de archivos mediante las siguientes operaciones:
* UPLOAD: Transferencia de un archivo del cliente hacia el servidor
* DOWNLOAD: Transferencia de un archivo del servidor hacia el cliente

Dada las diferentes operaciones que pueden realizarse entre el cliente y el servidor, se requiere del diseño e implementación de un protocolo de aplicación básico que especifique los mensajes intercambiados entre los distintos procesos.

### Links útiles

* [Enunciado completo](https://campus.fi.uba.ar/pluginfile.php/311617/mod_folder/content/0/tp_file_transfer_udp_selective_repeat.pdf)
* [Informe en Latex](https://www.overleaf.com/3316582635qsyvscytgbdb)

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