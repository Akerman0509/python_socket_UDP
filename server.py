import socket
import os
import hashlib
import threading
import time
import random
from pathlib import Path



from dotenv import load_dotenv

load_dotenv()
def debug_log(message):
    print(f"[DEBUG] {time.strftime('%H:%M:%S')} - {message}")
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
def chunk_num(file_path, buffer_size = 1024):
# File size in bytes
    file_size = os.path.getsize(file_path)  
    temp = file_size // buffer_size
    print(f"File size: {temp} K bytes")
    chunks_num = file_size // buffer_size + 1
    print(f"Number of chunks: {chunks_num}")
    return chunks_num
def create_filename_pkt():
    server_dir = "serverFiles"
    files = os.listdir(server_dir)
    msg = "LIST:" + ",".join(files)
    print(msg)
    return msg.encode()
def create_pkt(file_name,seq_num, buffer_size = 1024):
    # print(f"Reading chunk {seq_num}")
    file_path = f"serverFiles/{file_name}"
    reading_index = buffer_size * (seq_num - 1) 
    with open(file_path, "rb") as f:
        f.seek(reading_index)
        chunk = f.read(buffer_size)
        check_sum = compute_checksum(chunk)  
        header = f"{seq_num}|{check_sum}||".encode()
        # print(f"sending chunk : {chunk}")
        result = header + chunk
        return result

def create_pkt0(file_name, data_ranges):
    # file_name = file_path.split("/")[-1]
    file_path = f"serverFiles/{file_name}"
    seq_max = chunk_num(file_path)
    metadata = f"{seq_max}|{file_name}|{data_ranges}"
    check_sum = compute_checksum(metadata.encode())
    pkt0 = f"0|{check_sum}||{metadata}".encode()
    print (f"Sending metadata: {metadata}")
    return pkt0

def check_ack_in_window(wnd_buffer, pkt_seq):
    if pkt_seq in wnd_buffer:
        return True
    return False

# return True if window is shifted
def shift_window(wnd_buffer, seq_max):
    curr_sent = wnd_buffer[-1]
    if curr_sent < seq_max:
        wnd_buffer.pop(0)
        wnd_buffer.append(curr_sent + 1)
    return
    

    

def chunks_index(seq_max, part_nums = 4, buffer_size = 1024):
    arr = []
    part_size = seq_max // part_nums
    remainder = seq_max % part_nums
    part1 = (1, part_size)
    part2 = (part_size + 1, 2 * part_size)
    part3 = (2 * part_size + 1, 3 * part_size)
    part4 = (3 * part_size + 1, seq_max)
    
    arr.append(part1)
    arr.append(part2)
    arr.append(part3)
    arr.append(part4)
    return arr


def check_full_address(client_addr):
    for i in range(len(client_addr)):
        if client_addr[i] == None:
            return False
    return True

def find_addr(server, client_addr):
    client_data_addr = [None] * 4
    while True:
        try:
            data, addr = server.recvfrom(BUFFER_SIZE)
            msg = data.decode()
            flag = msg.split(":")[0]
            if flag == "START":
                num = msg.split(":")[1]
                client_data_addr[int(num)] = addr
                print(f"Received START signal from client socket  {num}") # 0, 1, 2, 3
                if check_full_address(client_data_addr):
                    server.sendto("Address received".encode(), client_addr) #maybe drop this ??? :((
                    return client_data_addr
        except socket.timeout:
            print("Waiting for START signal ...")
            continue


def start_process_func(server, server_files):
    """Thread nhận yêu cầu file và đợi ACK của pkt0."""
    while True:
        try:
            data, addr = server.recvfrom(BUFFER_SIZE)
            msg = data.decode()
            msg_parts = msg.split(":")
            flag = msg_parts[0]

            if flag == "file_name":
                file_name = msg_parts[1]
                print(f"Received request for file_name: {file_name}")
                file_path = f"serverFiles/{file_name}"
                seq_max = chunk_num(file_path)
                print("======= max seq_num: ", seq_max)
                
                parts = chunks_index(seq_max)
                address = addr

                # Gửi pkt0 (metadata)
                pkt0 = create_pkt0(file_name, parts)
                server.sendto(pkt0, address)
                print("Sending metadata packet 0")

                # Chờ ACK cho pkt0
                while True:
                    try:
                        data, addr = server.recvfrom(BUFFER_SIZE)
                        ack_msg = data.decode()
                        if ack_msg == f"ACK:0":
                            print("Received ACK for pkt0.")
                            res = (file_name, address, seq_max, parts)
                            return res # Trả về tuple chứa thông tin cần thiết
                    except socket.timeout:
                        print("Waiting for ACK of pkt0 ...")
                        server.sendto(pkt0, address)  # Gửi lại pkt0 nếu timeout
                        continue
                    
            elif flag == "LIST":
                filename_pkt = create_filename_pkt()
                server.sendto(filename_pkt, addr)
                continue
                

        except socket.timeout:
            print("Waiting for request ...")
            continue

