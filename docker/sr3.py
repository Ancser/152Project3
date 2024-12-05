import socket
import time
import select

PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE

# Initial adaptive window parameters
WINDOW_SIZE = 5  # Start with a small window size
TIMEOUT = 2
MAX_WINDOW_SIZE = 50  # Define a maximum limit for the window size

# Bandwidth Estimation variables (Implementation 1)
ACKED_BYTES = 0
BANDWIDTH_UPDATE_INTERVAL = 1  # Update bandwidth estimation every second
bandwidth = 0
last_bandwidth_update = time.time()

# Adaptive RTT variables (Implementation 2)
alpha = 0.125
beta = 0.25
EstimatedRTT = 0.1  # Initial RTT estimate
DevRTT = 0.1

# Read file to send
with open('file.mp3', 'rb') as f:
    data = f.read()

# Break data into packets
packets = [data[i:i+MESSAGE_SIZE] for i in range(0, len(data), MESSAGE_SIZE)]
print(f"Total packets to send: {len(packets)}")

# UDP socket setup
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udpSocket:
    SERVER_ADDRESS = ('127.0.0.1', 5001)
    udpSocket.setblocking(False)

    # Metrics
    startTime = time.time()
    totalRetransmission = 0
    totalJitter = 0
    delayList = []
    lastDelay = None

    # Sliding window variables
    baseIndex = 0
    newIndex = 0
    sentTime = {}

    # Main send loop
    while baseIndex < len(packets):
        # Send packets within the window
        while newIndex < baseIndex + WINDOW_SIZE and newIndex < len(packets):
            SeqID = newIndex
            sizeSeqID = SeqID * MESSAGE_SIZE

            # Prepare and send packet
            udpPacket = int.to_bytes(sizeSeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[SeqID]
            udpSocket.sendto(udpPacket, SERVER_ADDRESS)
            sentTime[sizeSeqID] = time.time()

            print(f"Sent package [{sizeSeqID}] ({len(packets[SeqID])} bytes) >>>")
            newIndex += 1

        # Wait for ACKs
        received, _, _ = select.select([udpSocket], [], [], TIMEOUT)
        if received:
            ack, _ = udpSocket.recvfrom(PACKET_SIZE)
            sizeAckID = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)

            # Confirm ACK and update metrics
            SeqID = sizeAckID // MESSAGE_SIZE
            print(f"Received ACK {sizeAckID}, Confirmed transmitted Package {SeqID + 1} ###")

            if sizeAckID in sentTime:
                receiveTime = time.time()
                delay = receiveTime - sentTime[sizeAckID]
                delayList.append(delay)

                # Adaptive RTT (Implementation 2)
                SampleRTT = delay
                EstimatedRTT = (1 - alpha) * EstimatedRTT + alpha * SampleRTT
                DevRTT = (1 - beta) * DevRTT + beta * abs(SampleRTT - EstimatedRTT)
                TIMEOUT = EstimatedRTT + 4 * DevRTT  # Update timeout dynamically

                # Update jitter calculation
                if lastDelay is not None:
                    totalJitter += abs(delay - lastDelay)
                lastDelay = delay

                # Bandwidth estimation (Implementation 1)
                ACKED_BYTES += MESSAGE_SIZE

            # Update the base index and remove sent time entries
            for confirmedSeqID in range(baseIndex, SeqID + 1):
                sizeSeqID = confirmedSeqID * MESSAGE_SIZE
                if sizeSeqID in sentTime:
                    del sentTime[sizeSeqID]

            baseIndex = SeqID + 1
            # Increase window size on successful transmission
            WINDOW_SIZE = min(WINDOW_SIZE + 1, MAX_WINDOW_SIZE)

        # Handle timeouts and retransmissions
        now = time.time()
        for SeqID in range(baseIndex, newIndex):
            sizeSeqID = SeqID * MESSAGE_SIZE
            if sizeSeqID in sentTime and (now - sentTime[sizeSeqID]) > TIMEOUT:
                udpPacket = int.to_bytes(sizeSeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[SeqID]
                udpSocket.sendto(udpPacket, SERVER_ADDRESS)
                sentTime[sizeSeqID] = now

                print(f"RE-Sent package [{sizeSeqID}] ({len(packets[SeqID])} bytes) >>>")
                totalRetransmission += 1
                # Decrease window size on retransmission
                WINDOW_SIZE = max(WINDOW_SIZE - 1, 1)

        # Update bandwidth estimation every interval (Implementation 1)
        if now - last_bandwidth_update >= BANDWIDTH_UPDATE_INTERVAL:
            bandwidth = ACKED_BYTES / BANDWIDTH_UPDATE_INTERVAL  # Bytes per second
            ACKED_BYTES = 0
            last_bandwidth_update = now
            print(f"Estimated Bandwidth: {bandwidth:.2f} bytes/sec")

    # Metrics calculation
    endTime = time.time()
    useTime = endTime - startTime

    # Throughput calculation
    totalData = len(packets) * MESSAGE_SIZE
    throughput = totalData / useTime

    # Delay and jitter
    avgDelay = sum(delayList) / len(delayList) if delayList else 0
    avgJitter = totalJitter / (len(delayList) - 1) if len(delayList) > 1 else 0

    # Metric
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


