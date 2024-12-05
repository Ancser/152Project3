import socket
import time
import select
import threading
from queue import Queue

PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE
WINDOW_SIZE = 25  # Initial window size
TIMEOUT = 1
MAX_WINDOW_SIZE = 40
MIN_WINDOW_SIZE = 5

# Metrics
startTime = time.time()
totalRetransmission = 0
totalJitter = 0
delayList = []
lastDelay = None

# BBR Variables
currentBandwidth = 0  # Estimated bandwidth
minRTT = float('inf')  # Minimum observed RTT
sendingRate = 1  # Packets per second
phase = "Startup"  # Current BBR phase

# Read file to send
with open('file.mp3', 'rb') as f:
    data = f.read()

# Break data into packets
packets = [data[i:i + MESSAGE_SIZE] for i in range(0, len(data), MESSAGE_SIZE)]
print(f"Total packets to send: {len(packets)}")

# Shared variables and locks
sentTime = {}
baseIndex = 0
newIndex = 0
baseIndexLock = threading.Lock()
queueLock = threading.Lock()

# UDP socket setup
udpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
SERVER_ADDRESS = ('127.0.0.1', 5001)
udpSocket.setblocking(False)

# Sender thread
def sender():
    global newIndex, baseIndex, sendingRate, phase, currentBandwidth, minRTT, WINDOW_SIZE

    while True:
        with baseIndexLock:
            if baseIndex >= len(packets):
                break

        # Send all packets within the window
        packets_sent = 0
        while newIndex < baseIndex + WINDOW_SIZE and newIndex < len(packets):
            SeqID = newIndex
            sizeSeqID = SeqID * MESSAGE_SIZE

            # Send packet
            udpPacket = int.to_bytes(sizeSeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[SeqID]
            udpSocket.sendto(udpPacket, SERVER_ADDRESS)

            # Record send time
            with queueLock:
                sentTime[sizeSeqID] = time.time()

            print(f"Sent package [{sizeSeqID}] ({len(packets[SeqID])} bytes) >>>")
            newIndex += 1
            packets_sent += 1

        # Adjust sending rate and window after sending batch
        if packets_sent > 0:
            if phase == "Startup":
                sendingRate *= 1.25  # Ramp up rate
                if currentBandwidth > sendingRate:
                    phase = "Drain"
            elif phase == "Drain":
                sendingRate *= 0.8  # Slow down
                if sendingRate <= currentBandwidth:
                    phase = "ProbeBW"
            elif phase == "ProbeBW":
                sendingRate = currentBandwidth  # Maintain bandwidth
            elif phase == "ProbeRTT":
                sendingRate = 1  # Minimize rate temporarily
                time.sleep(0.1)
                phase = "ProbeBW"

            # Adjust window size
            WINDOW_SIZE = min(MAX_WINDOW_SIZE, max(MIN_WINDOW_SIZE, int(WINDOW_SIZE * 1.1)))

        # Pause briefly after a batch
        time.sleep(0.01)


# Receiver thread
def receiver():
    global baseIndex, currentBandwidth, minRTT, sendingRate

    while True:
        with baseIndexLock:
            if baseIndex >= len(packets):
                break

        # Check for ACKs
        received, _, _ = select.select([udpSocket], [], [], TIMEOUT)
        if received:
            ack, _ = udpSocket.recvfrom(PACKET_SIZE)
            sizeAckID = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)

            # Mark ACK received and update metrics
            SeqID = sizeAckID // MESSAGE_SIZE
            print(f"Received ACK ID [{sizeAckID}] <<<")

            with baseIndexLock:
                with queueLock:
                    for confirmedSeqID in range(baseIndex, SeqID + 1):
                        sizeSeqID = confirmedSeqID * MESSAGE_SIZE
                        if sizeSeqID in sentTime:
                            rtt = time.time() - sentTime[sizeSeqID]
                            currentBandwidth = max(currentBandwidth, MESSAGE_SIZE / rtt)
                            minRTT = min(minRTT, rtt)
                            del sentTime[sizeSeqID]
                baseIndex = SeqID + 1
        time.sleep(0.01)

# Start threads
senderThread = threading.Thread(target=sender)
receiverThread = threading.Thread(target=receiver)

senderThread.start()
receiverThread.start()

senderThread.join()
receiverThread.join()

# Metrics calculation
endTime = time.time()
useTime = endTime - startTime
totalData = len(packets) * MESSAGE_SIZE
throughput = totalData / useTime
avgDelay = sum(delayList) / len(delayList) if delayList else 0
avgJitter = totalJitter / (len(delayList) - 1) if len(delayList) > 1 else 0
metric = (
    0.2 * (throughput / 2000) +
    0.1 * (1 / avgJitter if avgJitter > 0 else 0) +
    0.8 * (1 / avgDelay if avgDelay > 0 else 0)
)

print("\n=========== METRIC ==================")
print(f"Total Time: {useTime:.2f} seconds")
print(f"Throughput: {throughput:.2f} bytes/second")
print(f"Average Delay: {avgDelay:.7f} seconds")
print(f"Average Jitter: {avgJitter:.7f} seconds")
print(f"Metric: {metric:.7f}")

