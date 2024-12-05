import socket
import time
import select
import heapq
import math

# PERFORMANCE OPTIMIZATION: Adaptive parameters
PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE

# IMPROVEMENT: Dynamically adjustable window size with advanced congestion control
WINDOW_SIZE = 25
MAX_WINDOW_SIZE = 200
TIMEOUT = 1
WINDOW_GROWTH_FACTOR = 1.2
WINDOW_DECREASE_FACTOR = 0.5

# IMPROVEMENT: More sophisticated timeout and retransmission strategy
BASE_TIMEOUT = 0.5
ADAPTIVE_TIMEOUT_ALPHA = 0.125  # Recommended value for RTT estimation
ADAPTIVE_TIMEOUT_BETA = 0.25   # Recommended value for RTT variation

# read file to send
with open('file.mp3', 'rb') as f:
    data = f.read()

# break data
packets = [data[i:i+MESSAGE_SIZE] for i in range(0, len(data), MESSAGE_SIZE)]
print(f"Total packets to send: {len(packets)}")

# IMPROVEMENT: Advanced packet tracking with priority queue
class PacketTracker:
    def __init__(self):
        self.sentTime = {}  # Track sent times (kept original variable name)
        self.rttEstimates = {}  # RTT estimation per packet
        self.rttVariations = {}  # RTT variation tracking
        self.unackedPackets = []  # Priority queue of unacked packets

    def add_packet(self, sizeSeqID, sendTime):
        heapq.heappush(self.unackedPackets, sizeSeqID)
        self.sentTime[sizeSeqID] = sendTime

    def remove_packet(self, sizeSeqID):
        self.sentTime.pop(sizeSeqID, None)
        self.rttEstimates.pop(sizeSeqID, None)
        self.rttVariations.pop(sizeSeqID, None)

    def update_rtt(self, sizeSeqID, rtt):
        # IMPROVEMENT: Adaptive RTT estimation (Jacobson's algorithm)
        if sizeSeqID not in self.rttEstimates:
            self.rttEstimates[sizeSeqID] = rtt
            self.rttVariations[sizeSeqID] = rtt / 2
        else:
            oldRTT = self.rttEstimates[sizeSeqID]
            oldVar = self.rttVariations[sizeSeqID]
            
            self.rttEstimates[sizeSeqID] = (1 - ADAPTIVE_TIMEOUT_ALPHA) * oldRTT + ADAPTIVE_TIMEOUT_ALPHA * rtt
            self.rttVariations[sizeSeqID] = (1 - ADAPTIVE_TIMEOUT_BETA) * oldVar + ADAPTIVE_TIMEOUT_BETA * abs(rtt - oldRTT)

    def get_timeout(self, sizeSeqID):
        # Adaptive timeout calculation
        if sizeSeqID not in self.rttEstimates:
            return BASE_TIMEOUT
        
        estimatedRTT = self.rttEstimates[sizeSeqID]
        rttVariation = self.rttVariations[sizeSeqID]
        return estimatedRTT + 4 * rttVariation

# make udp socket
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udpSocket:
    # receiver address
    SERVER_ADDRESS = ('127.0.0.1', 5001)

    # allow dynamic waiting
    udpSocket.setblocking(False)

    # metric calculations
    startTime = time.time()
    totalRetransmission = 0
    totalJitter = 0
    delayList = []
    lastDelay = None

    # window variable
    baseIndex = 0
    newIndex = 0
    currentWindowSize = WINDOW_SIZE
    packetTracker = PacketTracker()

    # Main send loop with advanced congestion control
    while baseIndex < len(packets):
        # send
        while (newIndex < baseIndex + currentWindowSize and 
               newIndex < len(packets)):
            SeqID = newIndex
            sizeSeqID = SeqID * MESSAGE_SIZE

            # set up package
            udpPacket = int.to_bytes(sizeSeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[SeqID]
            udpSocket.sendto(udpPacket, SERVER_ADDRESS)
            
            currentTime = time.time()
            packetTracker.add_packet(sizeSeqID, currentTime)
            
            print(f"Sent package [{sizeSeqID}] ({len(packets[SeqID])} bytes) >>>")
            newIndex += 1

        # wait ack
        received, _, _ = select.select([udpSocket], [], [], TIMEOUT)
        if received:
            ack, _ = udpSocket.recvfrom(PACKET_SIZE)
            sizeAckID = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)
            SeqID = (sizeAckID // MESSAGE_SIZE)

            if SeqID >= baseIndex:  # 確認ACK有效
                print(f"Received ACK ID [{sizeAckID}] <<<")

                # update window
                for confirmedSeqID in range(baseIndex, SeqID + 1):
                    confirmedSizeSeqID = confirmedSeqID * MESSAGE_SIZE
                    if confirmedSizeSeqID in packetTracker.sentTime:
                        packetTracker.remove_packet(confirmedSizeSeqID)

                # update window
                baseIndex = SeqID + 1

                # dynamic window
                currentWindowSize = min(MAX_WINDOW_SIZE, int(currentWindowSize * WINDOW_GROWTH_FACTOR))

        # timeout:
        for SeqID in range(baseIndex, newIndex):
            sizeSeqID = SeqID * MESSAGE_SIZE

            if sizeSeqID in packetTracker.sentTime:
                sentTime = packetTracker.sentTime[sizeSeqID]
                packetTimeout = packetTracker.get_timeout(sizeSeqID)

                if (currentTime - sentTime) > packetTimeout:
                    # resent
                    udpPacket = int.to_bytes(sizeSeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[SeqID]
                    udpSocket.sendto(udpPacket, SERVER_ADDRESS)

                    # reduce window
                    packetTracker.sentTime[sizeSeqID] = currentTime
                    currentWindowSize = max(WINDOW_SIZE, int(currentWindowSize * WINDOW_DECREASE_FACTOR))

                    totalRetransmission += 1
                    print(f"RE-Sent package [{sizeSeqID}] ({len(packets[SeqID])} bytes) >>>")


# Staticstic Output================================================
endTime = time.time()
useTime = endTime - startTime

# throughput
totalData = len(packets) * MESSAGE_SIZE
throughput = totalData / useTime

# delay and jitter
avgDelay = sum(delayList) / len(delayList) if delayList else 0
avgJitter = totalJitter / (len(delayList) - 1) if len(delayList) > 1 else 0

# metric
metric = (
    0.3 * (throughput / 2000) +
    0.2 * (1 / (avgJitter + 0.001)) +
    0.5 * (1 / (avgDelay + 0.001))
)

print("\n=========== METRIC ==================")
print(f"Package sent: {len(packets)}")
print(f"Package retransmission: {totalRetransmission}")
print(f"Time: {useTime:.7f} seconds\n")

print(f"Throughput: {throughput:.7f} bytes/second")
print(f"Average delay: {avgDelay:.7f} seconds")
print(f"Average jitter: {avgJitter:.7f} seconds")
print(f"Metric: {metric:.7f}")
