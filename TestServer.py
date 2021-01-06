from rdt import RDTSocket

SERVER_ADDR = '127.0.0.1'
SERVER_PORT = 7070

server = RDTSocket(102400)
server.bind((SERVER_ADDR, SERVER_PORT))
print('Server is ready')

while True:
    print("======================accept=========================")
    conn, client = server.accept()
    print("======================recv=========================")
    data = conn.recv(2048)
    # print(data.decode())
    if not data:
        break
    print("======================send client the msg received=========================")
    # conn.send(data)
    print("======================close=========================")
    conn.close()
