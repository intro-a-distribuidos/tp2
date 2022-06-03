## TESTS:

### Test 1: Subir archivo chico
```sh
# In server terminal
python3 src/start-server.py
# In client terminal
python3 src/upload.py -s client_files/tests/test1/tiny_file -n tests/test1/tiny_file 
md5sum client_files/tests/test1/tiny_file server_files/tests/test1/tiny_file

rm server_files/tests/test1/tiny_file
```

### Test 2: Subir un archivo grande
```sh
# In server terminal
python3 src/start-server.py
# In client terminal
python3 src/upload.py -s client_files/tests/test2/big_file -n tests/test2/big_file
md5sum client_files/tests/test2/big_file server_files/tests/test2/big_file

rm server_files/tests/test2/big_file
```

### Test 3: Sobreescribir un archivo que ya existe
```sh
# In server terminal
python3 src/start-server.py
# In client terminal
python3 src/upload.py -s client_files/tests/test3/file -n tests/test3/file 
md5sum client_files/tests/test3/file server_files/tests/test3/file

python3 src/upload.py -s client_files/tests/test3/other_file -n tests/test3/file
md5sum client_files/tests/test3/other_file server_files/tests/test3/file

rm server_files/tests/test3/file
```

### Test 4: descargar archivo 
```sh
# In server terminal
python3 src/start-server.py
# In client terminal
python3 src/download.py -n tests/test4/file -d client_files/tests/test4/my_file
md5sum client_files/tests/test4/my_file server_files/tests/test4/file

rm client_files/tests/test4/my_file
```

### Test 5: descargar un archivo inexistente
```sh
# In server terminal
python3 src/start-server.py
# In client terminal
python3 src/download.py -n tests/test5/not_existent_file -d client_files/tests/test5/my_file
# "The file you are trying to access cannot open"
```

### Test 6: Descargar simultaneamente diferentes archivos
```sh
# In server terminal:
python3 src/start-server.py
# In client terminal 1:
python3 src/download.py -n tests/test6/file_1 -d client_files/tests/test6/file_1
md5sum client_files/tests/test6/file_1 server_files/tests/test6/file_1

rm client_files/tests/test6/file_1
# In client terminal 2:
python3 src/download.py -n tests/test6/file_2 -d client_files/tests/test6/file_2
md5sum client_files/tests/test6/file_2 server_files/tests/test6/file_2

rm client_files/tests/test6/file_2
```

### Test 7: Descargar simultaneamente el mismo archivo
```sh
# In server terminal:
python3 src/start-server.py
# In client terminal 1:
python3 src/download.py -n tests/test7/file_1 -d client_files/tests/test7/file_1
md5sum client_files/tests/test7/file_1 server_files/tests/test7/file_1

rm client_files/tests/test7/file_1
# In client terminal 2:
python3 src/download.py -n tests/test7/file_1 -d client_files/tests/test7/file_2
# logging.info("The file you are trying to access is currently busy")
```

### Test 8: Cargar simultaneamente hacia diferentes paths
```sh
# In server terminal
python3 src/start-server.py
# In client terminal 1
python3 src/upload.py -s client_files/tests/test8/file_client1 -n tests/test8/file_client1
md5sum client_files/tests/test8/file_client1 server_files/tests/test8/file_client1

rm server_files/tests/test8/file_client1
# In client terminal 2
python3 src/upload.py -s client_files/tests/test8/file_client2 -n tests/test8/file_client2
md5sum client_files/tests/test8/file_client2 server_files/tests/test8/file_client2

rm server_files/tests/test8/file_client2
```

### Test 9: Cargar simultaneamente hacia mismo path
```sh
# In server terminal
python3 src/start-server.py
# In client terminal 1
python3 src/upload.py -s client_files/tests/test9/file_client1 -n tests/test9/file
md5sum client_files/tests/test9/file_client1 server_files/tests/test9/file

rm server_files/tests/test9/file
# In client terminal 2
python3 src/upload.py -s client_files/tests/test9/file_client2 -n tests/test9/file
# logging.info("The file you are trying to access is currently busy")
```

### Test10: Cargar y subir diferentes archivos en simultaneo
```sh
# In server terminal
python3 src/start-server.py
# In client terminal 1
python3 src/upload.py -s client_files/tests/test10/file_client1_upload -n tests/test10/file_client1
md5sum client_files/tests/test10/file_client1_upload server_files/tests/test10/file_client1

python3 src/download.py -n tests/test10/file_client1 -d client_files/tests/test10/file_client1_download
md5sum client_files/tests/test10/file_client1_download server_files/tests/test10/file_client1

rm server_files/tests/test10/file_client1
rm client_files/tests/test10/file_client1_download
# In client terminal 2
python3 src/download.py -n tests/test10/file_client2 -d client_files/tests/test10/file_client2_download
md5sum  client_files/tests/test10/file_client2_download server_files/tests/test10/file_client2

python3 src/upload.py -s client_files/tests/test10/file_client2_upload -n tests/test10/file_client2
md5sum  client_files/tests/test10/file_client2_upload server_files/tests/test10/file_client2

rm client_files/tests/test10/file_client2_download
```

### Test11: Cargar y subir el mismo archivo
```sh
# In server terminal
python3 src/start-server.py
# In client terminal 1
python3 src/upload.py -s client_files/tests/test11/file_upload -n tests/test11/file
md5sum client_files/tests/test11/file_upload server_files/tests/test11/file

rm server_files/tests/test11/file
# In client terminal 2
python3 src/download.py -n tests/test11/file -d client_files/tests/test11/file_client2_download
# logging.info("The file you are trying to access is currently busy")
```



# Doc tests
Comparar SW vs SR