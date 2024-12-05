import socket
import time
import select

PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE

WINDOW_SIZE = 25
TIMEOUT = 2

# read file to send
with open('file.mp3', 'rb') as f:
    data = f.read()

packets = [data[i:i+MESSAGE_SIZE] for i in range(0, len(data), MESSAGE_SIZE)]
print(f"Total packets to send: {len(packets)}")

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udpSocket:
    SERVER_ADDRESS = ('127.0.0.1', 5001)
    udpSocket.setblocking(False)

    startTime = time.time()
    totalRetransmission = 0

    cwnd = 1  # Initial congestion window
    ssthresh = WINDOW_SIZE // 2  # Initial threshold
    baseIndex = 0
    newIndex = 0
    sentTime = {}
    dupAcks = 0
    lastAck = -1
    inFastRecovery = False

    while baseIndex < len(packets):
        while newIndex < baseIndex + cwnd and newIndex < len(packets):
            SeqID = newIndex
            sizeSeqID = SeqID * MESSAGE_SIZE

            udpPacket = int.to_bytes(sizeSeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[SeqID]
            udpSocket.sendto(udpPacket, SERVER_ADDRESS)
            sentTime[sizeSeqID] = time.time()

            newIndex += 1

        received, _, _ = select.select([udpSocket], [], [], TIMEOUT)
        if received:
            ack, _ = udpSocket.recvfrom(PACKET_SIZE)
            sizeAckID = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)
            SeqID = sizeAckID // MESSAGE_SIZE

            if SeqID > lastAck:  # New ACK
                baseIndex = SeqID + 1
                dupAcks = 0
                if inFastRecovery:  # Exit fast recovery
                    cwnd = ssthresh
                    inFastRecovery = False
                if cwnd < ssthresh:  # Slow start
                    cwnd *= 2
                else:  # Congestion avoidance
                    cwnd += 1
            elif SeqID == lastAck:  # Duplicate ACK
                dupAcks += 1
                if dupAcks == 3:  # Triple duplicate ACK
                    ssthresh = max(cwnd // 2, 1)
                    cwnd = ssthresh + 3  # Reno: Enter fast recovery
                    inFastRecovery = True
                    newIndex = baseIndex  # Retransmit lost packet
            lastAck = SeqID
        else:
            # Timeout
            ssthresh = max(cwnd // 2, 1)
            cwnd = 1  # Reset to 1
            inFastRecovery = False
            totalRetransmission += 1
            for SeqID in range(baseIndex, newIndex):
                sizeSeqID = SeqID * MESSAGE_SIZE
                if sizeSeqID in sentTime and (time.time() - sentTime[sizeSeqID]) > TIMEOUT:
                    udpPacket = int.to_bytes(sizeSeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[SeqID]
                    udpSocket.sendto(udpPacket, SERVER_ADDRESS)
                    sentTime[sizeSeqID] = time.time()

    finPacket = int.to_bytes(-1, SEQ_ID_SIZE, byteorder='big', signed=True) + b'==FINACK=='
    udpSocket.sendto(finPacket, SERVER_ADDRESS)

endTime = time.time()
print(f"Time taken: {endTime - startTime:.2f}s, Retransmissions: {totalRetransmission}")
