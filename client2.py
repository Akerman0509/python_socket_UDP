import socket
import hashlib
import os
import threading
import time

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
            print("Timeout for pkt0")



def send_fname(client, file_name):
    #delete file if exist
    if (os.path.exists(f"clientFile/{file_name}")):
        os.remove(f"clientFile/{file_name}")
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
    

def handle_pkt(client):
    while True:
        try:
            data, addr = client.recvfrom(BUFFER_SIZE)
            seq_num, chunk = process_pkt(data)
            print(f"Receiving seq_num: {seq_num}")
            if (seq_num == None or chunk == None):
                return seq_num, chunk, False
            else:
                return seq_num +1 , chunk, True
        except socket.timeout:
            print("Timeout for pkt")
            return None, None, False
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
            append_file(f"clientFiles/{file_name}",chunk)
        if (seq_num == seq_max +1 ):
            print("enough pkt, stop")
            send_ack(client, seq_num) #send max seq_num + 1 to stop server
            # FLAG1 = False
            return
        print(f"sent ack for seq_num {seq_num}")
        send_ack(client, seq_num)
    
    return

INPUT_FILE = "input.txt" 
processed_files = set()
file_queue = [] 

def debug_log(message):
    print(f"[DEBUG] {time.strftime('%H:%M:%S')} - {message}")

def read_new_files():
    debug_log("Scanning input.txt...")
    
    if not os.path.exists(INPUT_FILE):
        open(INPUT_FILE, "w").close()  
        return []

    with open(INPUT_FILE, "r") as f:
        all_files = {line.strip() for line in f if line.strip()}  

    # Filter out processed files
    new_files = list(all_files - processed_files)

    if new_files:
        debug_log(f"New file: {new_files}")

    return new_files


def scanFile():
    while True:
        debug_log("check file input.txt...")
        new_files = read_new_files()
        if new_files:
            file_queue.extend(new_files)  
            processed_files.update(new_files) 
            debug_log(f"Queue: {file_queue}")
        time.sleep(5)  


# HOST_ADD =   # The server's hostname or IP address
# PORT = 3000  # The port used by the server


# Open a file for writing
# file_name = "hello.txt"
# file_name = "2MB.png"
# file_name = "10MB.pdf"

# if(send_fname(client,file_name)):
#     receive_file(client)


# print(f"File saved as {file_name}")
SERVER_ADD = (os.getenv('HOST_IP'), int(os.getenv('LISTEN_PORT')))
BUFFER_SIZE = 1200
RESEND_TIMEOUT = 2  # Timeout in seconds
client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.settimeout(RESEND_TIMEOUT)
client.connect(("127.0.0.1",2000))

def request_file_list(client):
    try:
        client.sendto("LIST".encode(), SERVER_ADD) 
        data, addr = client.recvfrom(BUFFER_SIZE)  
        file_list = data.decode().split("\n")  
        print("\nAvailable Files:")
        for file in file_list:
            print(f" - {file}")
        return file_list
    except socket.timeout:
        print("Timeout")
        return []






# Scan file every 5 seconds
read_new_files()
scanner_thread = threading.Thread(target=scanFile, daemon=True)
scanner_thread.start()

def main():

   
    global running
    running = True
    scanner_thread = threading.Thread(target=scanFile, daemon=True)
    scanner_thread.start()
    
    #  Request file list from server
    file_list = request_file_list(client)
    try:
        while running:
            if file_queue:
                file_name = file_queue.pop(0)
                debug_log(f"Take file from queue: {file_name}")
                #Download file
                debug_log(f"Queue after download : {file_queue}")
            else:
                debug_log("No file in queue...")
                time.sleep(1)
    except KeyboardInterrupt:
        running = False  
        time.sleep(1)
        debug_log("Exit!")

if __name__ == "__main__":
    main()