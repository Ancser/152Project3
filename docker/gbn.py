import socket
import time

PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE

# read file to send
with open('file.mp3', 'rb') as f:
    data = f.read()

# break data
packets = [data[i:i+MESSAGE_SIZE] for i in range(0, len(data), MESSAGE_SIZE)]
print(f"Total packets to send: {len(packets)}")

# make udp socklet
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udpSocket:
    SERVER_ADDRESS = ('127.0.0.1', 5001)  # receiver address

    # start calculator as socket created 
    startTime = time.time()
    totalRetransmission = 0
    totalJitter = 0
    delayList = []
    lastDelay = None


    # GBN window setting ===============================================
    windowSize = 5 
    baseIndex = 0
    nextSeqID = 0
    waitAckPacket = {}


    while baseIndex < len(packets):

        # Send window >>>>>>
        # must check window index maximum greater than the next s
        while nextSeqID < baseIndex + windowSize and nextSeqID < len(packets):
            packet = packets[nextSeqID]
            SeqID = nextSeqID * MESSAGE_SIZE
            udpPacket = int.to_bytes(SeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packet
            udpSocket.sendto(udpPacket, SERVER_ADDRESS)
            print(f"Sent packet ID [{SeqID}] ({len(packet)} byte) >>>")

            sendTime = time.time()

            #  the list of the package with no ack response yet
            # for now is all, record id, package info and time
            waitAckPacket[SeqID] = (packet,sendTime)
            nextSeqID += 1
        
        # Wait for resonse <<<<<
        try:
            # time out setting this might make huge change,try it!!!
            udpSocket.settimeout(1)

            # getting ACK package, getting ACK ID
            ack, _ = udpSocket.recvfrom(PACKET_SIZE)
            AckID = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)
            print(f"Receive ACK ID: {AckID} <<<")

            # ACK must be > window range
            while baseIndex * MESSAGE_SIZE < AckID:

                SeqID = baseIndex * MESSAGE_SIZE

                # Comfirm the wating ACK response is now comfirmed.
                if SeqID in waitAckPacket:
                    _, sendTime = waitAckPacket.pop(SeqID)
                    

                    # Calculating Delay
                    recvTime = time.time()
                    delay = recvTime - sendTime
                    delayList.append(delay)

                    # Calculate jitter
                    if lastDelay is not None:
                        jitterIncrement = abs(delay - lastDelay)
                        totalJitter += jitterIncrement
                    lastDelay = delay

                # Comfired received, now base index can move on   
                baseIndex += 1
            print(f"Window moved! new base index [{baseIndex}] +++")

        # timeout send all window >>>>>>
        except socket.timeout:
            # Retransmit all packets in the current window
            print(f"Timeout! Retransmitting window from [{baseIndex}] >>>")
            totalRetransmission += 1

            for SeqID in range(baseIndex, nextSeqID):
                reSeqID = SeqID * MESSAGE_SIZE
                print(f"Resending {list(waitAckPacket.keys())}")
                if SeqID in waitAckPacket:
                    # preparing resend package
                    packet, sendTime = waitAckPacket[reSeqID]

                    # resend process
                    udpPacket = int.to_bytes(SeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packet
                    udpSocket.sendto(udpPacket, SERVER_ADDRESS)
                    


    # send end signal
    finPacket = int.to_bytes(-1, SEQ_ID_SIZE, byteorder='big', signed=True) + b'==FINACK=='
    udpSocket.sendto(finPacket, SERVER_ADDRESS)
    print(f"Sent FINACK signal XXX")

# Staticstic Output ===================================================
# time ---------------------------------------
endTime = time.time()
useTime = endTime - startTime

# throuput ------------------------------------
totalData = len(packets) * MESSAGE_SIZE
throughput = totalData / useTime

# delay and jitter -----------------------------
avgDelay = sum(delayList) / len(delayList) if delayList else 0
avgJitter = totalJitter / (len(delayList) - 1) if len(delayList) > 1 else 0

# metric ---------------------------------------
metric = (
    0.2 * (throughput / 2000) +
    0.1 * (1 / avgJitter if avgJitter > 0 else 0) +
    0.8 * (1 / avgDelay if avgDelay > 0 else 0)
)

print("\n=========== METRIC ==================")
print(f"Package sent: {len(packets)}")
print(f"Package retransmission: {totalRetransmission}")
print(f"Time: {useTime:.7f} seconds\n")

print(f"Throughput: {throughput:.7f} bytes/second")
print(f"Average delay: {avgDelay:.7f} seconds")
print(f"Average jitter: {avgJitter:.7f} seconds")
print(f"Metric: {metric:.7f}")
