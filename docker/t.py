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
    cwnd = 1
    ssthresh = WINDOW_SIZE // 2
    baseIndex = 0
    newIndex = 0
    sentTime = {}

    while baseIndex < len(packets):
        while newIndex < baseIndex + cwnd and newIndex < len(packets):
            SeqID = newIndex
            sizeSeqID = SeqID * MESSAGE_SIZE
            udpPacket = int.to_bytes(sizeSeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[SeqID]
            udpSocket.sendto(udpPacket, SERVER_ADDRESS)
            sentTime[sizeSeqID] = time.time()
            print(f"Sent packet ID [{sizeSeqID}] ({len(packets[SeqID])} bytes) <<<")
            newIndex += 1

        received, _, _ = select.select([udpSocket], [], [], TIMEOUT)
        if received:
            ack, _ = udpSocket.recvfrom(PACKET_SIZE)
            sizeAckID = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)
            SeqID = sizeAckID // MESSAGE_SIZE
            print(f"Returning ACK ID [{sizeAckID}] >>>")

            if SeqID == baseIndex:  # Valid ACK for the expected packet
                baseIndex += 1
                if cwnd < ssthresh:
                    cwnd *= 2  # Slow start
                else:
                    cwnd += 1  # Congestion avoidance
            else:
                print(f"Warning: Received unexpected ACK ID [{sizeAckID}]")

        else:
            # Timeout handling: Retransmit all packets in the current window
            print(f"Timeout: Retransmitting packets in window [{baseIndex}:{newIndex}]")
            ssthresh = max(cwnd // 2, 1)
            cwnd = 1
            totalRetransmission += 1
            for SeqID in range(baseIndex, newIndex):
                sizeSeqID = SeqID * MESSAGE_SIZE
                udpPacket = int.to_bytes(sizeSeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[SeqID]
                udpSocket.sendto(udpPacket, SERVER_ADDRESS)
                sentTime[sizeSeqID] = time.time()
                print(f"Retransmitted packet ID [{sizeSeqID}] <<<")

    finPacket = int.to_bytes(-1, SEQ_ID_SIZE, byteorder='big', signed=True) + b'==FINACK=='
    udpSocket.sendto(finPacket, SERVER_ADDRESS)
    print("Sent FINACK signal")

endTime = time.time()
print(f"Time taken: {endTime - startTime:.2f}s, Retransmissions: {totalRetransmission}")
