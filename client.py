import socket
import hashlib
import os
import threading
import ast
from dotenv import load_dotenv

load_dotenv()
# exist_flag = True

def missing_pkt(data_buffer):
    miss_flag = False
    data_after = False
    index = -1
    for i in range(len(data_buffer)):
        if data_buffer[i] == None:
            miss_flag = True
            index = i
            break
    for k in range(index + 1, len(data_buffer)):
        if data_buffer[k] != None:
            data_after = True
            break
    if miss_flag and data_after:
        return index
    return -1

# newest received pkt index
def newest_pkt(start, arr_base, data_buffer):
    for i in range(len(data_buffer)):
        if data_buffer[i] == None:
            index  = i + arr_base + start - 1
            return index
    return -1

def index_to_seq(start, index, arr_base):
    seq_num = index + arr_base + start
    return seq_num
def seq_to_index(start, seq_num, arr_base, buffer_max):
    index  = (seq_num - arr_base - start) % buffer_max
    return index
def count_consec(start, curr_seq, arr_base):
    tmp  = curr_seq - arr_base - start + 1
    return tmp
def adjust_buffer(data_buffer, wnd_max, buffer_max):    
    # bool_buffer = bool_buffer[10:]
    data_buffer = data_buffer[wnd_max:]
    
    # bool_buffer.extend([False] * (20 - len(bool_buffer)))
    data_buffer.extend([None] * (buffer_max - len(data_buffer)))
    return data_buffer
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

def handle_pkt0(client, server_addr):
    print("handle_pkt0")
    seq_max = 0
    seq_num = -1
    file_name = ""
    while True:
        try:
            data, addr = client.recvfrom(BUFFER_SIZE)
            seq_num, chunk = process_pkt(data)

            if (seq_num == 0):
                seq_max, file_name, data_ranges = process_metadata(chunk)
                print(f"Receiving metadata: {seq_max} and {file_name} and {data_ranges}")
                send_ack(client,0, server_addr)
                return seq_max, file_name ,data_ranges
        except socket.timeout:
            send_Nack(client, 0, server_addr)
            print("Timeout for pkt0")

        
def append_file(file_name, data_buffer,start, arr_base,  wnd_max):
    print("$$ write to file")
    file_path = f"clientFiles/{file_name}"
    data = data_buffer[:wnd_max]
    # print(f"data buffer: {data_buffer}")
    # print(f"data: {data}")
    # print (f"len data = {len(data)}")
    with open(file_path,"ab") as f:
        for i in range(len(data)):
            print (f"writing chunk {i + arr_base + start} to file")
            # print(f"data[i]: {data[i]}")
            f.write(data[i])
        
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

    return seq_num, chunk

def process_metadata(metadata):
    metadata = metadata.decode()
    # print(f"metadata: {metadata}")
    seq_max, file_name, data_ranges = metadata.split("|")
    seq_max = int(seq_max)
    return seq_max, file_name, data_ranges
    
def send_ack(client,seq_num, server_addr):
    msg = f"ACK:{seq_num}"
    ack = f"{msg}".encode()
    client.sendto(ack, server_addr)
    return

def send_Nack(client,seq_num, server_addr):
    msg = f"nACK:{seq_num}"
    ack = f"{msg}".encode()
    client.sendto(ack, server_addr)
    return



def send_fname(client, file_name, server_addr):
    #delete file if exist
    if (os.path.exists(f"clientFiles/{file_name}")):
        os.remove(f"clientFiles/{file_name}")
    while True:
        try:
            pkt0 = f"file_name:{file_name}".encode()
            client.sendto(pkt0, server_addr)
            # data, addr = client.recvfrom(BUFFER_SIZE)
            # if (data.decode() == f"ACK for {file_name}"):
            #     print(f"received ACK for {file_name}")
            seq_max, file_name,data_ranges = handle_pkt0(client, server_addr)
            
            return seq_max, file_name, data_ranges
        except socket.timeout:
            print("Timeout for first pkt")
    
def file_part_name(file_name, part_index):  
    return f"{file_name}_part{part_index}"
def merge_files(file_name, num_parts):
    with open(f"clientFiles/{file_name}", "wb") as outfile:
        for i in range(num_parts):
            file_part = f"clientFiles/{file_name}_part{i}"
            with open(file_part, "rb") as infile:
                outfile.write(infile.read())
            os.remove(file_part)
