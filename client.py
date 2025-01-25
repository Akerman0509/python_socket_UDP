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
        # print ("Checksum matched")
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
        return None, None
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
        return None, None
    # append_file("clientFile/output.png",chunk)
    # print(f"Receiving seq_num: {seq_num}")
    # print(f"recieve chunk : {chunk}")
    # ADD ACK logic
    return seq_num, chunk

def process_metadata(metadata):
    metadata = metadata.decode()
    seq_max, file_name = metadata.split("|")
    seq_max = int(seq_max)
    print(f"Receiving metadata: {metadata}")
    return seq_max, file_name
    
def send_ack(client,seq_num):
    ack = f"{seq_num}".encode()
    client.sendto(ack, SERVER_ADD)
    return


def handle_pkt0(client):
    print("handle_pkt0")
    seq_max = 0
    seq_num = -1
    file_name = ""
    while True:
        try:
            send_ack(client,0)
            data, addr = client.recvfrom(BUFFER_SIZE)
            seq_num, chunk = process_pkt(data)

            if (seq_num == 0):
                seq_max, file_name = process_metadata(chunk)
                print(f"Receiving metadata: {seq_max} and {file_name}")
                send_ack(client,1)
                return seq_max, file_name  
        except socket.timeout:
            print("Timeout")

def handle_pkt(client):
    while True:
        try:
            data, addr = client.recvfrom(BUFFER_SIZE)
            seq_num, chunk = process_pkt(data)
            if (seq_num == None or chunk == None):
                return seq_num, chunk, False
            else:
                return seq_num +1 , chunk, True
        except socket.timeout:
            print("Timeout")
            return None, None, False

def send_fname(client, file_name):
    while True:
        try:
            pkt0 = f"{file_name}".encode()
            client.sendto(pkt0, SERVER_ADD)
            data, addr = client.recvfrom(BUFFER_SIZE)
            if (data.decode() == f"ACK for {file_name}"):
                print(f"received ACK for {file_name}")
                return True
        except socket.timeout:
            print("Timeout for first pkt")
    


def receive_file(client):
    # print("Receiving file-----------------")
    FLAG1 = True

    seq_max, file_name = handle_pkt0(client)
    buffer_arr = [False] * seq_max
    buffer_arr[0] = True
    current_rcv = 0
    seq_num = 0
    while FLAG1:
        seq_num, chunk, success = handle_pkt(client)
        if (success == False):
            # not write file
            continue
        else:
            # buffer_arr[seq_num] = True
            append_file(f"clientFile/{file_name}",chunk)
        if (seq_num == seq_max +1 ):
            FLAG1 = False
        send_ack(client, seq_num)
    print(f"success")
    
    return
    



# HOST_ADD =   # The server's hostname or IP address
# PORT = 3000  # The port used by the server
SERVER_ADD = (os.getenv('HOST_IP'), int(os.getenv('LISTEN_PORT')))
BUFFER_SIZE = 1200
RESEND_TIMEOUT = 2  # Timeout in seconds
client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.settimeout(RESEND_TIMEOUT)
client.connect(("127.0.0.1",2000))

# Open a file for writing
output_file = "clientFile/output.png"

if(send_fname(client,"hello.txt")):
    receive_file(client)


print(f"File saved as {output_file}")