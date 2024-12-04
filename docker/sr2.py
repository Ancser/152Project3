import socket
import time
import select

PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE

WINDOW_SIZE = 10
TIMEOUT = 1

# selective resend
# reason: since receiver collect all packages in a list, no order is require, 
# so we can continue to send without waiting, only resend when there is no response, 
# need a independent timer for them.

# read file to send
with open('file.mp3', 'rb') as f:
    data = f.read()

# break data
packets = [data[i:i+MESSAGE_SIZE] for i in range(0, len(data), MESSAGE_SIZE)]
print(f"Total packets to send: {len(packets)}")

# make udp socklet
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udpSocket:
    # receviver address
    SERVER_ADDRESS = ('127.0.0.1', 5001)

    # allow dynamic waiting =======================================
    # not like stop and wait that stuck between 2 process.
    # during whole socket process, will not stop if no receive
    udpSocket.setblocking(False)

    # metric calculations ==========================================
    # delete for improve performance
    startTime = time.time()
    totalRetransmission = 0
    totalJitter = 0
    delayList = []
    lastDelay = None

    # window variable ===============================================
    # sent time must be record for each pacakge
    baseIndex = 0
    nextSeqID = 0
    sentTime = {}
    ackList = set()

    # Main send loop ================================================
    # when still have packages
    while baseIndex < len(packets):

        # send -------------------------------------------
        # this process never stop
        # detail condition check window capcatiy
        while nextSeqID < baseIndex + WINDOW_SIZE and nextSeqID < len(packets):
            SeqID = nextSeqID
            fullSeqID = SeqID * MESSAGE_SIZE

            # set up package
            udpPacket = int.to_bytes(fullSeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[SeqID]
            udpSocket.sendto(udpPacket, SERVER_ADDRESS)
            sentTime[fullSeqID] = time.time()

            print(f"Snet package [{fullSeqID}] ({len(packets[SeqID])} bytes) >>>") 

            # move to next
            nextSeqID += 1


        # wait ack --------------------------------------
        # this is the process we dont want get stuck on
        # check if there is new received data, if timeout then return empty list
        # so it will not run
        received, _, _ = select.select([udpSocket],[],[],TIMEOUT)
        if received:
            ack, _ = udpSocket.recvfrom(PACKET_SIZE)
            AckID = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)

            # comfirmed receive, add to acked list
            ackSeqID = (AckID - MESSAGE_SIZE)
            print(f"Received ACK {AckID}, Comfirmed transmitted Package {ackSeqID}")


            if ackSeqID >= 0:
                # calculated matric
                if AckID in sentTime:
                    receiveTime = time.time()
                    delay = receiveTime - sentTime[AckID]
                    delayList.append(delay)

                    if lastDelay is not None:
                        totalJitter += abs(delay - lastDelay)
                    lastDelay = delay

                #  hendel and update comfirm list
                for comfirmedSeqID in range(baseIndex, ackSeqID +1):
                    fullSeqID = comfirmedSeqID * MESSAGE_SIZE
                    if fullSeqID in sentTime:
                        del sentTime[fullSeqID]
                    if comfirmedSeqID in ackList:
                        ackList.remove(comfirmedSeqID)
                
                baseIndex = ackSeqID + 1
                print(f"Window Moved: baseIndex[{baseIndex}], next ID [{nextSeqID}]")

        # timeout ---------------------------------------
        # alway update time
        now = time.time()
        # checking all the unsettleed index to current id (window)
        for SeqID in range(baseIndex, nextSeqID):
            fullSeqID = SeqID * MESSAGE_SIZE

            if fullSeqID in sentTime and (now - sentTime[fullSeqID]) > TIMEOUT:
                
                # set up package
                udpPacket = int.to_bytes(fullSeqID, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[SeqID]
                udpSocket.sendto(udpPacket, SERVER_ADDRESS)
                sentTime[fullSeqID] = now

                print(f"RE-Snet package [{fullSeqID}] ({len(packets[SeqID])} bytes) >>>") 
                totalRetransmission += 1
        
    # send fin package
    finPacket = int.to_bytes(-1, SEQ_ID_SIZE, byteorder='big', signed=True) + b'==FINACK=='
    udpSocket.sendto(finPacket, SERVER_ADDRESS)
    print(f"Sent FINACK signal XXX")


# Staticstic Output ===================================================
# time ---------------------------------------
endTime = time.time()
useTime = endTime - startTime

# throuput ------------------------------------
totalData = len(packets) * MESSAGE_SIZE
throughput = totalData / useTime

# delay and jitter -----------------------------
avgDelay = sum(delayList) / len(delayList) if delayList else 0
avgJitter = totalJitter / (len(delayList) - 1) if len(delayList) > 1 else 0

# metric ---------------------------------------
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
