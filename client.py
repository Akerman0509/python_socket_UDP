import socket
import hashlib
import os
from dotenv import load_dotenv

load_dotenv()
# exist_flag = True
def compute_checksum(chunk: bytes) -> str:
    sha256_hash = hashlib.sha256()
    sha256_hash.update(chunk)
    check_sum = sha256_hash.hexdigest()
    # print(check_sum)
    return check_sum
def validate_checksum(chunk: str, received_checksum: str) -> bool:
    computed_checksum = compute_checksum(chunk)
    # print (f"computed_checksum = {computed_checksum}")
    # print (f"received_checksum = {received_checksum}")
    if (computed_checksum == received_checksum):
        print ("Checksum matched")
        return True
    print ("Checksum not matched")
    return False

def append_file(file_name, chunk):
    with open(file_name,"ab") as f:
        f.write(chunk)
def process_pkt(data):
    # Find the header and binary data split
    header_end_idx = data.find(b'||')  # Locate the end of the header
    if header_end_idx == -1:
        print("Invalid packet format")
        return

    # Decode the header
    header = data[:header_end_idx].decode()  # Decode only the header part
    # print (f"header = {header}")
    seq_num, check_sum = header.split("|")
    seq_num = int(seq_num)
    # The rest is the binary data    
    chunk = data[header_end_idx + 2:]  
    # print(f"receive chunk : {chunk}")
    if(not validate_checksum(chunk,check_sum)):
        # add resend logic
        return
    append_file("clientFile/output.png",chunk)
    
    
    # ADD ACK logic
    return
    

    
    
    



# HOST_ADD =   # The server's hostname or IP address
# PORT = 3000  # The port used by the server
SERVER_ADD = (os.getenv('HOST_IP'), int(os.getenv('LISTEN_PORT')))
BUFFER_SIZE = 1200

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.connect(("127.0.0.1",2000))
# Notify the server to start sending the file
client.sendto(b"start", SERVER_ADD)

# Open a file for writing
output_file = "clientFile/output.png"
while True:
    # Receive data
    data, addr = client.recvfrom(BUFFER_SIZE)
    # Check for end of transmission signal
    if data == b"END":
        print("File transfer complete.")
        break
    process_pkt(data)


print(f"File saved as {output_file}")