def add_fuel(n_shift_arr, buffer, wnd_max, seq_max, part_index, start_num):
    n_shift_arr[part_index] = wnd_max  # Increase the window shift
    buffer.clear()  
    tmp_start = seq_max - wnd_max + 1
    # print(f"tmp_start = {tmp_start}")
    new_values = []
    if start_num >= tmp_start:
        new_values = list(range(tmp_start, seq_max + 1))
    else:
        new_values = list(range(start_num, start_num + wnd_max))  # Adjusted range
    buffer += new_values  # Ensures list is modified externally
        
def handle_ack(pkt_seq, n_shift_arr, buffers, file_parts, wnd_max):
    
    # start = file_parts[0][0]    #change for debug
    # seq_max = file_parts[-1][1]
    
    n = len(file_parts)
    for i in range(n):              #change for debug
        buffer = buffers[i]
        seq_max = file_parts[i][1]
        if check_ack_in_window(buffer, pkt_seq) and n_shift_arr[i] < wnd_max:
            n_shift_arr[i] += 1
            shift_window(buffer, seq_max)
            # print(f"buffer {i}: {buffer}")
            # print(f"n_shift_arr {i}: {n_shift_arr[i]}")
    return

def identify_thread_num(seq_num, file_parts):
    for i in range(len(file_parts)):
        start, end = file_parts[i]
        if start <= seq_num <= end:
            return i
    return -1

