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

    

    for seq_id, packet in enumerate(packets):
        # create package
        udpPacket = int.to_bytes(seq_id+len(packet), SEQ_ID_SIZE, byteorder='big', signed=True) + packet


        # wait ack
        while True:
            try:
                # Wait for ack
                # set timeout time
                udpSocket.settimeout(2)


                # send package
                udpSocket.sendto(udpPacket, SERVER_ADDRESS)
                print(f"[SENT] Packet {seq_id} (size: {len(packet)})")

                
                
                # this is ack return from receiver
                # check for ack to comfirm if correctly received
                ack, _ = udpSocket.recvfrom(PACKET_SIZE)
                print(f"[DEBUG] Raw ACK: {ack}")
                
                # comfirm ack format
                ack_id = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)
                print(f"[RECEIVED] ACK for Packet {seq_id} - Parsed ACK_ID: {ack_id}")
                

                if ack_id == seq_id:
                    print(f"[CONFIRMED] ACK matches expected ID for Packet {seq_id}")
                    break
                else:
                    print(f"[DEBUG] Received unexpected ACK with id={ack_id}, expected={seq_id}")
                    continue


            except socket.timeout:
                totalRetransmission += 1
                print(f"[TIMEOUT] No ACK received for Packet {seq_id}, retransmitting...")

    # send end signal
    finPacket = int.to_bytes(-1, SEQ_ID_SIZE, byteorder='big', signed=True) + b'==FINACK=='
    udpSocket.sendto(finPacket, SERVER_ADDRESS)
    print(f"[FIN] Sent FINACK signal")

# Staticstic Output
endTime = time.time()
useTime = endTime - startTime

print("\n====== Reception Statistics ======")
print(f"Total packets sent: {len(packets)}")
print(f"Total retransmission: {totalRetransmission}")
print(f"Time taken: {useTime:.2f} seconds")
