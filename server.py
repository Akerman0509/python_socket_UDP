import socket
import os
import hashlib
import sys
import threading
import time


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
def chunk_num(file_path, buffer_size = 1024):
# File size in bytes
    file_size = os.path.getsize(file_path)  
    temp = file_size // buffer_size
    print(f"File size: {temp} K bytes")
    chunks_num = file_size // buffer_size + 1
    print(f"Number of chunks: {chunks_num}")
    return chunks_num
    
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
    
# def handle_ack(server):
    # Window and state initialization
    wnd_max = 40 #change here for speed
    wnd_buffer = []
    curr_sent = wnd_max - 1
    file_name = ""
    address = None
    FLAG1 = True
    n_var = 0  # This counter indicates how many packets need to be sent.
    file_name_received = threading.Event()

    # One lock and a condition variable for all shared variables
    shared_lock = threading.Lock()
    shared_cv = threading.Condition(shared_lock)

    def receiver():
        nonlocal file_name, address, wnd_buffer, wnd_max, curr_sent, n_var, FLAG1
        seq_max = 0
        while FLAG1:
            try:
                data, addr = server.recvfrom(BUFFER_SIZE)
                msg = data.decode()
                parts = msg.split(":")
                flag = parts[0]

                if flag == "file_name":
                    with shared_cv:
                        file_name = parts[1]
                        print(f"Received request for file_name: {file_name}")
                        file_path = f"serverFiles/{file_name}"
                        seq_max = chunk_num(file_path)
                        print("======= max seq_num: ", seq_max)
                        # Adjust window size according to total chunks
                        wnd_max = min(wnd_max, seq_max + 1)
                        wnd_buffer = [i for i in range(wnd_max)]
                        print("======= wnd_buffer: ", wnd_buffer)
                        address = addr
                        file_name_received.set()
                        shared_cv.notify_all()

                elif flag == "ACK":
                    pkt_seq = int(parts[1])
                    print(f"-- Received ACK for seq_num {pkt_seq}")
                    with shared_cv:
                        print(f"*** current_buffer (receiver): {wnd_buffer}")
                        print(f"*** curr_sent: {curr_sent}, n_var: {n_var}")
                        # Increase n_var only if the ACK is valid and we haven't exceeded a limit.
                        if check_ack_in_window(wnd_buffer, pkt_seq) and n_var < wnd_max:
                            n_var += 1
                            curr_sent = shift_window(wnd_buffer, curr_sent, seq_max)
                            # Notify sender thread that there is work to do.
                            shared_cv.notify_all()

                elif flag == "nACK":
                    pkt_seq = int(parts[1])
                    print(f"++ Received NACK for seq_num {pkt_seq}")
                    # Immediately resend the requested packet.
                    pkt = create_pkt(file_name, pkt_seq)
                    server.sendto(pkt, addr)
                    print(f"++ Sending Nack chunk {pkt_seq}")

            except socket.timeout:
                print("Timeout, waiting for new ACK/NACK")
                continue

    # Start the receiver thread.
    recv_thread = threading.Thread(target=receiver, daemon = True)
    # recv_thread.daemon = True
    recv_thread.start()

    # Wait until the file_name and window are initialized.
    file_name_received.wait()

    # First-time sending of all chunks in the window.
    with shared_lock:
        current_wnd_buffer = wnd_buffer.copy()
        current_file_name = file_name
        current_address = address

    for seq in current_wnd_buffer:
        if seq == 0:
            pkt0 = create_pkt0(current_file_name)
            server.sendto(pkt0, current_address)
            print(f"Sending chunk {seq}")
        else:
            pkt = create_pkt(current_file_name, seq)
            server.sendto(pkt, current_address)
            print(f"Sending chunk {seq}")

    # Main sending loop: wait until there is work to do.
    while True:
        with shared_cv:
            # Wait until n_var is greater than 0 (i.e. receiver signalled a need to send packets)
            while n_var == 0:
                shared_cv.wait(timeout=0.01)
            # Capture the number of packets to send and reset n_var atomically.
            packets_to_send = n_var
            n_var = 0
            # Also capture the latest state for the window and destination.
            current_buffer = wnd_buffer.copy()
            current_file_name = file_name
            current_address = address

        # Now, outside the lock, send the packets.
        for i in range(packets_to_send):
            # Calculate the index for the packet.
            # (This logic follows your original idea, adjust as needed.)
            index = -packets_to_send + i
            if current_buffer[index] == 0:
                pkt0 = create_pkt0(current_file_name)
                server.sendto(pkt0, current_address)
                print("Resending metadata packet 0")
            else:
                pkt = create_pkt(current_file_name, current_buffer[index])
                print(f"Sending chunk after: {current_buffer[index]}")
                server.sendto(pkt, current_address)

        # A short sleep to prevent tight looping; adjust as necessary.
        time.sleep(0.01)
    
