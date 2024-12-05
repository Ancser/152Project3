import socket
import time
import threading

PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE

# Initial adaptive window parameters
WINDOW_SIZE = 10  # Start with a moderate window size
TIMEOUT = 2
MAX_WINDOW_SIZE = 100  # Define a maximum limit for the window size

# Adaptive RTT variables
alpha = 0.125
beta = 0.25
EstimatedRTT = 0.1
DevRTT = 0.1

# Thread-safe variables and locks
sentTime = {}
baseIndex = 0
newIndex = 0
baseIndexLock = threading.Lock()

# Metrics
startTime = time.time()
totalRetransmission = 0
delayList = []
lastDelay = None

# Read file to send
with open('file.mp3', 'rb') as f:
    data = f.read()

# Break data into packets
packets = [data[i:i + MESSAGE_SIZE] for i in range(0, len(data), MESSAGE_SIZE)]
print(f"Total packets to send: {len(packets)}")

# UDP socket setup
udpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
SERVER_ADDRESS = ('127.0.0.1', 5001)
udpSocket.setblocking(False)

# Sending thread
def sender():
    global newIndex, baseIndex, WINDOW_SIZE, totalRetransmission
    while True:
        with baseIndexLock:
            if baseIndex >= len(packets):
                break

        # Send packets in batch
        batchSent = 0
        while newIndex < baseIndex + WINDOW_SIZE and newIndex < len(packets):
            SeqID = newIndex
            sizeSeqID = SeqID * MESSAGE_SIZE
            udpPacket = int.to_bytes(sizeSeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[SeqID]
            udpSocket.sendto(udpPacket, SERVER_ADDRESS)
            sentTime[sizeSeqID] = time.time()
            print(f"Sent package [{sizeSeqID}] ({len(packets[SeqID])} bytes) >>>")
            newIndex += 1
            batchSent += 1

        # Dynamic sleep based on batch size
        time.sleep(max(0.001, 0.01 - batchSent * 0.001))

        # Handle retransmissions inline
        now = time.time()
        for SeqID in range(baseIndex, newIndex):
            sizeSeqID = SeqID * MESSAGE_SIZE
            if sizeSeqID in sentTime and (now - sentTime[sizeSeqID]) > TIMEOUT:
                udpPacket = int.to_bytes(sizeSeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[SeqID]
                udpSocket.sendto(udpPacket, SERVER_ADDRESS)
                sentTime[sizeSeqID] = now
                print(f"RE-Sent package [{sizeSeqID}] >>>")
                totalRetransmission += 1
                WINDOW_SIZE = max(WINDOW_SIZE - 1, 1)  # Reduce window size on retransmission

# Receiving thread
def receiver():
    global baseIndex, lastDelay, WINDOW_SIZE, EstimatedRTT, DevRTT, TIMEOUT

    while True:
        with baseIndexLock:
            if baseIndex >= len(packets):
                break

        try:
            # Process multiple ACKs in a non-blocking loop
            while True:
                ack, _ = udpSocket.recvfrom(PACKET_SIZE)
                sizeAckID = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)
                SeqID = sizeAckID // MESSAGE_SIZE

                # Confirm ACK and update metrics
                print(f"Received ACK {sizeAckID} ###")
                if sizeAckID in sentTime:
                    receiveTime = time.time()
                    delay = receiveTime - sentTime[sizeAckID]
                    delayList.append(delay)

                    # Adaptive RTT
                    SampleRTT = delay
                    EstimatedRTT = (1 - alpha) * EstimatedRTT + alpha * SampleRTT
                    DevRTT = (1 - beta) * DevRTT + beta * abs(SampleRTT - EstimatedRTT)
                    TIMEOUT = EstimatedRTT + 4 * DevRTT

                    # Update base index
                    with baseIndexLock:
                        for confirmedSeqID in range(baseIndex, SeqID + 1):
                            sizeSeqID = confirmedSeqID * MESSAGE_SIZE
                            if sizeSeqID in sentTime:
                                del sentTime[sizeSeqID]
                        baseIndex = SeqID + 1
                        WINDOW_SIZE = min(WINDOW_SIZE + 1, MAX_WINDOW_SIZE)  # Increase window size on success

        except BlockingIOError:
            pass

        time.sleep(0.01)  # Prevent high CPU usage

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

# Throughput calculation
totalData = len(packets) * MESSAGE_SIZE
throughput = totalData / useTime

# Delay
avgDelay = sum(delayList) / len(delayList) if delayList else 0

# Metric
metric = (
    0.2 * (throughput / 2000) +
    0.8 * (1 / avgDelay if avgDelay > 0 else 0)
)

print("\n=========== METRIC ==================")
print(f"Package sent: {len(packets)}")
print(f"Package retransmission: {totalRetransmission}")
print(f"Time: {useTime:.7f} seconds\n")
print(f"Throughput: {throughput:.7f} bytes/second")
print(f"Average delay: {avgDelay:.7f} seconds")
print(f"Metric: {metric:.7f}")



