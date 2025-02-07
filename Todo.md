# Todo

how to download file in python UDP socket✅
## Server
add header✅
- sequence✅
- checksum✅

send file name


add logic for ack response

timeout for ack response
resend logic for timeout

## Client
receive file✅
append file first to check✅
ack from client✅
link file parts based on sequence number
(only stop-and-wait)✅



buffer setting for both



# command
netstat -an | grep 127.0.0



# Notes
use delimeter✅
1.050000 CHUNK MAX✅

not encode for sequence and checksum yet for debugging
handle file already exists
- use go back N




# Bug
ảnh ko nhận full, chỉ nhận 1 phần (do chưa cài ACK và thứ tự)



# idea
first pkt contain:
filename
number of pkt



client only write consecutive sequence

must send pkt0 successfully

client send ack = 0 first

WRITE file if consecutive and shrink buffer

handle ack timeout in distinc function, the send function just based on returned ack

concurrency????


2461

pkt0 sending metadata (filename, number of pkt)
client send ack = 0 first
then client send ack = 1 and server start sending file

delete file if exists✅


# Progress
can send 3kb file