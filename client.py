import socket
import hashlib
import os
import threading
import ast
import time
import sys
import math
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
# def newest_pkt(start, arr_base, data_buffer):
#     for i in range(len(data_buffer)):
#         if data_buffer[i] == None:
#             index  = i + arr_base + start - 1
#             return index
#     return -1
def newest_pkt(start, arr_base, data_buffer):
    for i in range(len(data_buffer)):
        if data_buffer[i] == None:
            index  = i + arr_base + start - 1
            return index
    return len(data_buffer) + arr_base + start - 1

def index_to_seq(start, index, arr_base):
    seq_num = index + arr_base + start
    return seq_num
def seq_to_index(start, seq_num, arr_base, buffer_max):
    index  = (seq_num - arr_base - start)
    if index < 0 or index >= buffer_max:
        #print (f"pkt {seq_num} out of buffer")
        return index, False
    return index, True
def count_consec(start, curr_seq, arr_base):
    tmp  = curr_seq - arr_base - start + 1
    return tmp
def adjust_buffer(data_buffer, wnd_max, buffer_max):    
    # data_buffer = data_buffer[wnd_max:]
    
    # data_buffer.extend([None] * (buffer_max - len(data_buffer)))
    data_buffer.clear()
    data_buffer.extend([None] * wnd_max)
    # #print("data_buffer: ", data_buffer) 
    return data_buffer
def compute_checksum(chunk: bytes) -> str:
    sha256_hash = hashlib.sha256()
    sha256_hash.update(chunk)
    check_sum = sha256_hash.hexdigest()
    # #print(check_sum)
    return check_sum
def validate_checksum(chunk: str, received_checksum: str) -> bool:
    computed_checksum = compute_checksum(chunk)
    # #print (f"computed_checksum = {computed_checksum}")
    # #print (f"received_checksum = {received_checksum}")
    if (computed_checksum == received_checksum):
        # #print ("Checksum matched")
        return True
    #print ("Checksum not matched")
    return False

def handle_pkt0(client, server_addr, req_filename):
    #print("handle_pkt0")
    seq_max = 0
    seq_num = -1
    while True:
        try:
            data, addr = client.recvfrom(BUFFER_SIZE)
            seq_num, chunk = process_pkt(data)

            if (seq_num == 0):
                seq_max, file_name, data_ranges = process_metadata(chunk)
                #print(f"Receiving metadata: {seq_max} and {file_name} and {data_ranges}")
                send_ack(client,0, server_addr)
                return seq_max, file_name ,data_ranges
        except socket.timeout:
            #print(f"Timeout for pkt0, resend pkt0")
            pkt0 = f"file_name:{req_filename}".encode()
            client.sendto(pkt0, server_addr)


# def control_nACK (nACK_var, seq_num, creation = 0, resolved = False):
#     if creation:
#         nACK_var[seq_num] = seq_num
#         nACK_var["count_down"] = 4
#         nACK_var["resolved"] = False
#     else:
#         nACK_var["count_down"] -= 1
        
#     if resolved:
#         nACK_var["resolved"] = True
#     if nACK_var["count_down"] == 0:
#         return seq_num
#     return None
def append_file(file_name, data_buffer,start, arr_base,  wnd_max):
    #print("$$ write to file")
    file_path = f"clientFiles/{file_name}"
    data = data_buffer[:wnd_max]


    with open(file_path,"ab") as f:
        for i in range(len(data)):
            #print (f"writing chunk {i + arr_base + start} to file")
            f.write(data[i])
        
def process_pkt(data):
    # Find the header and binary data split
    header_end_idx = data.find(b'||')  # Locate the end of the header
    if header_end_idx == -1:
        #print("Invalid packet format")
        return None, None
    # Decode the header
    header = data[:header_end_idx].decode()  # Decode only the header part
    seq_num, check_sum = header.split("|")
    seq_num = int(seq_num)
    # The rest is the binary data    
    chunk = data[header_end_idx + 2:]  
    if(not validate_checksum(chunk,check_sum)):
        # add resend logic
        return None, None

    return seq_num, chunk

def process_metadata(metadata):
    metadata = metadata.decode()
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



