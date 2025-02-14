import socket
import hashlib
import os
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

def newest_pkt(data_buffer):
    for i in range(len(data_buffer)):
        if data_buffer[i] == None:
            return i - 1
    return -1

def convert_index(seq_num, arr_base, buffer_max):
    index  = (seq_num - arr_base) % buffer_max
    return index
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

def handle_pkt0(client):
    print("handle_pkt0")
    seq_max = 0
    seq_num = -1
    file_name = ""
    while True:
        try:
            data, addr = client.recvfrom(BUFFER_SIZE)
            seq_num, chunk = process_pkt(data)

            if (seq_num == 0):
                seq_max, file_name = process_metadata(chunk)
                print(f"Receiving metadata: {seq_max} and {file_name}")
                send_ack(client,0)
                return seq_max, file_name  
        except socket.timeout:
            send_Nack(client, 0)
            print("Timeout for pkt0")
            
def append_file(file_name, chunk):
    with open(file_name,"ab") as f:
        f.write(chunk)
        
def append_file2(file_name, data_buffer, wnd_max):
    print("$$ write to file")
    file_path = f"clientFiles/{file_name}"
    data = data_buffer[:wnd_max]
    # print(f"data buffer: {data_buffer}")
    # print(f"data: {data}")
    # print (f"len data = {len(data)}")
    with open(file_path,"ab") as f:
        for i in range(len(data)):
            print (f"writing chunk {i}")
            if data[i] == "dummy":
                continue
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
    msg = f"ACK:{seq_num}"
    ack = f"{msg}".encode()
    client.sendto(ack, SERVER_ADD)
    return

def send_Nack(client,seq_num):
    msg = f"nACK:{seq_num}"
    ack = f"{msg}".encode()
    client.sendto(ack, SERVER_ADD)
    return



def send_fname(client, file_name):
    #delete file if exist
    if (os.path.exists(f"clientFiles/{file_name}")):
        os.remove(f"clientFiles/{file_name}")
    while True:
        try:
            pkt0 = f"file_name:{file_name}".encode()
            client.sendto(pkt0, SERVER_ADD)
            # data, addr = client.recvfrom(BUFFER_SIZE)
            # if (data.decode() == f"ACK for {file_name}"):
            #     print(f"received ACK for {file_name}")
            seq_max, file_name= handle_pkt0(client)
            
            return seq_max, file_name
        except socket.timeout:
            print("Timeout for first pkt")
    

def receive_file(client, file_name ):
    seq_max, file_name2 = send_fname(client, file_name)
    wnd_max = min(seq_max+1, 40)  #change here for speed
    buffer_max = wnd_max + 10
    data_buffer = [None] * buffer_max
    data_buffer[0] = "dummy"
    arr_base = 0
    
    req_seq = 1 # dummy
    curr_seq = 1
    
    
    while True:
        try:
            data, addr = client.recvfrom(BUFFER_SIZE)
            pkt_seq, chunk = process_pkt(data)
            print(f"== Receiving pkt with seq_num: {pkt_seq}")
            if (pkt_seq == None or chunk == None):
                # nACK for failed pkt
                send_Nack(client, pkt_seq)
            else:
                # if the pkt seq out of buffer
                if (pkt_seq >= arr_base + buffer_max ):
                    continue
                # add to buffer
                index = convert_index(pkt_seq, arr_base, buffer_max) 
                data_buffer[index] = chunk
                # print("data_buffer: ", data_buffer)
                # find missing pkt with nACK
                req_seq_index = missing_pkt(data_buffer)
                if (req_seq_index != -1): # wanting missing pkt index
                    req_seq = req_seq_index + arr_base
                    print(f"send nACK for pkt {req_seq}")
                    send_Nack(client, req_seq)
                    curr_seq = req_seq - 1
                else:
                    req_seq = newest_pkt(data_buffer) + arr_base + 1 # wanting next pkt index
                    curr_seq = req_seq-1
                    
                if(req_seq < pkt_seq):
                    print(f"++ send nACK <<< for pkt {req_seq}")
                    send_Nack(client, req_seq)
                else:
                    print(f"send ACK for pkt {pkt_seq}")    
                    send_ack(client, pkt_seq) # success
                #if ack cannot reach server ???? resend in timeout
            


            # write continuous data to file
            print(f"arr_base: {arr_base}, req_seq: {req_seq}")
            if req_seq - arr_base >= wnd_max:
                append_file2(f"{file_name2}", data_buffer, wnd_max)
                # print("data_buffer: ", data_buffer)
                data_buffer = adjust_buffer(data_buffer, wnd_max, buffer_max)
                arr_base += wnd_max
            
            # stop condition
            if (curr_seq == seq_max):
                append_file2(f"{file_name2}", data_buffer, curr_seq - arr_base + 1)
                print("enough pkt, stop")
                return
        except socket.timeout:
            print(f"Timeout for pkt, send nACK for {curr_seq + 1}") 
            send_Nack(client, curr_seq + 1)
            continue
        

# def receive_file(client):
#     # print("Receiving file-----------------")
#     FLAG1 = True

#     seq_num = 0
#     while FLAG1:
#         seq_num, chunk, success = handle_pkt(client)
#         if (success == False):
#             # not write file
#             continue
#         else:
#             # buffer_arr[seq_num] = True
#             append_file(f"clientFiles/{file_name}",chunk)
#         if (seq_num == seq_max +1 ):
#             print("enough pkt, stop")
#             send_ack(client, seq_num) #send max seq_num + 1 to stop server
#             # FLAG1 = False
#             return
#         print(f"sent ack for seq_num {seq_num}")
#         send_ack(client, seq_num)
#     return
    



# HOST_ADD =   # The server's hostname or IP address
# PORT = 3000  # The port used by the server
SERVER_ADD = (os.getenv('HOST_IP'), int(os.getenv('LISTEN_PORT')))
BUFFER_SIZE = 1200
RESEND_TIMEOUT = 2  # Timeout in seconds
client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.settimeout(RESEND_TIMEOUT)
client.connect(("127.0.0.1",2000))

# Open a file for writing
# file_name = "hello.txt"
# file_name = "40KB.txt"
# file_name = "2MB.png"
# file_name = "10MB.pdf"
# file_name = "200MB_2.pdf"
file_name = "230MB.mp4"


receive_file(client, file_name) 


print(f"File saved as {file_name}")