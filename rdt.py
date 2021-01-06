"""
Author Jiahong Xiang
SID 11812613
"""
import math
import random
from socket import timeout
from USocket import UnreliableSocket
from ast import literal_eval
import threading
import time

TIME_OUT = 1.6
PKT_SIZE = 512
WND_SIZE = 3
client_isn = 3
server_isn = 0
CONGESTION = 0.001


def CONGESTION_CONTROL(ACK_NUM, SEND_WND):
    if ACK_NUM < SEND_WND * 0.1:
        return 1.8
    elif ACK_NUM < SEND_WND * 0.3:
        return 1.6
    elif ACK_NUM < SEND_WND * 0.6:
        return 1.4
    elif ACK_NUM < SEND_WND * 0.8:
        return 1.2
    elif ACK_NUM < SEND_WND * 0.9:
        return 0.9
    else:
        return 0.8
    pass


class RDTSocket(UnreliableSocket):

    def __init__(self, rate=None, debug=True):
        super().__init__(rate=rate)
        self._rate = rate
        self.debug = debug
        self.address = None
        self.WND_SIZE = 128

    def accept(self):  # -> (RDTSocket, (str, int)):
        while True:
            # receive syn
            data, addr = super().recvfrom(2048)
            header = getHeader(data)
            if self.debug:
                print("first handshaking: {}".format(header))
            if header['syn'] == 1:
                conn = RDTSocket(self._rate)
                conn.address = addr
                server_addr = self.getsockname()
                conn.bind((server_addr[0], server_addr[1] + random.randint(1, 50000)))
                while True:
                    # send syn, ack
                    conn.sendto(genPKT(1, 0, 0, server_isn, header['seq'] + 1, 0), addr)
                    # receive ack
                    conn_header = getHeader(conn.recvfrom(2048)[0])
                    if (conn_header['syn'] == 0 and conn_header['seq_ack'] == server_isn + 1) or \
                            (conn_header['syn'] == 1 and conn_header['fin'] == 1 and conn_header['ack'] == 1):
                        if self.debug:
                            print('third handshaking: {}\n<Connection setup>\n'.format(conn_header))
                        return conn, conn.address

    def connect(self, addr: (str, int)):
        while True:
            # send syn
            self.sendto(genPKT(1, 0, 0, client_isn, 0, 0), addr)
            # receive syn, ack
            data, address = super().recvfrom(2048)
            header = getHeader(data)
            if self.debug:
                print("second handshaking: {}".format(header))
            if header['syn'] == 1:
                for i in range(5):
                    self.sendto(genPKT(0, 0, 0, header['seq_ack'], header['seq'] + 1, 0), address)  # send ack
                    time.sleep(0.1)
                self.address = address
                if self.debug:
                    print('<Connection setup>\n')
                break

    # (syn, fin, ack, seq, seq_ack, length):
    def send(self, msg: bytes):
        global CONGESTION
        SEND_WND = 128
        # the number of slices for sending
        pktBufferSize = math.ceil(len(msg) / PKT_SIZE)
        super().settimeout(TIME_OUT)
        while True:
            try:
                # tell the recv how many slice need to recv
                self.sendto(genPKT(1, 1, 1, pktBufferSize, 0, 0), self.address)
                while True:
                    data, addr = super().recvfrom(2048)
                    if addr != self.address:
                        continue
                    header = getHeader(data)
                    # if recv other status: like recv request -> the ack pkt missed so just break to next status
                    if not check(data) or header['syn'] != 1 or header['fin'] != 0 or header['ack'] != 1:
                        break
                    if not check(data) or header['syn'] != 1 or header['fin'] != 1 or header['ack'] != 0:
                        continue
                    # print('<send 1> header :{0}'.format(header))
                    break
                break
            except timeout:
                continue
        while True:
            try:
                # get the query from recv
                data, addr = super().recvfrom(2048)
                if addr != self.address:
                    continue
                header = getHeader(data)
                # if recv other status: like recv request -> the ack pkt missed so just break to next status
                if check(data) and header['syn'] == 1 and header['fin'] == 1 and header['ack'] == 1:
                    break
                if check(data) and header['syn'] == 0 and header['fin'] == 1 and header['ack'] == 0:
                    return b''
                if not check(data) or header['syn'] != 1 or header['fin'] != 0 or header['ack'] != 1:
                    continue
                ACK_NUM = header['seq_ack']
                NAKList = (data[17:17 + header['len']]).decode()
                # congestion control
                if len(NAKList) > 64: CONGESTION = CONGESTION * CONGESTION_CONTROL(ACK_NUM, SEND_WND)
                if CONGESTION > 0.15: CONGESTION = 0.15
                if self.debug:
                    print("=======ACK_NUM=======SEND_WND==========CONGESTION========", 'TIME_OUT')
                    print("========", ACK_NUM, "========", SEND_WND, "========", CONGESTION, "========",TIME_OUT)
                    print('<send 2>', (data[17:17 + header['len']]))
                NAKList = literal_eval(NAKList)
                SEND_WND = len(NAKList)
                # send the query list
                for i in NAKList:
                    payload = msg[i * PKT_SIZE:(i + 1) * PKT_SIZE if (i + 1) * PKT_SIZE < len(msg) else len(msg)]
                    self.sendto(genPKT(1, 0, 0, i, 0, len(payload), payload), self.address)
                    time.sleep(CONGESTION)
                if not NAKList:
                    break
            except timeout:
                continue

    def recv(self, bufsize: int):
        global TIME_OUT
        ACK_NUM = 0
        super().settimeout(TIME_OUT)
        # pktbuffer to recv data
        # NAK-list to record the item which is NAK
        pktBuffer, NAKList = [], []
        while True:
            try:
                data, addr = super().recvfrom(bufsize)
                if addr != self.address:
                    continue
                header = getHeader(data)
                if check(data) and header['syn'] == 0 and header['fin'] == 1 and header['ack'] == 0:
                    return b''
                if not check(data) or header['syn'] != 1 or header['fin'] != 1 or header['ack'] != 1:
                    continue
                # new pkt buffer and nak-list
                for i in range(header['seq']):
                    pktBuffer.append([])
                NAKList = [i for i in range(header['seq'])]
                for i in range(5):
                    self.sendto(genPKT(1, 1, 0, 0, 0, 0), addr)
                    time.sleep(0.01)
                break
            except timeout:
                continue
        # initial TIMEOUT by the len of NAK-LIST
        TIME_OUT = 0.02 * len(NAKList)
        TIME_OUT = 0.15 if TIME_OUT < 0.15 else TIME_OUT
        TIME_OUT = 1.6 if TIME_OUT > 1.6 else TIME_OUT
        super().settimeout(TIME_OUT)
        while True:
            subNAKList = NAKList[:self.WND_SIZE] if len(NAKList) > self.WND_SIZE else NAKList
            bytesNAKList = str(subNAKList).encode('utf-8')
            self.sendto(genPKT(1, 0, 1, 0, ACK_NUM, len(bytesNAKList), bytesNAKList), addr)  # send ack
            ACK_NUM = 0
            if self.debug:
                print('<recv 2>', NAKList)
            if not NAKList: break
            while True:
                try:
                    data, addr = super().recvfrom(bufsize)
                    if addr != self.address:
                        continue
                    header = getHeader(data)
                    seq = header['seq']
                    if check(data) and header['syn'] == 0 and header['fin'] == 1 and header['ack'] == 0:
                        return b''
                    if not check(data) or seq not in NAKList or header['syn'] != 1 or header['fin'] != 0 or header[
                        'ack'] != 0:
                        continue
                    ACK_NUM += 1
                    pktBuffer[seq] = data[17:17 + header['len']]
                    NAKList.remove(seq)
                except timeout:
                    break
        MSG = b''
        for i in pktBuffer:
            MSG += i
        return MSG

    def close(self):
        if self.debug:
            print('start to close')
        super().settimeout(30)

        while True:
            self.sendto(genPKT(0, 1, 0, 0, 0, 0), self.address)
            data, address = super().recvfrom(2048)
            header = getHeader(data)
            if self.debug:
                print('wave header:{}'.format(header))
            if header['fin'] == 1:
                self.sendto(genPKT(0, 0, 1, 0, 0, 0), self.address)  # send ack
                self.sendto(genPKT(0, 1, 0, 0, 0, 0), self.address)  # send fin
                super().close()
                if self.debug:
                    print('closed')
                break
        super().close()


def genPKT(syn, fin, ack, seq, seq_ack, length, payload=b''):
    header = syn.to_bytes(1, 'big') + fin.to_bytes(1, 'big') + \
             ack.to_bytes(1, 'big') + seq.to_bytes(4, 'big') + \
             seq_ack.to_bytes(4, 'big') + length.to_bytes(4, 'big')
    checksum = int.to_bytes(calc_checksum(header + payload), 2, 'big')
    return header + checksum + payload


def getHeader(data):
    keys = {'syn': bytes_int(data[0:1]), 'fin': bytes_int(data[1:2]),
            'ack': bytes_int(data[2:3]), 'seq': bytes_int(data[3:7]),
            'seq_ack': bytes_int(data[7:11]), 'len': bytes_int(data[11:15])}
    return keys


def bytes_int(bytes):
    return int.from_bytes(bytes, 'big')


def check(payload):
    sum = 0
    for byte in payload:
        sum += byte
    return sum % 256 == 0


def calc_checksum(payload):
    sum = 0
    for byte in payload:
        sum += byte
    sum = -(sum % 256)
    return sum & 0xFF


def updateNAK(ACKList, NAKList):
    for i in ACKList:
        NAKList.remove(i)
    return NAKList