def sendFile(server):
    # Receive thread
    def receiver():
        nonlocal file_name, address ,buffers, n_shift_arr, file_parts, send_completed, shared_cv, server,stop_flags,curr_sent_arr,continue_sending
        while not send_completed.is_set():
            try:
                data, addr = server.recvfrom(BUFFER_SIZE)
                msg = data.decode().split(":")
                flag = msg[0]
                address = addr
                
                if flag == "ACK":
                    pkt_seq = int(msg[1])
                    debug_log(f"-- Received ACK for seq_num {pkt_seq}")
                    with shared_cv:
                        # # Increase n_var only if the ACK is valid and we haven't exceeded a limit.
                        handle_ack(pkt_seq, n_shift_arr, buffers, file_parts, wnd_max)
                        print(f"**** n_shift_arr: {n_shift_arr}")
                        # print(f"buffers: {buffers}")
                        print(f"curr_sent_arr: {curr_sent_arr}")
                        # print(f"**** buffers: {buffers}")
                        # Notify sender thread that there is work to do.
                        shared_cv.notify_all()

                elif flag == "nACK":
                    pkt_seq = int(msg[1])
                    debug_log(f"++Received NACK for seq_num {pkt_seq}")
                    temp_part_index = identify_thread_num(pkt_seq, file_parts)
                    # temp_part_index = 0
                    # print(f"++ Thread number: {temp_part_index}")
  
                    pkt = create_pkt(file_name, pkt_seq)
                    server.sendto(pkt, address)
                    print(f"++ Sending Nack chunk {pkt_seq}")
                    if pkt_seq < buffers[temp_part_index][0] - 10:
                        with shared_cv:
                            continue_sending[temp_part_index] = False
                            print(f"Stop sending from thread {temp_part_index}")
                        
                elif flag == "FINISH":
                    thread_num = int(msg[1])
                    print(f"Received FINISH signal from client socket {thread_num}")
                     # set flag to stop sending thread
                    with shared_cv:
                        stop_flags[thread_num] = True
                        print(f"++++++++++++++ stop_flags: {stop_flags}")
                        
                elif flag == "Continue":
                    pkt_seq = int(msg[1])
                    # temp_part_index = 0 # for debugging 
                    temp_part_index = identify_thread_num(pkt_seq, file_parts)
                    
                    with shared_cv:
                        continue_sending[temp_part_index] = True
                        print(f"Continue sending from thread {temp_part_index} with client pkt {pkt_seq}")
                        curr_sent_arr[temp_part_index] = pkt_seq - 1
                        add_fuel(n_shift_arr, buffers[temp_part_index], wnd_max, file_parts[-1][1], temp_part_index, pkt_seq)
                        shared_cv.notify_all()
                    

            except socket.timeout:
                print("Timeout, waiting for new ACK/NACK")
                continue
    def send_file_parts(socket_data, file_name, start_end, part_index, wnd_buffer, address):
        LOSS_RATE = 0.1
        nonlocal wnd_max, server, shared_cv, n_shift_arr,stop_flags,curr_sent_arr,continue_sending
        print (f"$$ start sending part {part_index}")
        # Window and state initialization
        start, end = start_end
        small_end = min(end, start + wnd_max - 1)
        with shared_cv:
            wnd_buffer.extend([i for i in range(start, small_end + 1)])
            print(f"wnd_buffer: {wnd_buffer}")
        # First-time sending of all chunks in the window.
        with shared_cv: # ???? share_lock
            current_wnd_buffer = wnd_buffer.copy()

        for seq in current_wnd_buffer:
            pkt = create_pkt(file_name, seq)
            # print(f"current addr = {current_address}")
            socket_data.sendto(pkt, address)
            print(f"Sending chunk {seq}")

        # Main sending loop: wait until there is work to do.
        while not stop_flags[part_index]:
            if continue_sending[part_index]:
                with shared_cv:
                    # Wait until n_var is greater than 0 (i.e. receiver signalled a need to send packets)
                    while n_shift_arr[part_index] == 0 :
                        if stop_flags[part_index]:
                            break
                        print(f"thread {part_index}: waiting for n_var change")
                        # shared_cv.wait(timeout=0.01)
                        shared_cv.wait(timeout=0.01)
                    # Capture the number of packets to send and reset n_var atomically.
                    print(f">>> n_shift_arr: {n_shift_arr}")
                    packets_to_send = n_shift_arr[part_index]
                    print(f"@@@ thread {part_index}: packets_to_send = {packets_to_send}")
                    n_shift_arr[part_index] = 0
                    # Also capture the latest state for the window and destination.
                    current_buffer = wnd_buffer.copy()

                # Now, outside the lock, send the packets.
                for i in range(packets_to_send):
                    # Calculate the index for the packet.
                    # (This logic follows your original idea, adjust as needed.)
                    index = -packets_to_send + i
                    sending_seq = current_buffer[index]
                    if sending_seq > curr_sent_arr[part_index]:
                        pkt = create_pkt(file_name, sending_seq)
                        debug_log(f"Sending chunk after thread {part_index}: {sending_seq}")
                        if random.random() > LOSS_RATE: # Simulate packet loss
                            socket_data.sendto(pkt, address)
                        curr_sent_arr[part_index] = sending_seq
                    else: 
                        continue

            # A short sleep to prevent tight looping; adjust as necessary.
            time.sleep(0.01)
        print(f"$$ Done sending part {part_index}")
        return
    
    server_files = load_file_list()
    while True:
        client_data_addr = []
        client_addr = None
        file_name = ""
        address = None
        seq_max = 0
        file_parts = []
        send_completed = threading.Event()    

        file_name, client_addr, seq_max, file_parts = start_process_func(server, server_files)
        wnd_max = min(40, seq_max)
        buffers = [[] for _ in range (len(file_parts))]
        
        
        client_data_addr = find_addr(server, client_addr)
        print (f"client_data_addr: {client_data_addr}") 
        print("$$$ Start the process $$$ ")
        
        # Create data sockets
        # buffer0 ,buffer1, buffer2, buffer3 = [], [], [], []
        n_shift_arr = [0, 0, 0, 0]
        continue_sending = [True, True, True, True]
        stop_flags = [False, False, False, False]
        curr_sent_arr = [0, 0, 0, 0]
        
        
        shared_lock = threading.Lock()
        shared_cv = threading.Condition(shared_lock)
        # Start the receiver thread.
        recv_thread = threading.Thread(target=receiver, daemon = True)
        recv_thread.start()
        #start sending parts
        send_threads = []
        
        num_parts = len(file_parts)
        for i in range(num_parts):
        # for k in range(1):
            # i = 3
            thread = threading.Thread(target=send_file_parts, args=(server, file_name, file_parts[i], i, buffers[i],client_data_addr[i]))
            thread.start()
            send_threads.append(thread)

        for thread in send_threads:
            thread.join()
        
        
        # start1 = file_parts[0][0]
        # end1 = file_parts[-1][1]
        # start_end = (start1, end1)
        # print(f"+++ start_end = {start_end}")
        # thread = threading.Thread(target=send_file_parts, args=(server, file_name, start_end,  0, buffers[0],client_data_addr[0]))
        # thread.start()  
        
        # thread.join()
        print("===============All threads joined================")
        
        send_completed.set()
        recv_thread.join()

        print(f"==> Sending file {file_name} completed!")
        
        
    return 1



def load_file_list():
    FILE_LIST_PATH = Path("serverFiles/")
    if not FILE_LIST_PATH.exists():
        return []
    files = [f.name for f in FILE_LIST_PATH.iterdir() if f.is_file()]
    print(f"Files in server directory: {files}")
    return files

        
        
        
        
        

        
def server_side():
    HOST_IP = "127.0.0.1"
    MAIN_PORT = 3000

    # Create a socket using IPv4 and UDP
    RESEND_TIMEOUT = 1  # Timeout in seconds
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((HOST_IP, MAIN_PORT)) 
    server.settimeout(RESEND_TIMEOUT)

    print(f"Server is running on {HOST_IP}:{MAIN_PORT}")
    
    
    sendFile(server)
    
    
BUFFER_SIZE = 1024

# Port to listen on (non-privileged ports are > 1023)
# 0 to 65,535
server_side()


