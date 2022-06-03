## TESTS:

### Test 1: Subir archivo chico
```sh
# In server terminal
$1 python3 src/start-server.py
# In client terminal
$2 python3 src/upload.py -s client_files/tests/test1/tiny_file -n tests/test1/tiny_file 
$2 md5sum client_files/tests/test1/tiny_file server_files/tests/test1/tiny_file
```

### Test 2: Subir un archivo grande
```sh
# In server terminal
$1 python3 src/start-server.py
# In client terminal
$2 python3 src/upload.py -s client_files/tests/test2/big_file -n tests/test2/big_file
$2 md5sum client_files/tests/test2/big_file server_files/tests/test2/big_file
```

### Test 3: Sobreescribir un archivo que ya existe
```sh
# In server terminal
$1 python3 src/start-server.py
# In client terminal
$2 python3 src/upload.py -s client_files/tests/test3/file -n test/test3/file 
$2 python3 src/upload.py -s client_files/tests/test3/other_file -n test/test3/file
$2 md5sum client_files/tests/test3/other_file server_files/tests/test3/file
```

### Test 4: Bajar archivo 
```sh
# In server terminal
$1 python3 src/start-server.py
# In client terminal
$2 python3 src/download.py -n tests/test4/file -d client_files/tests/test4/my_file
$2 md5sum  client_files/tests/test4/my_file server_files/tests/test4/file
```

### Test 5: Bajar un archivo inexistente
```sh
# In server terminal
$1 python3 src/start-server.py
# In client terminal
$2 python3 src/download.py -n tests/test4/not_existent_file -d client_files/tests/test4/my_file
# "The file you are trying to access doesn't exists"
```

Querer descargar simultaneamente diferentes archivos
Querer descargar simultaneamente el mismo archivo
Querer cargar simultaneamente hacia diferentes paths
Querer cargar simultaneamente hacia mismo path
Cargar y subir diferentes archivos (o sea no cargar sobre el que quiero descargar)
	Subir y cargar (dar vuelta la ejecución de los clientes)
Cargar y subir el mismo archivo
	Subir y cargar (dar vuelta la ejecución de los clientes)

# Doc tests
Comparar SW vs SR