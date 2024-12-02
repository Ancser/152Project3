import socket
import time
from threading import Timer

PACKET_SIZE = 1024  # Total packet size
SEQ_ID_SIZE = 4  # Sequence ID size
MESSAGE_SIZE = PACKET_SIZE - SEQ_ID_SIZE  # Size of the message part
WINDOW_SIZE = 4  # Size of the sliding window

# Read the file to send
with open('file.mp3', 'rb') as f:
    data = f.read()

# Split the file into packets
packets = [data[i:i + MESSAGE_SIZE] for i in range(0, len(data), MESSAGE_SIZE)]

# Create a global retransmission counter
totalRetransmissions = 0

# Create UDP socket
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udpSocket:
    SERVER_ADDRESS = ('127.0.0.1', 5001)  # Address of the receiver
    base = 0  # Initial sequence number of the window
    nextSeq = 0  # Next sequence number to send

    # Define timeout function
    def timeout():
        global totalRetransmissions
        print(f"[TIMEOUT] Retransmitting window starting from {base}")
        for seq_id in range(base, min(base + WINDOW_SIZE, len(packets))):
            udpPacket = int.to_bytes(seq_id, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[seq_id]
            udpSocket.sendto(udpPacket, SERVER_ADDRESS)
            print(f"[RETRANSMIT] Packet {seq_id}")
            totalRetransmissions += 1  # Increment retransmission counter

    timer = None  # Timer initialization

    while base < len(packets):
        # Send packets in the window
        while nextSeq < base + WINDOW_SIZE and nextSeq < len(packets):
            udpPacket = int.to_bytes(nextSeq, SEQ_ID_SIZE, byteorder='big', signed=True) + packets[nextSeq]
            udpSocket.sendto(udpPacket, SERVER_ADDRESS)
            print(f"[SENT] Packet {nextSeq}")
            if base == nextSeq:
                if timer:
                    timer.cancel()  # Cancel previous timer
                timer = Timer(2.0, timeout)  # Start a 2-second timer
                timer.start()
            nextSeq += 1

        try:
            # Wait for ACK
            udpSocket.settimeout(2)
            ack, _ = udpSocket.recvfrom(PACKET_SIZE)
            ack_id = int.from_bytes(ack[:SEQ_ID_SIZE], byteorder='big', signed=True)
            print(f"[RECEIVED] ACK for Packet {ack_id}")

            if ack_id >= base:
                base = ack_id + 1  # Slide the window
                if timer:
                    timer.cancel()  # Cancel timer after ACK
        except socket.timeout:
            print("[TIMEOUT] No ACK received, retransmitting...")
            timeout()

    # Send finish signal
    finPacket = int.to_bytes(-1, SEQ_ID_SIZE, byteorder='big', signed=True) + b'==FINACK=='
    udpSocket.sendto(finPacket, SERVER_ADDRESS)
    print("[FIN] Sent FINACK signal")
    if timer:
        timer.cancel()

    # Print statistics
    print("\n====== Transmission Statistics ======")
    print(f"Total packets sent: {len(packets)}")
    print(f"Total retransmissions: {totalRetransmissions}")


