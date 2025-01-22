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
    with open(file_name, "rb") as f:
        f.seek(buffer_size * seq_num)
        chunk = f.read(buffer_size)
        check_sum = compute_checksum(chunk)  
        header = f"{seq_num}|{check_sum}||".encode()
        # print(f"sending chunk : {chunk}")
        result = header + chunk
        return result
    
    
def sendFile(server, address,file_name):
    seq_max = chunk_num(file_name)
    for seq_num in range(seq_max):
        chunk = create_pkt(file_name,seq_num)
        # print("size of chunk = ", len(chunk)) 
        server.sendto(chunk, address)
    return 1
    
# Port to listen on (non-privileged ports are > 1023)
# 0 to 65,535
LISTEN_PORT  = int(os.getenv('LISTEN_PORT'))
HOST_IP = os.getenv('HOST_IP')
BUFFER_SIZE = 1024
# Create a socket using IPv4 and UDP
server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((HOST_IP, LISTEN_PORT)) 

print(f"Server is running on {HOST_IP}:{LISTEN_PORT}")

# Listen for incoming messages
while True:
    data, address = server.recvfrom(BUFFER_SIZE)  # Buffer size is 1024 bytes
    data = data.decode()
    print(f"Received message: {data} from {address}")
    if data == "exit":
        break
    elif data == "start":
        print("Start sending file")
        
        if(sendFile(server, address, "2MB.png")):
            server.sendto(b"END", address)
            print("File sent")
        else:
            print("Error")
        
    

