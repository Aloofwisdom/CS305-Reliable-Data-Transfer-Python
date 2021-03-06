from socket import socket, AF_INET, SOCK_DGRAM, inet_aton, inet_ntoa
import random, time
import threading, queue
from socketserver import ThreadingUDPServer

lock = threading.Lock()


def bytes_to_addr(bytes):
    return inet_ntoa(bytes[:4]), int.from_bytes(bytes[4:8], 'big')


def addr_to_bytes(addr):
    return inet_aton(addr[0]) + addr[1].to_bytes(4, 'big')


class Server(ThreadingUDPServer):
    def __init__(self, addr, rate=None, delay=None):
        super().__init__(addr, None)
        self.rate = rate
        self.buffer = 0
        self.delay = delay

    def verify_request(self, request, client_address):
        """
        request is a tuple (data, socket)
        data is the received bytes object
        socket is new socket created automatically to handle the request

        if this function returns False， the request will not be processed, i.e. is discarded.
        details: https://docs.python.org/3/library/socketserver.html
        """
        if self.buffer < 48000:  # some finite buffer size (in bytes)
            self.buffer += len(request[0])
            print(self.buffer)
            return True
        else:
            print("BUFFER WARNING!")
            return False

    def finish_request(self, request, client_address):
        data, socket = request

        with lock:
            if self.rate: time.sleep(len(data) / self.rate)
            self.buffer -= len(data)

        loss_rate = 0.01
        corrupt_rate = 0.00001
        if random.random() < loss_rate:
            print('pkt miss')
            return
        for i in range(len(data) - 1):
            data = bytearray(data)
            if random.random() < corrupt_rate:
                print('hhh pkt was corrupt')
                data[i] = random.randint(0, 255)
        data = bytes(data)


        to = bytes_to_addr(data[:8])
        # print(client_address, to)  # observe tht traffic
        socket.sendto(addr_to_bytes(client_address) + data[8:], to)


server_address = ('127.0.0.1', 12345)

if __name__ == '__main__':
    with Server(server_address,10240) as server:
        server.serve_forever()
