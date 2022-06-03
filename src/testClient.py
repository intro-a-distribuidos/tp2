from lib.RDTSocketSR import RDTSocketSR
import logging
import sys
from time import sleep

from lib.exceptions import LostConnection

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y/%m/%d %I:%M:%S %p',
                    stream=sys.stdout)

client_socket = RDTSocketSR()
client_socket.connect(('127.0.0.1', 12000))
try:
    client_socket.send(
        '#1. Bernardo: ¿Quien esta ahi?'.encode())

    client_socket.send(
        '#2. Francisco: No, respondame el a mi. Detengase y diga quien es.'.encode())

    client_socket.send('#3. Bernardo: ¡Viva el Rey!'.encode())

    client_socket.send('#4. Francisco: ¿Es Bernardo?'.encode())

    client_socket.send('#5. Bernardo: El mismo.'.encode())

    client_socket.send(
        '#6. Francisco: Tu eres el mas puntual en venir a la hora.'.encode())

    client_socket.send(
        '#7. Bernardo: Las doce han dado ya; bien puedes ir a recogerte'.encode())

    client_socket.send(
        '#8. Francisco: Te doy mil gracias por la mudanza. Hace un frio que penetra y yo estoy delicado del pecho.'.encode())

    client_socket.send(
        '#9. Bernardo: ¿Has hecho tu guardia tranquilamente?.'.encode())

    client_socket.send(
        '#10. Francisco: Ni un ratón se ha movido.'.encode())

    client_socket.send(
        '#11. Bernardo: Muy bien. Buenas noches. Si encuentras a Horacio y Marcelo, mis compañeros de guardia, diles que vengan presto.'.encode())

    client_socket.send(
        '#12. Francisco: Me parece que los oigo. Alto ahi. ¡Eh! ¿Quien va?'.encode())

except LostConnection:
    logging.info("Could not reach the server, closing connection")

client_socket.closeSender()