def send_fname(client, req_filename, server_addr):
    #delete file if exist
    if (os.path.exists(f"clientFiles/{req_filename}")):
        os.remove(f"clientFiles/{req_filename}")
    while True:
        try:
            pkt0 = f"file_name:{req_filename}".encode()
            client.sendto(pkt0, server_addr)
            seq_max, file_name,data_ranges = handle_pkt0(client, server_addr,req_filename)
            
            return seq_max, file_name, data_ranges
        except socket.timeout:
            #print("Timeout for first pkt")
            continue
    
def send_continue_msg(socket_data, curr_seq, server_addr):
    msg = f"Continue:{curr_seq}".encode()
    socket_data.sendto(msg, server_addr)
    
def update_line(file_name, part_index, start, end, curr_sent):
    tmp = end - start
    if tmp == 0:
        percent = 100
    else:
        percent = (curr_sent - start) * 100 / tmp
    percent = math.ceil(percent)
    new_content = f"=> Downloading {file_name} part {part_index + 1} .... {percent}%"

    # Move cursor to the correct line
    line_number = part_index + 1 +20
    sys.stdout.write(f"\033[{line_number}H")  # Move cursor to the specific line
    sys.stdout.write("\033[2K")  # Clear the entire line
    sys.stdout.write(f"\033[{line_number}H{new_content}")  # Move cursor back & write new content
    sys.stdout.flush()
        
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
    past_missing = (0,False,4)
    outbuffer_state = False
    missing_boolen = False
    past_continue_index = 0
    max_seq_rcved = 0
    start, end = start_end
    # buffer_max = wnd_max + 10
    buffer_max = wnd_max
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
            #debug_log(f"== Receiving pkt with seq_num: {pkt_seq}")
            if (pkt_seq == None or chunk == None):
                # nACK for failed pkt
                ##print("Invalid pkt")
                send_Nack(socket_data, pkt_seq, server_addr)
            elif pkt_seq < curr_seq: # if receive duplicate pkt
                continue
            else:
                # if the pkt seq out of buffer
                if (pkt_seq >= start + arr_base + buffer_max ): 
                    if outbuffer_state == False:
                        #print(f"pkt_seq {pkt_seq} out of buffer, send nACK for {req_seq} 1 time")
                        send_Nack(socket_data, req_seq, server_addr)
                        outbuffer_state = True
                else:
                    outbuffer_state = False

                    # continue
                # add to buffer
                index, outbuffer_flag = seq_to_index(start, pkt_seq, arr_base, buffer_max) 
                # #print(f"Thread {part_index} -------index = {index}")
                if outbuffer_flag:
                    data_buffer[index] = chunk
                    max_seq_rcved = max(max_seq_rcved, pkt_seq)
                    
                    #print(f"Thread {part_index} == send ACK for pkt {pkt_seq}")    
                    send_ack(socket_data, pkt_seq, server_addr) # success
                # #print("data_buffer: ", data_buffer)
                
                if past_missing[0] == pkt_seq:  # missing pkt is resolved
                    past_missing = (pkt_seq,True,5)
                    
                # find missing pkt with nACK
                # debug_log (f"------------- past missing = {past_missing}")                            ####
                check_holes = missing_pkt(data_buffer)
                
                if (check_holes != -1): # wanting missing pkt index
                    # #print(f"%%% missing index = {check_holes}")
                    missing_boolen = True
                    req_seq = index_to_seq(start, check_holes, arr_base)
                    # debug_log(f"?? there is a hole for pkt {req_seq}")                    ####
                else:
                    req_seq = max_seq_rcved + 1
                    tmp, _ = seq_to_index(start, req_seq - 1, arr_base, buffer_max)
                    #print(f"++ newest pkt = {req_seq - 1}, -------index = {tmp}")
                    if missing_boolen == True and req_seq - 2 * wnd_max > past_continue_index:
                        #print (f"wnd_max = {wnd_max}")
                        #print(f"~~~ Sending continue Signal with curr-seq = {req_seq-1}")
                        send_continue_msg(socket_data, req_seq-1, server_addr)
                        missing_boolen = False
                        past_continue_index = req_seq - 1
                        
                    
                if past_missing[0] != req_seq: #change missing pkt
                    past_missing = (req_seq, False, wnd_max // 5)
                else: # missing pkt is the same
                    past_missing = (past_missing[0],past_missing[1],past_missing[2] - 1)
                # send nACK for missing pkt
                if past_missing[2] <= 0 and not past_missing[1] and past_missing[0] < max_seq_rcved: # missing pkt is not resolved
                    #debug_log(f"Thread {part_index} ++ send nACK02 <<< for pkt {req_seq}")
                    send_Nack(socket_data, req_seq, server_addr)
                    past_missing = (req_seq,False,wnd_max // 5)

                    
                
                curr_seq = req_seq-1
                update_line( file_name, part_index, start, end, curr_seq)

            # write continuous data to file
            #print(f"arr_base: {arr_base}, req_seq: {req_seq}")
            consec_pkt = count_consec(start, curr_seq, arr_base)
            if consec_pkt >= wnd_max:
                append_file(f"{file_name}", data_buffer,start , arr_base,  wnd_max)
                # #print("data_buffer: ", data_buffer)
                
                data_buffer = adjust_buffer(data_buffer, wnd_max, buffer_max)
                arr_base += wnd_max
            
            # stop condition
            if (curr_seq >= end):
                #print(f"write last bytes to file")
                append_file(f"{file_name}", data_buffer,start, arr_base,  consec_pkt )
                msg = f"FINISH:{part_index}".encode()
                socket_data.sendto(msg, server_addr)
                #print(f"enough pkt for part {part_index}")
                return
        except socket.timeout:
            #print(f"Timeout for pkt, send nACK for {req_seq}") 
            # send_Nack(socket_data, req_seq, server_addr)
            send_continue_msg(socket_data, req_seq, server_addr)
            continue
        

def send_addr(client, server_addr, data_sockets):
    while True:
        try:    
            for i in range (len(data_sockets)):
                data_sockets[i].sendto(f"START:{i}".encode(), server_addr)
            data, _ = client.recvfrom(BUFFER_SIZE)
            if data.decode() == "Address received":
                #print("Finished sending addresses")
                return
        except socket.timeout:
            #print("Timeout for sending addresses")
            continue
    
def receive_file(client, server_addr, data_sockets,  req_filename ):
    global IDLE_FLAG
    seq_max, file_name, data_ranges_str = send_fname(client, req_filename,server_addr )
    send_addr(client, server_addr, data_sockets)
    # if seq_max and file_name and data_ranges_str:
    #     #print(f"receive: {seq_max} and {file_name} and {data_ranges_str}")
    data_ranges = ast.literal_eval(data_ranges_str)
    curr_sent_arr = [0] * len(data_ranges)
    
    
    wnd_max = min(40 , seq_max) # change for speed
    #print(f"wnd_max = {wnd_max}")
    receive_threads = []
    num_parts = len(data_ranges)
    for i in range (num_parts):
    # for k in range (1):
        # i = 3
        thread = threading.Thread(target=receive_parts, args=(data_sockets[i], server_addr, file_name, wnd_max, data_ranges[i], i ))
        thread.start()
        receive_threads.append(thread)
        
    for thread in receive_threads:
        thread.join()
    
    # start = data_ranges[0][0]
    # end = data_ranges[-1][1]
    # start_end = (start, end)
    # #print(f"+++ start_end = {start_end}")
    # thread = threading.Thread(target=receive_parts, args=(data_sockets[0], server_addr, file_name2, wnd_max,  start_end, 0))
    # thread.start()
    
    # thread.join()
        
    #print("All parts received")
    merge_files(file_name, num_parts)
    IDLE_FLAG = True
    return

def save_filename(files):
    with open("serverAvailFiles.txt", "w") as f:
        for file in files:
            f.write(f"{file}\n")
    #print("Saved file list to serverAvailFiles.txt")
def request_file_list(client):
    file_list = []
    while True:
        try:
            client.sendto("LIST".encode(), server_addr) 
            data, addr = client.recvfrom(BUFFER_SIZE)  
            flag = data.decode().split(":")[0]
            if flag == "LIST":
                filename_str = data.decode().split(":")[1]
                file_list = filename_str.split(",")
                save_filename(file_list)
                for file in file_list:
                    print(f"File: {file}")
            return file_list
        except socket.timeout:
            #print("Timeout for requesting file list")
            continue

def debug_log(message):
    print(f"[DEBUG] {time.strftime('%H:%M:%S')} - {message}")

def read_filename():
    # debug_log("Scanning input.txt...")
    # create file if not exist
    if not os.path.exists(INPUT_FILE):
        open(INPUT_FILE, "w").close()  
        return []

    with open(INPUT_FILE, "r") as f:
        all_files = [line.strip() for line in f if line.strip()]
    # #print("all_files: ", all_files)
    return all_files

def schedule_next_scan(file_queue,files_sent, server_files):
    global RUNNING_FLAG
    """Schedule the next scan using Timer"""
    if RUNNING_FLAG:
        timer = threading.Timer(5.0, scan_file, args=[file_queue,files_sent, server_files])
        timer.start()
    
def scan_file(curr_file_queue, files_sent,server_files):
    """Kiểm tra file mới và thêm vào hàng đợi nếu file hợp lệ"""
    #print("Checking input.txt...")
    files_found = read_filename()
    #print(f"file queue: {curr_file_queue}")
    new_files = [file for file in files_found if file not in curr_file_queue]
    new_files = [file for file in new_files if file not in files_sent]
    
    #print(f"new files: {new_files}")
    for file in new_files:
        if file in server_files:
            curr_file_queue.append(file)
        else:
            print(f"File {file} not found on server")
# Schedule the next scan
    schedule_next_scan(curr_file_queue,files_sent, server_files)


def client_side():
    global RUNNING_FLAG, IDLE_FLAG
    files_sent = []
    file_queue = [] 
    # Scan file every 5 seconds
    
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.settimeout(1)
    client.connect(("127.0.0.1",MAIN_PORT))
    #print(f"main socket on {client.getsockname()}")
    
    server_files = request_file_list(client)

    # Start the first scan, which will schedule subsequent scans
    schedule_next_scan(file_queue,files_sent, server_files)

    

    
        # Create separate sockets for data transmission
    #  Request file list from server
    socket_num = 4
    data_sockets = {} #{index: socket} #start from 0
    for i in range (socket_num):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.02)  # Set timeout for retransmissions
        sock.connect(server_addr)
        data_sockets[i] = sock
    # Get the local address and port
        local_addr = sock.getsockname()  # Returns (local_ip, local_port)
        #print(f"Data socket num {i} bound to local address {local_addr}, connected to {server_addr}")
    
    # handle reading file here
        # Open a file for writing
    # file_name = "hello.txt"
    # file_name = "40KB.txt"
    # file_name = "2MB.png"
    # file_name = "730KB.pdf"
    # file_name = "10MB.pdf"
    # file_name = "200MB_2.pdf"
    # file_name = "230MB.mp4"
    # file_name = "1.1GB.mkv"
    
    # receive_file(client,server_addr,  data_sockets , file_name) 
    
    try:
        while RUNNING_FLAG:
            # send next file in queue
            if len(file_queue) and IDLE_FLAG:
                next_filename = file_queue.pop(0)
                files_sent.append(next_filename)
                #debug_log(f"Sending file: {next_filename}")
                #Download file
                #debug_log(f"Queue after download : {file_queue}")
                IDLE_FLAG = False
                receive_file(client,server_addr,  data_sockets , next_filename) 
                
    except KeyboardInterrupt:
        RUNNING_FLAG = False
        time.sleep(1)
        #debug_log("Exit!")
        client.close()
        for sock in data_sockets.values():
            sock.close()

    
MAIN_PORT = 3000
HOST_IP = "127.0.0.1"
server_addr = (HOST_IP, MAIN_PORT)  

BUFFER_SIZE = 1200
RESEND_TIMEOUT = 2  # Timeout in seconds

# client_side()
# #print("End program")
INPUT_FILE = "input.txt" 
RUNNING_FLAG = True
IDLE_FLAG = True
def main():

    client_side()
    #print("End program")

if __name__ == "__main__":
    main()