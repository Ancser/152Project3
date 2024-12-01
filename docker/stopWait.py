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
    delays = []
    totalJitter = 0
    lastDelay = None  

    seq_id = 0

    for packet in packets:
        
        # wait ack
        while True:
            try:
                # create and send the package ====================================
                sendTime = time.time()
                udpPacket = int.to_bytes(seq_id, SEQ_ID_SIZE, byteorder='big', signed=True) + packet
                udpSocket.sendto(udpPacket, SERVER_ADDRESS)
                print(f"Sent packet ID [{seq_id}] ({len(packet)} byte) >>>")

                # wait for response =============================================
                # setting timeout
                udpSocket.settimeout(2)

                # check for ack to comfirm if correctly received
                ack, _ = udpSocket.recvfrom(PACKET_SIZE)
                
                # comfirm ack format
                ack_id = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)
                print(f"Receive ACK ID: {ack_id} for pacakge ID {seq_id} <<<")
                
                # Delay
                recvTime = time.time()
                delay = recvTime - sendTime
                delays.append(delay)

                # Jitter
                if lastDelay is not None:
                    totalJitter += abs(delay - lastDelay)
                lastDelay = delay

                # Send next data of currect.
                # seq_id is current, must match the expected return ack with higher id
                if ack_id == seq_id + len(packet):
                    seq_id += len(packet)
                    print(f"Success! ACK ID mactched with {seq_id} +++")
                    break
                else:
                    print(f"Warning! ACK ID not matched {ack_id}, expected{seq_id} xxx")
                    continue


            except socket.timeout:
                totalRetransmission += 1
                print(f"Timeout package ID [{seq_id}], Retransmission...")


    # send end signal
    finPacket = int.to_bytes(-1, SEQ_ID_SIZE, byteorder='big', signed=True) + b'==FINACK=='
    udpSocket.sendto(finPacket, SERVER_ADDRESS)
    print(f"Sent FINACK signal XXX")

# Staticstic Output ===================================================
# all time
endTime = time.time()
useTime = endTime - startTime

# throuput
totalData = len(packets) * MESSAGE_SIZE
throughput = totalData / useTime

# delay and jitter
avgDelay = sum(delays) / len(delays)
avgJitter = totalJitter / (len(delays) - 1) if len(delays) > 1 else 0

# final metric
metric = (
    0.2 * (throughput / 2000) +
    0.1 * (1 / avgJitter if avgJitter > 0 else 0) +
    0.8 * (1 / avgDelay if avgDelay > 0 else 0)
)

print("\n=========== METRIC ==================")
print(f"Total packets sent: {len(packets)}")
print(f"Total retransmission: {totalRetransmission}")

print(f"Time taken: {useTime:.2f} seconds")
print(f"Throughput: {throughput:.2f} bytes/second")
print(f"Average packet delay: {avgDelay:.2f} seconds")
print(f"Average jitter: {avgJitter:.2f} seconds")
print(f"Performance Metric: {metric:.2f}")