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
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
    SERVER_ADDRESS = ('127.0.0.1', 5001)  # receiver address

    for seq_id, packet in enumerate(packets):
        # create package
        seq_id_bytes = int.to_bytes(seq_id, SEQ_ID_SIZE, byteorder='big', signed=True)
        udp_packet = seq_id_bytes + packet

        # wait ack
        while True:
            try:
                # 发送数据包
                udp_socket.sendto(udp_packet, SERVER_ADDRESS)
                print(f"Sent packet {seq_id}")

                # 等待 ACK
                udp_socket.settimeout(2)  # 设置超时时间
                ack, _ = udp_socket.recvfrom(PACKET_SIZE)

                # 检查 ACK
                ack_id = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)
                if ack_id == seq_id + 1:
                    print(f"Received ACK for packet {seq_id}")
                    break
            except socket.timeout:
                print(f"Timeout for packet {seq_id}, resending...")

    # send end signal
    fin_packet = int.to_bytes(-1, SEQ_ID_SIZE, byteorder='big', signed=True) + b'==FINACK=='
    udp_socket.sendto(fin_packet, SERVER_ADDRESS)
    print("Sent FINACK")
