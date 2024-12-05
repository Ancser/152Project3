import socket
import time
import select
import threading
from queue import Queue

PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE
WINDOW_SIZE = 40
TIMEOUT = 2

# Read file to send
with open('file.mp3', 'rb') as f:
    data = f.read()

# Break data into packets
packets = [data[i:i + MESSAGE_SIZE] for i in range(0, len(data), MESSAGE_SIZE)]
print(f"Total packets to send: {len(packets)}")

# Shared variables and locks
sentTime = {}
ackList = set()
baseIndex = 0
newIndex = 0
baseIndexLock = threading.Lock()
queueLock = threading.Lock()
queue = Queue()

# UDP socket setup
udpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
SERVER_ADDRESS = ('127.0.0.1', 5001)
udpSocket.setblocking(False)
startTime = time.time()

# Sender thread
def sender():
    global newIndex, baseIndex

    while True:
        with baseIndexLock:
            if baseIndex >= len(packets):
                break

        # Send new packets within the window
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

        # Resend timed-out packets
        now = time.time()
        with queueLock:
            for SeqID in range(baseIndex, newIndex):
                sizeSeqID = SeqID * MESSAGE_SIZE
                if sizeSeqID in sentTime and (now - sentTime[sizeSeqID]) > TIMEOUT:
                    udpPacket = int.to_bytes(sizeSeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[SeqID]
                    udpSocket.sendto(udpPacket, SERVER_ADDRESS)
                    sentTime[sizeSeqID] = now
                    print(f"RE-Sent package [{sizeSeqID}] ({len(packets[SeqID])} bytes) >>>")
        time.sleep(0.01)  # Small sleep to avoid CPU overload

# Receiver thread
def receiver():
    global baseIndex

    while True:
        with baseIndexLock:
            if baseIndex >= len(packets):
                break

        # Check for ACKs
        received, _, _ = select.select([udpSocket], [], [], TIMEOUT)
        if received:
            ack, _ = udpSocket.recvfrom(PACKET_SIZE)
            sizeAckID = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)

            # Mark ACK received
            SeqID = sizeAckID // MESSAGE_SIZE
            print(f"Received ACK ID [{sizeAckID}] <<<")

            # Update baseIndex and remove sentTime entries
            with baseIndexLock:
                with queueLock:
                    for confirmedSeqID in range(baseIndex, SeqID + 1):
                        sizeSeqID = confirmedSeqID * MESSAGE_SIZE
                        if sizeSeqID in sentTime:
                            del sentTime[sizeSeqID]
                baseIndex = SeqID + 1
        time.sleep(0.01)  # Small sleep to avoid CPU overload

# Start threads
senderThread = threading.Thread(target=sender)
receiverThread = threading.Thread(target=receiver)

senderThread.start()
receiverThread.start()

senderThread.join()
receiverThread.join()

# Metrics
endTime = time.time()
useTime = endTime - startTime

# Throughput
totalData = len(packets) * MESSAGE_SIZE
throughput = totalData / useTime

print("\n=========== METRIC ==================")
print(f"Total Time: {useTime:.2f} seconds")
print(f"Throughput: {throughput:.2f} bytes/second")
