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

# make udp socket
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udpSocket:
    SERVER_ADDRESS = ('127.0.0.1', 5001)  # receiver address

    # start calculator as socket created 
    startTime = time.time()
    totalRetransmission = 0
    totalJitter = 0
    delays = []
    lastDelay = None

    windowSize = 5 
    baseIndex = 0
    nextSeqID = 0
    waitAckPacket = {}
    lowestUnackedSeqID = 0

    while baseIndex < len(packets):
        # Send window >>>>>>
        while nextSeqID < baseIndex + windowSize and nextSeqID < len(packets):
            packet = packets[nextSeqID]
            # CHANGE: Calculate SeqID based on actual byte position
            SeqID = nextSeqID * MESSAGE_SIZE
            
            # Prepare UDP packet with sequence ID
            udpPacket = int.to_bytes(SeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packet
            udpSocket.sendto(udpPacket, SERVER_ADDRESS)
            print(f"Sent packet ID [{SeqID}] ({len(packet)} byte) >>>")

            sendTime = time.time()

            waitAckPacket[SeqID] = {
                'packet': packet, 
                'sendTime': sendTime, 
                'sequenceIndex': nextSeqID
            }
            nextSeqID += 1
        
        # Wait for response <<<<<
        try:
            # Set timeout
            udpSocket.settimeout(1)

            # get ACK package
            ack, _ = udpSocket.recvfrom(PACKET_SIZE)
            
            # CHANGE: Extract ACK ID precisely
            AckID = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)
            print(f"Receive ACK ID: {AckID} <<<")

            # Remove all packets up to and including the acknowledged packet
            packetsToRemove = [
                seqId for seqId in list(waitAckPacket.keys()) 
                if seqId <= AckID
            ]
            
            for seqId in packetsToRemove:
                # Remove acknowledged packets from wait list
                if seqId in waitAckPacket:
                    # Calculate delay for this packet
                    sendTime = waitAckPacket[seqId]['sendTime']
                    recvTime = time.time()
                    delay = recvTime - sendTime
                    delays.append(delay)

                    # Calculate jitter
                    if lastDelay is not None:
                        jitterIncrement = abs(delay - lastDelay)
                        totalJitter += jitterIncrement
                    lastDelay = delay

                    # Remove the packet from wait list
                    del waitAckPacket[seqId]
            
            baseIndex = max(
                [waitAckPacket[key]['sequenceIndex'] for key in waitAckPacket] + [0]
            )
            
            print(f"Window moved! new base index [{baseIndex}] +++")

        # timeout send all window >>>>>>
        except socket.timeout:
            print(f"Timeout! Retransmitting unacknowledged packets >>>")
            totalRetransmission += 1

            # Retransmit only unacknowledged packets in the current window
            for SeqID, packetInfo in list(waitAckPacket.items()):
                # Prepare resend package
                packet = packetInfo['packet']
                sequenceIndex = packetInfo['sequenceIndex']

                # Resend process
                udpPacket = int.to_bytes(SeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packet
                udpSocket.sendto(udpPacket, SERVER_ADDRESS)
                print(f"Resending packet ID [{SeqID}] ({len(packet)} byte)")

    # send end signal
    finPacket = int.to_bytes(-1, SEQ_ID_SIZE, byteorder='big', signed=True) + b'==FINACK=='
    udpSocket.sendto(finPacket, SERVER_ADDRESS)
    print(f"Sent FINACK signal XXX")

# Staticstic Output ===================================================
# Calculate metrics (same as before)
endTime = time.time()
useTime = endTime - startTime

totalData = len(packets) * MESSAGE_SIZE
throughput = totalData / useTime if useTime > 0 else 0

avgDelay = sum(delays) / len(delays) if delays else 0
avgJitter = totalJitter / (len(delays) - 1) if len(delays) > 1 else 0

metric = (
    0.2 * (throughput / 2000) +
    0.1 * (1 / avgJitter if avgJitter > 0 else 0) +
    0.8 * (1 / avgDelay if avgDelay > 0 else 0)
)

print("\n=========== METRIC ==================")
print(f"Total packets sent: {len(packets)}")
print(f"Total retransmission: {totalRetransmission}")
print(f"Total Time: {useTime:.2f} seconds")
print(f"Throughput: {throughput:.2f} bytes/second")
print(f"Average packet delay: {avgDelay:.2f} seconds")
print(f"Average jitter: {avgJitter:.2f} seconds")
print(f"Performance Metric: {metric:.2f}")