# def send_file_parts(socket_data, file_name, start_end, part_index, wnd_max, wnd_buffer):
#     print (f"start sending part {part_index}")
#     # Window and state initialization
#     start, end = start_end
#     wnd_buffer = [i for i in range(start, end + 1)]
#     curr_sent = wnd_max - 1
#     FLAG1 = True
#     n_var = 0  # This counter indicates how many packets need to be sent.
#     address = None
#     # One lock and a condition variable for all shared variables
#     shared_lock = threading.Lock()
#     shared_cv = threading.Condition(shared_lock)
#     find_addr = threading.Event()
    
#     def receiver():
#         nonlocal file_name, address, wnd_buffer, wnd_max, curr_sent, n_var, FLAG1
#         seq_max = 0
#         while FLAG1:
#             try:
#                 data, addr = socket_data.recvfrom(BUFFER_SIZE)
#                 msg = data.decode()
#                 parts = msg.split(":")
#                 flag = parts[0]
#                 address = addr
#                 if flag == "START":
#                     print("Received START signal")
#                     find_addr.set()
#                     continue
#                 elif flag == "ACK":
#                     pkt_seq = int(parts[1])
#                     print(f"-- Received ACK for seq_num {pkt_seq}")
#                     with shared_cv:
#                         print(f"*** current_buffer (receiver): {wnd_buffer}")
#                         print(f"*** curr_sent: {curr_sent}, n_var: {n_var}")
#                         # Increase n_var only if the ACK is valid and we haven't exceeded a limit.
#                         if check_ack_in_window(wnd_buffer, pkt_seq) and n_var < wnd_max:
#                             n_var += 1
#                             curr_sent = shift_window(wnd_buffer, curr_sent, seq_max)
#                             # Notify sender thread that there is work to do.
#                             shared_cv.notify_all()

#                 elif flag == "nACK":
#                     pkt_seq = int(parts[1])
#                     print(f"++ Received NACK for seq_num {pkt_seq}")
#                     # Immediately resend the requested packet.
#                     if pkt_seq > end:
#                         print(f"done this part!!! part {part_index} ")
#                         return
#                     else:
#                         pkt = create_pkt(file_name, pkt_seq)
#                         socket_data.sendto(pkt, address)
#                         print(f"++ Sending Nack chunk {pkt_seq}")

#             except socket.timeout:
#                 print("Timeout, waiting for new ACK/NACK")
#                 continue

#     # Start the receiver thread.   
#     recv_thread = threading.Thread(target=receiver)
#     recv_thread.start()
#     find_addr.wait()
    
#     # First-time sending of all chunks in the window.
#     with shared_lock:
#         current_wnd_buffer = wnd_buffer.copy()

#     for seq in current_wnd_buffer:
#         pkt = create_pkt(file_name, seq)
#         # print(f"current addr = {current_address}")
#         socket_data.sendto(pkt, address)
#         print(f"Sending chunk {seq}")

#     # Main sending loop: wait until there is work to do.
#     while True:
#         with shared_cv:
#             # Wait until n_var is greater than 0 (i.e. receiver signalled a need to send packets)
#             while n_var == 0:
#                 shared_cv.wait(timeout=0.01)
#             # Capture the number of packets to send and reset n_var atomically.
#             packets_to_send = n_var
#             n_var = 0
#             # Also capture the latest state for the window and destination.
#             current_buffer = wnd_buffer.copy()
#             current_address = address

#         # Now, outside the lock, send the packets.
#         for i in range(packets_to_send):
#             # Calculate the index for the packet.
#             # (This logic follows your original idea, adjust as needed.)
#             index = -packets_to_send + i
#             pkt = create_pkt(file_name, current_buffer[index])
#             print(f"Sending chunk after: {current_buffer[index]}")
#             socket_data.sendto(pkt, current_address)

#         # A short sleep to prevent tight looping; adjust as necessary.
#         time.sleep(0.01)
    

def chunks_index(seq_max, part_nums = 4, buffer_size = 1024):
    arr = []
    delimeter = part_nums - 1
    part_size = seq_max // delimeter
    part1 = (1, part_size)
    part2 = (part_size + 1, 2 * part_size)
    part3 = (2 * part_size + 1, 3 * part_size)
    arr.append(part1)
    arr.append(part2)
    arr.append(part3)
    if seq_max % delimeter != 0:
        part4 = (3 * part_size + 1, seq_max)
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
            flag, num = msg.split(":")
            if flag == "START":
                client_data_addr[int(num)] = addr
                print(f"Received START signal from client socket  {num}") # 0, 1, 2, 3
                if check_full_address(client_data_addr):
                    server.sendto("Address received".encode(), client_addr) #maybe drop this ??? :((
                    return client_data_addr
        except socket.timeout:
            print("Waiting for START signal ...")
            continue


def start_process_func(server):
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

        except socket.timeout:
            print("Waiting for request ...")
            continue

