import socket
import time

PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE

# TCP Tahoe specific constants
INITIAL_CWND = 1
INITIAL_SSTHRESH = 64
TIMEOUT = 1

# read file to send
with open("file.mp3", "rb") as f:
    data = f.read()

# break data
packets = [data[i : i + MESSAGE_SIZE] for i in range(0, len(data), MESSAGE_SIZE)]
print(f"Total packets to send: {len(packets)}")

# make udp socket
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udpSocket:
    SERVER_ADDRESS = ("127.0.0.1", 5001)  # receiver address

    # start calculator as socket created
    startTime = time.time()
    totalRetransmission = 0
    totalJitter = 0
    delayList = []
    lastDelay = None

    # TCP Tahoe variables
    cwnd = INITIAL_CWND
    ssthresh = INITIAL_SSTHRESH
    dupAcks = 0
    lastAckId = -1

    # Window management
    baseIndex = 0  # first unacked packet
    nextIndex = 0  # next packet to send
    sentTime = {}  # track send times for each packet

    while baseIndex < len(packets):
        # Send packets within current window ======================================================
        while nextIndex < baseIndex + cwnd and nextIndex < len(packets):
            sizeSeqId = nextIndex * MESSAGE_SIZE

            # send package
            udpPacket = (
                int.to_bytes(sizeSeqId, SEQ_ID_SIZE, byteorder="big", signed=True)
                + packets[nextIndex]
            )
            udpSocket.sendto(udpPacket, SERVER_ADDRESS)

            # record send time
            sentTime[sizeSeqId] = time.time()

            print(
                f"Sent packet [{sizeSeqId}] ({len(packets[nextIndex])} bytes), Window: {cwnd} >>>"
            )
            nextIndex += 1

        # Wait for response ======================================================
        try:
            udpSocket.settimeout(TIMEOUT)

            # getting ACK package
            ack, _ = udpSocket.recvfrom(PACKET_SIZE)
            sizeAckId = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder="big", signed=True)
            ackPktId = sizeAckId // MESSAGE_SIZE

            print(f"Received ACK [{sizeAckId}], Packet {ackPktId} confirmed ###")

            # Calculate delay and jitter if we have the send time
            if sizeAckId in sentTime:
                recvTime = time.time()
                delay = recvTime - sentTime[sizeAckId]
                delayList.append(delay)

                if lastDelay is not None:
                    jitterIncrement = abs(delay - lastDelay)
                    totalJitter += jitterIncrement

                lastDelay = delay
                sentTime.pop(sizeAckId)

            # Handle duplicate ACKs
            if sizeAckId == lastAckId:
                dupAcks += 1
                if dupAcks == 3:  # Fast Retransmit
                    print(f"Fast Retransmit triggered, Window: {cwnd} -> 1")
                    ssthresh = max(cwnd // 2, 2)
                    cwnd = 1
                    dupAcks = 0
                    nextIndex = baseIndex  # retransmit from last acked packet
            else:
                dupAcks = 0
                lastAckId = sizeAckId

                # Move window forward
                while (
                    baseIndex < len(packets) and baseIndex * MESSAGE_SIZE <= sizeAckId
                ):
                    baseIndex += 1

                # Update congestion window
                if cwnd < ssthresh:  # Slow Start
                    cwnd *= 2
                    print(f"Slow Start: Window increased to {cwnd}")
                else:  # Congestion Avoidance
                    cwnd += 1
                    print(f"Congestion Avoidance: Window increased to {cwnd}")

            print(f"Base index [{baseIndex}], Next index [{nextIndex}] []->[]")

        except socket.timeout:
            # Timeout: set ssthresh and reset cwnd
            print(f"Timeout! Window: {cwnd} -> 1")
            ssthresh = max(cwnd // 2, 2)
            cwnd = 1
            totalRetransmission += 1
            nextIndex = baseIndex  # retransmit from last acked packet

    # send end signal
    finPacket = (
        int.to_bytes(-1, SEQ_ID_SIZE, byteorder="big", signed=True) + b"==FINACK=="
    )
    udpSocket.sendto(finPacket, SERVER_ADDRESS)
    print(f"Sent FINACK signal XXX")

# Staticstic Output ===================================================
# time ---------------------------------------
endTime = time.time()
useTime = endTime - startTime

# throughput ------------------------------------
totalData = len(packets) * MESSAGE_SIZE
throughput = totalData / useTime

# delay and jitter -----------------------------
avgDelay = sum(delayList) / len(delayList) if delayList else 0
avgJitter = totalJitter / (len(delayList) - 1) if len(delayList) > 1 else 0

# metric ---------------------------------------
metric = (
    0.2 * (throughput / 2000)
    + 0.1 * (1 / avgJitter if avgJitter > 0 else 0)
    + 0.8 * (1 / avgDelay if avgDelay > 0 else 0)
)

print("\n=========== METRIC ==================")
print(f"Packets sent: {len(packets)}")
print(f"Packet retransmissions: {totalRetransmission}")
print(f"Time: {useTime:.7f} seconds\n")

print(f"Throughput: {throughput:.7f} bytes/second")
print(f"Average delay: {avgDelay:.7f} seconds")
print(f"Average jitter: {avgJitter:.7f} seconds")
print(f"Metric: {metric:.7f}")
