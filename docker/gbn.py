import socket
import time

PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE

# move constant here
WINDOW_SIZE = 5
TIMEOUT = 1

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
    baseIndex = 0
    newIndex = 0
    sentTime = {}


    while baseIndex < len(packets):

        # Send window ======================================================== >>>>>>
        # must check window index maximum greater than the next s
        while newIndex < baseIndex + WINDOW_SIZE and newIndex < len(packets):
            
            # index to full size id, otherwise mismatch
            SeqID = newIndex
            sizeSeqID = newIndex * MESSAGE_SIZE

            # send package
            udpPacket = int.to_bytes(sizeSeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[SeqID]
            udpSocket.sendto(udpPacket, SERVER_ADDRESS)

            #  the list of the package with no ack response yet
            # for now is all, record id, package info and time
            sentTime[sizeSeqID] = time.time()

            print(f"Sent packet [{sizeSeqID}] ({len(packets)} byte) >>>")

            newIndex += 1
        
        # Wait for resonse ====================================================== <<<<<
        # it is same running time with the sending 1-1, not efficient
        try:
            # time out setting this might make huge change
            udpSocket.settimeout(TIMEOUT)

            # getting ACK package, getting ACK ID
            ack, _ = udpSocket.recvfrom(PACKET_SIZE)
            sizeAckID = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)
            SeqID = sizeAckID // MESSAGE_SIZE

            print(f"Requesting ACK {sizeAckID}, Comfirmed transmitted Package {SeqID+1} ###")

            # Comfirm the wating ACK response is now comfirmed.
            if sizeAckID in sentTime:
                _, sendTime = sentTime.pop(sizeAckID)
                
                # Calculating Delay
                recvTime = time.time()
                delay = recvTime - sendTime
                delayList.append(delay)

                # Calculate jitter
                if lastDelay is not None:
                    jitterIncrement = abs(delay - lastDelay)
                    totalJitter += jitterIncrement

                lastDelay = delay

            # comfirmed received, move in window
            while baseIndex < len(packets) and baseIndex * MESSAGE_SIZE <= sizeAckID:
                baseIndex += 1

            print(f"Comfirm index [{baseIndex}], newest index [{newIndex}] []->[]")

        # timeout send all window >>>>>>
        except socket.timeout:
            # Retransmit all packets in the current window
            print(f"Timeout! Retransmitting window from [{baseIndex}] >>>")
            totalRetransmission += 1

            for SeqID  in range(baseIndex, newIndex):
                sizeReSeqID = SeqID  * MESSAGE_SIZE
                
                # resent all package, from time list not delisted
                if SeqID  in sentTime:

                    # resend process
                    udpPacket = int.to_bytes(sizeReSeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[SeqID]
                    udpSocket.sendto(udpPacket, SERVER_ADDRESS)

                    print(f"Resending package [{sizeReSeqID}]>>>")
                    


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