def handle_ack(pkt_seq, n_shift_arr, buffers, file_parts, wnd_max):
    n = len(file_parts)
    for i in range(n):
        buffer = buffers[i]
        seq_max = file_parts[i][1]
        start = file_parts[i][0]
        if check_ack_in_window(buffer, pkt_seq) and n_shift_arr[i] < wnd_max and n_shift_arr[i] < seq_max - wnd_max - start + 1:
            n_shift_arr[i] += 1
            shift_window(buffer, seq_max)
            # print(f"buffer {i}: {buffer}")
            # print(f"n_shift_arr {i}: {n_shift_arr[i]}")
    return

def check_finishing_threads(stop_flags):    
    return all(stop_flags) 
def sendFile(server):


    client_data_addr = []
    client_addr = None
    file_name = ""
    address = None
    seq_max = 0
    file_parts = []
    FLAG1 = True
    

    file_name, client_addr, seq_max, file_parts = start_process_func(server)
    wnd_max = min(30, seq_max)
    buffers = [[] for _ in range (len(file_parts))]
    
    
    client_data_addr = find_addr(server, client_addr)
    print (f"client_data_addr: {client_data_addr}") 
    print("$$$ Start the process $$$ ")
    
    # Create data sockets
    # buffer0 ,buffer1, buffer2, buffer3 = [], [], [], []
    n_shift_arr = [0, 0, 0, 0]
    stop_flags = [False, False, False, False]
    
    shared_lock = threading.Lock()
    shared_cv = threading.Condition(shared_lock)
    
    # Receive thread
    def receiver():
        nonlocal file_name, address, seq_max ,buffers, n_shift_arr, file_parts, FLAG1, shared_cv, server,stop_flags
        while FLAG1:
            try:
                data, addr = server.recvfrom(BUFFER_SIZE)
                msg = data.decode().split(":")
                flag = msg[0]
                address = addr
                
                if flag == "ACK":
                    pkt_seq = int(msg[1])
                    print(f"-- Received ACK for seq_num {pkt_seq}")
                    with shared_cv:
                        # print(f"*** current_buffer (receiver): {wnd_buffer}")
                        # print(f"*** curr_sent: {curr_sent}, n_var: {n_var}")
                        # # Increase n_var only if the ACK is valid and we haven't exceeded a limit.
                        handle_ack(pkt_seq, n_shift_arr, buffers, file_parts, wnd_max)
                        # print(f"**** n_shift_arr: {n_shift_arr}")
                        # Notify sender thread that there is work to do.
                        shared_cv.notify_all()

                elif flag == "nACK":
                    pkt_seq = int(msg[1])
                    print(f"++Received NACK for seq_num {pkt_seq}")
                    # Immediately resend the requested packet.
                    pkt = create_pkt(file_name, pkt_seq)
                    server.sendto(pkt, address)
                    print(f"++ Sending Nack chunk {pkt_seq}")
                        
                elif flag == "FINISH":
                    thread_num = int(msg[1])
                    print(f"Received FINISH signal from client socket {thread_num}")
                     # set flag to stop sending thread
                    with shared_cv:
                        stop_flags[thread_num] = True
                    

            except socket.timeout:
                print("Timeout, waiting for new ACK/NACK")
                continue
    
    def send_file_parts(socket_data, file_name, start_end, part_index, wnd_buffer, address):
        nonlocal wnd_max, server, shared_cv, n_shift_arr,stop_flags
        print (f"$$ start sending part {part_index}")
        # Window and state initialization
        start, end = start_end
        small_end = min(end, start + wnd_max - 1)
        with shared_cv:
            wnd_buffer.extend([i for i in range(start, small_end + 1)])
            print(f"wnd_buffer: {wnd_buffer}")
        FLAG1 = True
        # First-time sending of all chunks in the window.
        with shared_lock:
            current_wnd_buffer = wnd_buffer.copy()

        for seq in current_wnd_buffer:
            pkt = create_pkt(file_name, seq)
            # print(f"current addr = {current_address}")
            socket_data.sendto(pkt, address)
            print(f"Sending chunk {seq}")

        # Main sending loop: wait until there is work to do.
        while not stop_flags[part_index]:
            with shared_cv:
                # Wait until n_var is greater than 0 (i.e. receiver signalled a need to send packets)
                n_var = n_shift_arr[part_index]
                # print(f"n_var = {n_var}")
                while n_var == 0:
                    shared_cv.wait(timeout=0.01)
                # Capture the number of packets to send and reset n_var atomically.
                packets_to_send = n_var
                n_shift_arr[part_index] = 0
                # Also capture the latest state for the window and destination.
                current_buffer = wnd_buffer.copy()

            # Now, outside the lock, send the packets.
            for i in range(packets_to_send):
                # Calculate the index for the packet.
                # (This logic follows your original idea, adjust as needed.)
                index = -packets_to_send + i
                pkt = create_pkt(file_name, current_buffer[index])
                print(f"Sending chunk after: {current_buffer[index]}")
                socket_data.sendto(pkt, address)

            # A short sleep to prevent tight looping; adjust as necessary.
            time.sleep(0.01)
        print(f"$$ Done sending part {part_index}")
            
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

    print("==> File sending completed!")
    return 1


def rcv_file_request(server):
    return

def server_side():
    HOST_IP = os.getenv('HOST_IP')
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