def receive_parts(socket_data, server_addr,  file_name, wnd_max, start_end, part_index):

    start, end = start_end
    buffer_max = wnd_max + 10
    data_buffer = [None] * buffer_max
    # data_buffer[0] = "dummy"          #no metadata, receive from index 0
    arr_base = 0
    
    req_seq = start # dummy
    curr_seq = start
    file_name = file_part_name(file_name, part_index)
    
    socket_data.sendto(f"START:0".encode(), server_addr) # potential loss
    while True:
        try:
            
            data, addr = socket_data.recvfrom(BUFFER_SIZE)
            pkt_seq, chunk = process_pkt(data)
            print(f"== Receiving pkt with seq_num: {pkt_seq}")
            if (pkt_seq == None or chunk == None):
                # nACK for failed pkt
                print("Invalid pkt")
                send_Nack(socket_data, pkt_seq, server_addr)
            else:
                # if the pkt seq out of buffer
                if (pkt_seq >= start + arr_base + buffer_max ):
                    print(f"pkt_seq {pkt_seq} out of buffer")
                    continue
                # add to buffer
                index = seq_to_index(start, pkt_seq, arr_base, buffer_max) 
                print(f"Thread {part_index} -------index = {index}")
                data_buffer[index] = chunk
                # print("data_buffer: ", data_buffer)
                # find missing pkt with nACK
                req_seq_index = missing_pkt(data_buffer)
                if (req_seq_index != -1): # wanting missing pkt index
                    req_seq = index_to_seq(start, req_seq_index, arr_base)
                    print(f"Thread {part_index} == send nACK for pkt {req_seq}")
                    send_Nack(socket_data, req_seq, server_addr)
                else:
                    req_seq = newest_pkt(start, arr_base , data_buffer) + 1
                curr_seq = req_seq-1
                    
                if(req_seq < pkt_seq):
                    print(f"Thread {part_index} ++ send nACK <<< for pkt {req_seq}")
                    send_Nack(socket_data, req_seq, server_addr)
                else:
                    print(f"Thread {part_index} == send ACK for pkt {pkt_seq}")    
                    send_ack(socket_data, pkt_seq, server_addr) # success
                #if ack cannot reach server ???? resend in timeout

            # write continuous data to file
            print(f"arr_base: {arr_base}, req_seq: {req_seq}")
            consec_pkt = count_consec(start, curr_seq, arr_base)
            if consec_pkt >= wnd_max:
                append_file(f"{file_name}", data_buffer,start , arr_base,  wnd_max)
                # print("data_buffer: ", data_buffer)
                data_buffer = adjust_buffer(data_buffer, wnd_max, buffer_max)
                arr_base += wnd_max
            
            # stop condition
            if (curr_seq >= end):
                print(f"write last bytes to file")
                append_file(f"{file_name}", data_buffer,start, arr_base,  consec_pkt )
                msg = f"FINISH:{part_index}".encode()
                socket_data.sendto(msg, server_addr)
                print(f"enough pkt for part {part_index}")
                return
        except socket.timeout:
            print(f"Timeout for pkt, send nACK for {req_seq}") 
            send_Nack(client, req_seq, server_addr)
            continue
        

def send_addr(client, server_addr, data_sockets):
    while True:
        try:    
            for i in range (len(data_sockets)):
                data_sockets[i].sendto(f"START:{i}".encode(), server_addr)
            data, _ = client.recvfrom(BUFFER_SIZE)
            if data.decode() == "Address received":
                print("Finished sending addresses")
                return
        except socket.timeout:
            print("Timeout for sending addresses")
            continue
    
def receive_file(client, server_addr, data_sockets,  file_name ):
        
    seq_max, file_name2, data_ranges_str = send_fname(client, file_name,server_addr )
    send_addr(client, server_addr, data_sockets)
    if seq_max and file_name2 and data_ranges_str:
        print(f"receive: {seq_max} and {file_name2} and {data_ranges_str}")
    
    data_ranges = ast.literal_eval(data_ranges_str)
    # for i in range(len(data_ranges)):
    #     print(f"part {i} : {data_ranges[i]}, start: {data_ranges[i][0]}, end: {data_ranges[i][1]}")
    file_path = f"clientFiles/{file_name2}"
    
    
    wnd_max = min(20 , seq_max) # change for speed
    print(f"wnd_max = {wnd_max}")
    receive_threads = []
    # threading.Thread(target=receive_parts, args=(client, server_addr, file_name2, wnd_max, data_ranges[0], 0)).start()
    num_parts = len(data_ranges)
    
    for i in range (num_parts):
    # for k in range (1):
        # i = 3
        thread = threading.Thread(target=receive_parts, args=(data_sockets[i], server_addr, file_name2, wnd_max, data_ranges[i], i))
        thread.start()
        receive_threads.append(thread)
        
    for thread in receive_threads:
        thread.join()
        
    print("All parts received")
    merge_files(file_name2, num_parts)
    return

# HOST_ADD =   # The server's hostname or IP address
# PORT = 3000  # The port used by the server
# SERVER_ADD = (os.getenv('HOST_IP'), int(os.getenv('LISTEN_PORT')))
MAIN_PORT = 3000
HOST_IP = "127.0.0.1"
server_addr = (HOST_IP, MAIN_PORT)  

BUFFER_SIZE = 1200
RESEND_TIMEOUT = 2  # Timeout in seconds
client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.settimeout(RESEND_TIMEOUT)
client.connect(("127.0.0.1",MAIN_PORT))
print(f"main socket on {client.getsockname()}")

# Create separate sockets for data transmission
socket_num = 4
data_sockets = {} #{index: socket} #start from 0
for i in range (socket_num):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(RESEND_TIMEOUT)  # Set timeout for retransmissions
    sock.connect(server_addr)
    data_sockets[i] = sock
 # Get the local address and port
    local_addr = sock.getsockname()  # Returns (local_ip, local_port)
    print(f"Data socket num {i} bound to local address {local_addr}, connected to {server_addr}")
    


# Open a file for writing
# file_name = "hello.txt"
# file_name = "40KB.txt"
# file_name = "2MB.png"
# file_name = "10MB.pdf"
# file_name = "200MB_2.pdf"
file_name = "230MB.mp4"


receive_file(client,server_addr,  data_sockets , file_name) 


print(f"File saved as {file_name}")