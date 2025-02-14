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

def create_pkt0(file_name):
    # file_name = file_path.split("/")[-1]
    file_path = f"serverFiles/{file_name}"
    seq_max = chunk_num(file_path)
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

def check_ack_in_window(wnd_buffer, pkt_seq):
    if pkt_seq in wnd_buffer:
        return True
    return False

# return True if window is shifted
def shift_window(wnd_buffer, curr_sent, seq_max):
    if curr_sent < seq_max:
        wnd_buffer.pop(0)
        wnd_buffer.append(curr_sent + 1)
        return curr_sent + 1
    else:
        return curr_sent
    
def handle_ack(server):
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
    
# def handle_ack(server):
#     wnd_max = 10
#     wnd_buffer = []
#     curr_sent = wnd_max - 1
#     buffer_index = wnd_max - 1

#     file_name = ""
#     address = None
#     shifted_flag = False
#     seq_max = 0
#     FLAG1 = True
#     n_var = 0
#     file_name_received = threading.Event()
    
#     # One lock for all shared variables
#     shared_lock = threading.Lock()

#     def receiver():
#         nonlocal file_name, address, wnd_buffer, wnd_max, curr_sent, seq_max, shifted_flag, n_var
#         # arr_Nack = []
#         arr_ack = []
        
#         while FLAG1:
#             try:
#                 data, address = server.recvfrom(BUFFER_SIZE)
#                 msg = data.decode()
#                 flag = msg.split(":")[0]
                
#                 if flag == "file_name":
#                     with shared_lock:
#                         file_name = msg.split(":")[1]
#                         print(f"Received request for file_name: {file_name}")
#                         file_path = f"serverFiles/{file_name}"  
#                         seq_max = chunk_num(file_path)
#                         print("======= max seq_num: ", seq_max)
#                         wnd_max = min(wnd_max, seq_max + 1)
#                         print("======= updated wnd_max: ", wnd_max)
#                         wnd_buffer = [i for i in range(wnd_max)]
#                         print("======= wnd_buffer: ", wnd_buffer)
#                     file_name_received.set()
                    
#                 if flag == "ACK":
#                     pkt_seq = int(msg.split(":")[1])
#                     print(f"-- Received ACK for seq_num {pkt_seq}")
#                     # arr_ack.append(pkt_seq)
#                     # print(f"++++ ACK list: {arr_ack}")
                    
#                     with shared_lock:
#                         print(f"*** current_buffer 2: {wnd_buffer}")  
#                         print(f"*** curr_sent 2: {curr_sent}, n_var: {n_var}")
#                         if check_ack_in_window(wnd_buffer, pkt_seq) and n_var <10:
#                             n_var += 1
#                             curr_sent  = shift_window(wnd_buffer, curr_sent, seq_max)
#                         # else:
#                         #     shifted_flag = False
                       
#                 if flag == "nACK":
#                     pkt_seq = int(msg.split(":")[1])
#                     print(f"++ Received NACK for seq_num {pkt_seq}")
#                     # n_var -= 1 #????
#                     # arr_Nack.append(pkt_seq)
#                     # send back immediately
#                     pkt = create_pkt(file_name, pkt_seq)
#                     server.sendto(pkt, address)
#                     print(f"++ Sending Nack chunk {pkt_seq}")
                            
                        
                       
#             except socket.timeout:
#                 print("Timeout, waiting for new ACK/NACK")
#                 continue

#     recv_thread = threading.Thread(target=receiver)
#     recv_thread.daemon = True
#     recv_thread.start()

#     file_name_received.wait()

#     # First time sending 
#     with shared_lock:
#         current_wnd_buffer = wnd_buffer.copy()
#         current_file_name = file_name
#         current_address = address

#     for i in range(len(current_wnd_buffer)):
#         if current_wnd_buffer[i] == 0:
#             pkt0 = create_pkt0(current_file_name)
#             server.sendto(pkt0, current_address)
#             print(f"Sending chunk {current_wnd_buffer[i]}")
#         else:
#             pkt = create_pkt(current_file_name, current_wnd_buffer[i])
#             server.sendto(pkt, current_address)
#             print(f"Sending chunk {current_wnd_buffer[i]}")

#     # Handle changes
#     while True:
#         with shared_lock:
#             if n_var > 0:
#                 # Copy needed values inside lock
#                 current_buffer = wnd_buffer.copy()
#                 # n_var2 = n_var
#                 current_file_name = file_name
#                 current_address = address
#                 should_send = True
#             else:
#                 should_send = False

#         # Send packets outside lock
#         if should_send:

#             while n_var > 0:
#                 print(f"*** current_buffer: {current_buffer}")  
#                 index = -n_var
#                 print(f"*** index: {index}")
#                 # Special handling for pkt0
#                 if current_buffer[index] == 0:
#                     pkt0 = create_pkt0(file_name)
#                     server.sendto(pkt0, address)
#                     print("Resending metadata packet 0")
#                 else:
#                     pkt = create_pkt(current_file_name, current_buffer[index])
#                     print(f"Sending chunk after: {current_buffer[index]}")
#                     server.sendto(pkt, current_address)
#                 n_var -= 1

#         time.sleep(0.01)

#     return True

def sendFile(server,file_path, address):
    seq_num = 0
    curr_seq = 0
    seq_max = chunk_num(file_path)
    while True:
        seq_num = handle_ack(server, address,file_path, seq_num)
        if (seq_num == curr_seq):
            print(f"Resending seq_num: {seq_num}")
        else:
            curr_seq = seq_num
        print(f"new seq_num sent: {curr_seq}")
        if seq_num == seq_max +1 :
            print("All the chunks are sent")
            break
        pkt = create_pkt(file_path,seq_num)
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


# file_name, address = rcv_req(server)
# print(f"Received request for file: {file_name}")
# file_path = f"serverFiles/{file_name}"
# sendFile(server, file_path, address)
handle_ack(server)

print("File sent successfully")