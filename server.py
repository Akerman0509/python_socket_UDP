import socket
import os
import hashlib
import sys

from dotenv import load_dotenv

load_dotenv()

def compute_checksum(chunk: bytes) -> str:
    """
    Compute the SHA-256 checksum of a data chunk.
    
    Args:
        chunk (bytes): The data chunk to compute the checksum for.
        
    Returns:
        str: The computed checksum as a hexadecimal string.
        256 bits = 32 bytes
    """
    sha256_hash = hashlib.sha256()
    sha256_hash.update(chunk)
    check_sum = sha256_hash.hexdigest()
    # print(check_sum)
    return check_sum
def chunk_num(file_name, buffer_size = 1024):
# File size in bytes
    file_size = os.path.getsize(file_name)  
    temp = file_size // buffer_size
    print(f"File size: {temp} K bytes")
    chunks_num = file_size // buffer_size + 1
    print(f"Number of chunks: {chunks_num}")
    return chunks_num
    
def create_pkt(file_name,seq_num, buffer_size = 1024):
    print(f"Reading chunk {seq_num}")
    reading_index = buffer_size * (seq_num - 1) 
    with open(file_name, "rb") as f:
        f.seek(reading_index)
        chunk = f.read(buffer_size)
        check_sum = compute_checksum(chunk)  
        header = f"{seq_num}|{check_sum}||".encode()
        # print(f"sending chunk : {chunk}")
        result = header + chunk
        return result

def create_pkt0(file_name):
    seq_max = chunk_num(file_name)
    metadata = f"{seq_max}|{file_name}"
    check_sum = compute_checksum(metadata.encode())
    pkt0 = f"0|{check_sum}||{metadata}".encode()
    print (f"Sending metadata: {metadata}")
    
    return pkt0

def rcv_req(server):
    while True:
        try:
            data, address = server.recvfrom(BUFFER_SIZE)
            file_name = data.decode()
            server.sendto(f"ACK for {file_name}".encode(), address)
            return file_name, address
        except socket.timeout:
            print("Waiting for request ...")
            continue

def handle_ack(server, address,file_name ,curr_seq):
    while True:
        try:
            data, _ = server.recvfrom(BUFFER_SIZE)
            seq_num = int(data.decode())
            #resend metadata
            if seq_num == 0:
                pkt0 = create_pkt0(file_name)
                server.sendto(pkt0, address)
                continue
            if seq_num == curr_seq + 1:
                print(f"Received ACK for seq_num {seq_num}")
                return curr_seq + 1
            else:
                return curr_seq
        except socket.timeout:
            print("Timeout")
            return curr_seq
    


def sendFile(server,file_name, address):
    seq_num = 0
    curr_seq = 0
    seq_max = chunk_num(file_name)
    while True:
        seq_num = handle_ack(server, address,file_name, seq_num)
        if (seq_num == curr_seq):
            print(f"Resending seq_num: {seq_num}")
        else:
            curr_seq = seq_num
        print(f"new seq_num sent: {curr_seq}")
        if seq_num == seq_max +1 :
            print("All the chunks are sent")
            break
        pkt = create_pkt(file_name,seq_num)
        server.sendto(pkt, address)
    
    
    return 1
    
# Port to listen on (non-privileged ports are > 1023)
# 0 to 65,535
LISTEN_PORT  = int(os.getenv('LISTEN_PORT'))
HOST_IP = os.getenv('HOST_IP')

BUFFER_SIZE = 1024
# Create a socket using IPv4 and UDP
RESEND_TIMEOUT = 2  # Timeout in seconds
server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((HOST_IP, LISTEN_PORT)) 
server.settimeout(RESEND_TIMEOUT)

print(f"Server is running on {HOST_IP}:{LISTEN_PORT}")


file_name, address = rcv_req(server)
print(f"Received request for file: {file_name}")
sendFile(server, file_name, address)

print("File sent successfully")