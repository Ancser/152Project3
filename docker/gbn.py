import socket
import time

PACKET_SIZE = 1024
SEQ_ID_SIZE = 4
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE

# read file to send
with open('file.mp3', 'rb') as f:
    data = f.read()

# break data
packets = [data[i:i+MESSAGE_SIZE] for i in range(0, len(data), MESSAGE_SIZE)]
print(f"Total packets to send: {len(packets)}")

# make udp socklet
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udpSocket:
    SERVER_ADDRESS = ('127.0.0.1', 5001)  # receiver address

    # start calculator as socket created
    startTime = time.time()
    totalRetransmission = 0


    # GBN window setting ===============================================
    windowSize = 5 
    baseIndex = 0
    next_seq_id = 0
    unacked_packets = {}


    while baseIndex < len(packets):

        # Send packets within the window
        while next_seq_id < baseIndex + windowSize and next_seq_id < len(packets):
            packet = packets[next_seq_id]
            udpPacket = int.to_bytes(next_seq_id, SEQ_ID_SIZE, byteorder='big', signed=True) + packet
            udpSocket.sendto(udpPacket, SERVER_ADDRESS)
            print(f"Sent packet ID [{next_seq_id}] ({len(packet)} byte) >>>")
            unacked_packets[next_seq_id] = packet  # Track the packet
            next_seq_id += 1
        

        try:
            # Wait for ACK
            udpSocket.settimeout(2)
            ack, _ = udpSocket.recvfrom(PACKET_SIZE)
            ack_id = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)
            print(f"Receive ACK ID: {ack_id} <<<")

            if ack_id > baseIndex:
                # Slide the window forward
                for seq_id in range(baseIndex, ack_id):
                    if seq_id in unacked_packets:
                        del unacked_packets[seq_id]
                baseIndex = ack_id
                print(f"Window moved! new base index [{baseIndex}] +++")

        except socket.timeout:
            # Retransmit all packets in the current window
            totalRetransmission += 1
            print(f"Timeout! Retransmitting window starting from baseIndex {baseIndex}...")
            for seq_id in range(baseIndex, next_seq_id):
                if seq_id in unacked_packets:
                    packet = unacked_packets[seq_id]
                    udpPacket = int.to_bytes(seq_id, SEQ_ID_SIZE, byteorder='big', signed=True) + packet
                    udpSocket.sendto(udpPacket, SERVER_ADDRESS)


    # send end signal
    finPacket = int.to_bytes(-1, SEQ_ID_SIZE, byteorder='big', signed=True) + b'==FINACK=='
    udpSocket.sendto(finPacket, SERVER_ADDRESS)
    print(f"Sent FINACK signal XXX")

# Staticstic Output
endTime = time.time()
useTime = endTime - startTime

print("\n====== Reception Statistics ======")
print(f"Total packets sent: {len(packets)}")
print(f"Total retransmission: {totalRetransmission}")
print(f"Time taken: {useTime:.2f} seconds")
