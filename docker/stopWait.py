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

# make udp socklet
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udpSocket:
    SERVER_ADDRESS = ('127.0.0.1', 5001)  # receiver address

    # start calculator as socket created
    startTime = time.time()
    totalRetransmission = 0
    

    for seq_id, packet in enumerate(packets):
        # create package
        seq_id_bytes = int.to_bytes(seq_id, SEQ_ID_SIZE, byteorder='big', signed=True)
        udpPacket = seq_id_bytes + packet

        # wait ack
        while True:
            try:
                # send package
                udpSocket.sendto(udpPacket, SERVER_ADDRESS)
                print(f"Sent packet {seq_id}")

                # Wait for ack
                # set timeout time
                udpSocket.settimeout(2)
                
                # this is ack return from receiver
                # check for ack to comfirm if correctly received
                ack, _ = udpSocket.recvfrom(PACKET_SIZE)
                
                # comfirm ack format
                ack_id = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)
                print(f"Received ACK for sequence ID: {ack_id}")

                if ack_id == seq_id + 1:
                    print(f"Received ACK for packet {seq_id}")
                    break


            except socket.timeout:
                totalRetransmission += 1
                print(f"Timeout for packet {seq_id}, resending...")

    # send end signal
    finPacket = int.to_bytes(-1, SEQ_ID_SIZE, byteorder='big', signed=True) + b'==FINACK=='
    udpSocket.sendto(finPacket, SERVER_ADDRESS)
    print("Sent FINACK")

# Staticstic Output
endTime = time.time()
useTime = endTime - startTime

print("\n====== Reception Statistics ======")
print(f"Total packets sent: {len(packets)}")
print(f"Total retransmission: {totalRetransmission}")
print(f"Time taken: {useTime:.2f} seconds")
