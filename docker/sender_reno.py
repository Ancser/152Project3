import socket
import time

PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE

# TCP Reno specific constants
INITIAL_CWND = 1
INITIAL_SSTHRESH = 64
TIMEOUT = 2
MAX_WINDOW_SIZE = 25
MAX_RETRIES = 3


def print_debug_info(action, seqId, pktId, cwnd, ssthresh):
    print(f"\n=== DEBUG {action} ===")
    print(f"Sequence ID: {seqId}")
    print(f"Packet ID: {pktId}")
    print(f"Window size: {cwnd}")
    print(f"ssthresh: {ssthresh}")
    print("==================\n")


# read file to send
with open("file.mp3", "rb") as f:
    data = f.read()

# break data
packets = [data[i : i + MESSAGE_SIZE] for i in range(0, len(data), MESSAGE_SIZE)]
print(f"Total packets to send: {len(packets)}")

# make udp socket
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udpSocket:
    SERVER_ADDRESS = ("127.0.0.1", 5001)

    # start calculator as socket created
    startTime = time.time()
    totalRetransmission = 0
    totalJitter = 0
    delayList = []
    lastDelay = None

    # TCP Reno variables
    cwnd = INITIAL_CWND
    ssthresh = INITIAL_SSTHRESH
    dupAcks = 0
    lastAckId = -1
    inFastRecovery = False
    retries = 0

    # Window management
    baseIndex = 0
    nextIndex = 0
    sentTime = {}

    while baseIndex < len(packets):
        # Send packets within current window
        while nextIndex < baseIndex + cwnd and nextIndex < len(packets):
            sizeSeqId = nextIndex * MESSAGE_SIZE  # Convert index to sized sequence ID

            # send package
            udpPacket = (
                int.to_bytes(sizeSeqId, SEQ_ID_SIZE, byteorder="big", signed=True)
                + packets[nextIndex]
            )
            udpSocket.sendto(udpPacket, SERVER_ADDRESS)
            sentTime[sizeSeqId] = time.time()

            print_debug_info("SENDING", sizeSeqId, nextIndex, cwnd, ssthresh)
            print(
                f"Sent packet [{sizeSeqId}] ({len(packets[nextIndex])} bytes), Window: {min(cwnd, MAX_WINDOW_SIZE)} >>>"
            )
            nextIndex += 1

        try:
            udpSocket.settimeout(TIMEOUT)
            ack, _ = udpSocket.recvfrom(PACKET_SIZE)
            sizeAckId = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder="big", signed=True)
            ackIndex = sizeAckId // MESSAGE_SIZE  # Convert sized ID back to index

            print_debug_info("RECEIVED ACK", sizeAckId, ackIndex, cwnd, ssthresh)
            print(f"Received ACK for packet {sizeAckId} ###")

            # Handle delay and jitter calculations
            if sizeAckId in sentTime:
                recvTime = time.time()
                delay = recvTime - sentTime[sizeAckId]
                delayList.append(delay)

                if lastDelay is not None:
                    jitterIncrement = abs(delay - lastDelay)
                    totalJitter += jitterIncrement
                lastDelay = delay
                sentTime.pop(sizeAckId)

            # Handle new vs duplicate ACKs
            if sizeAckId >= lastAckId:
                if sizeAckId > lastAckId:  # New ACK
                    # Move window forward
                    oldBase = baseIndex
                    baseIndex = ackIndex + 1

                    if inFastRecovery:  # Exit Fast Recovery
                        cwnd = ssthresh
                        inFastRecovery = False
                        print("Exiting Fast Recovery")
                    else:
                        # Update window size with limit
                        if cwnd < ssthresh:  # Slow Start
                            cwnd = min(cwnd * 2, MAX_WINDOW_SIZE)
                            print(f"Slow Start: Window increased to {cwnd}")
                        else:  # Congestion Avoidance
                            cwnd = min(cwnd + 1, MAX_WINDOW_SIZE)
                            print(f"Congestion Avoidance: Window increased to {cwnd}")

                    dupAcks = 0
                    retries = 0  # Reset retries on successful ACK
                    print(f"Made progress: {oldBase} -> {baseIndex}")
                else:  # Duplicate ACK
                    dupAcks += 1
                    print(f"Duplicate ACK received. Count: {dupAcks}")
                    if dupAcks == 3:  # Triple duplicate ACK
                        if not inFastRecovery:  # Enter Fast Recovery
                            print(f"Fast Recovery triggered")
                            ssthresh = max(cwnd // 2, 2)
                            cwnd = ssthresh + 3  # Set to ssthresh + 3 for Reno
                            inFastRecovery = True
                            nextIndex = baseIndex  # Retransmit lost packet
                            totalRetransmission += 1
                        elif inFastRecovery:  # In Fast Recovery, inflate window
                            cwnd = min(cwnd + 1, MAX_WINDOW_SIZE)  # Inflate window
                            print(f"Fast Recovery: Window inflated to {cwnd}")

                lastAckId = sizeAckId

            print(f"Base index [{baseIndex}], Next index [{nextIndex}] []->[]")

            # Add progress check
            if baseIndex >= len(packets):
                break

        except socket.timeout:
            retries += 1
            print(
                f"TIMEOUT at baseIndex: {baseIndex}, nextIndex: {nextIndex}, Retry: {retries}"
            )
            if retries >= MAX_RETRIES:
                print(
                    f"Max retries reached for packet {baseIndex}, moving to next packet"
                )
                baseIndex += 1
                nextIndex = baseIndex
                retries = 0

            # Exit Fast Recovery if we're in it
            inFastRecovery = False
            ssthresh = max(cwnd // 2, 2)
            cwnd = 1
            dupAcks = 0
            totalRetransmission += 1
            nextIndex = baseIndex

    # send end signal
    finPacket = (
        int.to_bytes(-1, SEQ_ID_SIZE, byteorder="big", signed=True) + b"==FINACK=="
    )
    udpSocket.sendto(finPacket, SERVER_ADDRESS)
    print(f"Sent FINACK signal XXX")

# Calculate and print metrics
endTime = time.time()
useTime = endTime - startTime
totalData = len(packets) * MESSAGE_SIZE
throughput = totalData / useTime
avgDelay = sum(delayList) / len(delayList) if delayList else 0
avgJitter = totalJitter / (len(delayList) - 1) if len(delayList) > 1 else 0

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
