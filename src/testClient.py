from lib.RDTSocketSR import RDTSocketSR
import logging
import sys
from time import sleep

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y/%m/%d %I:%M:%S %p',
                    stream=sys.stdout)

client_socket = RDTSocketSR()
client_socket.connect(('127.0.0.1', 12000))

client_socket.sendSelectiveRepeat('#1. Bernardo: ¿Quien esta ahi?'.encode())
client_socket.sendSelectiveRepeat('#2. Francisco: No, respondame el a mi. Detengase y diga quien es.'.encode())
client_socket.sendSelectiveRepeat('#3. Bernardo: ¡Viva el Rey!'.encode())
client_socket.sendSelectiveRepeat('#4. Francisco: ¿Es Bernardo?'.encode())
client_socket.sendSelectiveRepeat('#5. Bernardo: El mismo.'.encode())
client_socket.sendSelectiveRepeat('#6. Francisco: Tu eres el mas puntual en venir a la hora.'.encode())
client_socket.sendSelectiveRepeat('#7. Bernardo: Las doce han dado ya; bien puedes ir a recogerte'.encode())
client_socket.sendSelectiveRepeat('#8. Francisco: Te doy mil gracias por la mudanza. Hace un frio que penetra y yo estoy delicado del pecho.'.encode())
client_socket.sendSelectiveRepeat('#9. Bernardo: ¿Has hecho tu guardia tranquilamente?.'.encode())
client_socket.sendSelectiveRepeat('#10. Francisco: Ni un ratón se ha movido.'.encode())
client_socket.sendSelectiveRepeat('#11. Bernardo: Muy bien. Buenas noches. Si encuentras a Horacio y Marcelo, mis compañeros de guardia, diles que vengan presto.'.encode())
client_socket.sendSelectiveRepeat('#12. Francisco: Me parece que los oigo. Alto ahi. ¡Eh! ¿Quien va?'.encode())

sleep(5)

client_socket.close()