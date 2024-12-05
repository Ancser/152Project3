import socket
import time
import select
import threading

PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE

# this window size from 20-25 is Comfirmed safe
# 20 = 75s 
# 25 = 60s
# 30 = 67s
# over 25 will have too much retransmission lag
WINDOW_SIZE = 25
TIMEOUT = 1

# selective resend
# reason: since receiver collect all packages in a list, no order is require, 
# so we can continue to send without waiting, only resend when there is no response, 
# need an independent timer for them.

# 2 ID format:
# a. index ID, as package / window index, start from 1-5000
# b. size ID, multiple with file size *1020, from 0-530,0000

# read file to send
with open('file.mp3', 'rb') as f:
    data = f.read()

# break data
packets = [data[i:i + MESSAGE_SIZE] for i in range(0, len(data), MESSAGE_SIZE)]
print(f"Total packets to send: {len(packets)}")

# Shared variables and locks
sentTime = {}
ackList = set()
baseIndex = 0
newIndex = 0
baseIndexLock = threading.Lock()
queueLock = threading.Lock()

# Metrics
startTime = time.time()
totalRetransmission = 0
totalJitter = 0
delayList = []
lastDelay = None

# UDP socket setup
udpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
SERVER_ADDRESS = ('127.0.0.1', 5001)
udpSocket.setblocking(False)

# Sender thread
def sender():
    global newIndex, baseIndex, totalRetransmission

    while True:
        with baseIndexLock:
            if baseIndex >= len(packets):
                break

        # Send -------------------------------------------
        # Send all packets within the current window
        while newIndex < baseIndex + WINDOW_SIZE and newIndex < len(packets):
            SeqID = newIndex
            sizeSeqID = SeqID * MESSAGE_SIZE

            # Prepare and send packet
            udpPacket = int.to_bytes(sizeSeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[SeqID]
            udpSocket.sendto(udpPacket, SERVER_ADDRESS)
            with queueLock:
                sentTime[sizeSeqID] = time.time()

            print(f"Sent package [{sizeSeqID}] ({len(packets[SeqID])} bytes) >>>")
            newIndex += 1

        # Resend timed-out packets
        now = time.time()
        with queueLock:
            for SeqID in range(baseIndex, newIndex):
                sizeSeqID = SeqID * MESSAGE_SIZE
                if sizeSeqID in sentTime and (now - sentTime[sizeSeqID]) > TIMEOUT:
                    udpPacket = int.to_bytes(sizeSeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[SeqID]
                    udpSocket.sendto(udpPacket, SERVER_ADDRESS)
                    sentTime[sizeSeqID] = now
                    totalRetransmission += 1
                    print(f"RE-Sent package [{sizeSeqID}] ({len(packets[SeqID])} bytes) >>>")
        time.sleep(0.01)

# Receiver thread
def receiver():
    global baseIndex, totalJitter, lastDelay, delayList

    while True:
        with baseIndexLock:
            if baseIndex >= len(packets):
                break

        # Wait for ACKs --------------------------------------
        received, _, _ = select.select([udpSocket], [], [], TIMEOUT)
        if received:
            ack, _ = udpSocket.recvfrom(PACKET_SIZE)
            sizeAckID = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)

            # Confirmed receive
            SeqID = sizeAckID // MESSAGE_SIZE
            print(f"Requesting ACK {sizeAckID}, Confirmed transmitted Package {SeqID + 1} ###")

            # Calculate delay and jitter
            with queueLock:
                if sizeAckID in sentTime:
                    receiveTime = time.time()
                    delay = receiveTime - sentTime[sizeAckID]
                    delayList.append(delay)

                    if lastDelay is not None:
                        totalJitter += abs(delay - lastDelay)
                    lastDelay = delay

                # Handle and update confirm list
                for confirmedSeqID in range(baseIndex, SeqID + 1):
                    sizeSeqID = confirmedSeqID * MESSAGE_SIZE
                    if sizeSeqID in sentTime:
                        del sentTime[sizeSeqID]

            with baseIndexLock:
                baseIndex = SeqID + 1
        time.sleep(0.01)

# Start threads
senderThread = threading.Thread(target=sender)
receiverThread = threading.Thread(target=receiver)

senderThread.start()
receiverThread.start()

senderThread.join()
receiverThread.join()

# Metrics Output
endTime = time.time()
useTime = endTime - startTime

# Throughput
totalData = len(packets) * MESSAGE_SIZE
throughput = totalData / useTime

# Delay and Jitter
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

