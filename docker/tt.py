import socket
import time
import threading

PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE

# TCP Tahoe specific constants
INITIAL_CWND = 1
INITIAL_SSTHRESH = 64
TIMEOUT = 1

MAX_WINDOW_SIZE = 100

# Read file to send
with open("file.mp3", "rb") as f:
    data = f.read()

# Break data
packets = [data[i:i + MESSAGE_SIZE] for i in range(0, len(data), MESSAGE_SIZE)]
print(f"Total packets to send: {len(packets)}")

# Thread-safe variables and locks
cwnd = INITIAL_CWND
ssthresh = INITIAL_SSTHRESH
dupAcks = 0
lastAckId = -1
baseIndex = 0
nextIndex = 0
sentTime = {}
lock = threading.Lock()
retransmissions = 0

# Metrics
startTime = time.time()
totalRetransmission = 0
totalJitter = 0
delayList = []
lastDelay = None

# UDP socket setup
udpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
SERVER_ADDRESS = ("127.0.0.1", 5001)
udpSocket.setblocking(False)

# Sending thread
def sender():
    global nextIndex, cwnd, baseIndex
    while True:
        with lock:
            if baseIndex >= len(packets):  # Exit condition
                break

        # Send packets within the current window
        while nextIndex < baseIndex + cwnd and nextIndex < len(packets):
            sizeSeqId = nextIndex * MESSAGE_SIZE
            udpPacket = (
                int.to_bytes(sizeSeqId, SEQ_ID_SIZE, byteorder="big", signed=True)
                + packets[nextIndex]
            )
            udpSocket.sendto(udpPacket, SERVER_ADDRESS)

            with lock:
                sentTime[sizeSeqId] = time.time()
            print(
                f"Sent packet [{sizeSeqId}] ({len(packets[nextIndex])} bytes), Window: {cwnd} >>>"
            )
            nextIndex += 1

        time.sleep(0.01)  # Prevent high CPU usage

# Receiving thread
def receiver():
    global baseIndex, nextIndex, lastAckId, dupAcks, cwnd, ssthresh, retransmissions, lastDelay, totalJitter
    while True:
        with lock:
            if baseIndex >= len(packets):  # Exit condition
                break

        try:
            ack, _ = udpSocket.recvfrom(PACKET_SIZE)
            sizeAckId = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder="big", signed=True)
            ackPktId = sizeAckId // MESSAGE_SIZE

            print(f"Received ACK [{sizeAckId}], Packet {ackPktId} confirmed ###")

            with lock:
                # Handle ACK and update congestion control
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
                    if dupAcks == 3:  # Trigger Fast Retransmit only on 3 consecutive duplicate ACKs
                        print(f"Fast Retransmit triggered, Window: {cwnd} -> 1")
                        ssthresh = max(cwnd // 2, 2)
                        cwnd = 1
                        dupAcks = 0
                        nextIndex = baseIndex  # Retransmit from the last acked packet
                else:
                    # Valid ACK: Reset duplicate count and advance the base index
                    dupAcks = 0
                    lastAckId = sizeAckId

                    while (
                        baseIndex < len(packets) and baseIndex * MESSAGE_SIZE <= sizeAckId
                    ):
                        baseIndex += 1

                    # Update congestion window
                    if cwnd < ssthresh:  # Slow Start
                        cwnd = min(cwnd * 2, MAX_WINDOW_SIZE)  # Cap window size
                        print(f"Slow Start: Window increased to {cwnd}")
                    else:  # Congestion Avoidance
                        cwnd += 1
                        print(f"Congestion Avoidance: Window increased to {cwnd}")

                print(f"Base index [{baseIndex}], Next index [{nextIndex}] []->[]")

        except BlockingIOError:
            pass
        except socket.timeout:
            with lock:
                print(f"Timeout! Window: {cwnd} -> 1")
                ssthresh = max(cwnd // 2, 2)
                cwnd = 1
                retransmissions += 1
                nextIndex = baseIndex  # Retransmit from the last acked packet

        time.sleep(0.01)  # Prevent high CPU usage



# Start threads
senderThread = threading.Thread(target=sender)
receiverThread = threading.Thread(target=receiver)

senderThread.start()
receiverThread.start()

senderThread.join()
receiverThread.join()

# Send end signal
finPacket = (
    int.to_bytes(-1, SEQ_ID_SIZE, byteorder="big", signed=True) + b"==FINACK=="
)
udpSocket.sendto(finPacket, SERVER_ADDRESS)
print(f"Sent FINACK signal XXX")

# Staticstic Output ===================================================
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
