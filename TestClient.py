import time

from rdt import RDTSocket
from TestData import TEST1
SERVER_ADDR = '127.0.0.1'
SERVER_PORT = 7070
BUFFER_SIZE = 2048

DATA = ""
with open("alice.txt") as f:
    DATA = f.read()

start_time = time.time()

MESSAGE = bytes(DATA, encoding='UTF-8')

client = RDTSocket(102400)
client.connect((SERVER_ADDR, SERVER_PORT))
print("======================send data=========================")
client.send(MESSAGE)
print("======================recv data=========================")
data = client.recv(BUFFER_SIZE)
# print(data.decode())
print("======================TIME=========================")
print(time.time() - start_time)
assert data == MESSAGE, 'Error'
print("Success\n")
print("======================close=========================")
client.close()

