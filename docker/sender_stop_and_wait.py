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
    delayList = []
    totalJitter = 0
    lastDelay = None  

    SeqID = 0

    for packet in packets:
        
        # wait ack
        while True:
            try:
                # create and send the package ====================================
                sendTime = time.time()
                udpPacket = int.to_bytes(SeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packet
                udpSocket.sendto(udpPacket, SERVER_ADDRESS)
                print(f"Sent packet [{SeqID}] ({len(packet)} byte) >>>")

                # wait for response =============================================
                # setting timeout
                udpSocket.settimeout(2)

                # check for ack to comfirm if correctly received
                ack, _ = udpSocket.recvfrom(PACKET_SIZE)
                
                # comfirm ack format
                AckID = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)
                print(f"ACK Requesting [{AckID}], Comfirmed [{SeqID}] <<<")
                
                # metruc calculation ==============================================
                # Delay
                recvTime = time.time()
                delay = recvTime - sendTime
                delayList.append(delay)

                # Jitter
                if lastDelay is not None:
                    totalJitter += abs(delay - lastDelay)
                lastDelay = delay

                # if error on different arc =============================================
                # this will shift the next package, otherwise, it will loop same seqID
                if AckID == SeqID + len(packet):
                    SeqID += len(packet)
                    print(f"Comfirmed received package [{SeqID}], Shift to next Index+++")
                    break
                else:
                    print(f"Warning! ACK ID not matched {AckID}, expected{SeqID} xxx")
                    continue

            # Send next data of currect. =============================================      
            except socket.timeout:
                totalRetransmission += 1
                print(f"Timeout package ID [{SeqID}], Retransmission >>>")


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