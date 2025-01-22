import hashlib
import sys

# def calculate_checksum(data):
#     return hashlib.md5(data).hexdigest()


# with open("2MB.png", "rb") as f:
#     a = calculate_checksum(f.read(1024))
#     print(a)

def compute_checksum(chunk: bytes) -> str:
    """
    Compute the SHA-256 checksum of a data chunk.
    
    Args:
        chunk (bytes): The data chunk to compute the checksum for.
        
    Returns:
        str: The computed checksum as a hexadecimal string.
    """
    sha256_hash = hashlib.sha256()
    sha256_hash.update(chunk)
    check_sum = sha256_hash.hexdigest()
    print(check_sum)
    print(sys.getsizeof(check_sum.encode()))
    
    return check_sum


def validate_checksum(chunk: bytes, received_checksum: str) -> bool:
    """
    Validate the checksum of a data chunk using SHA-256.
    
    Args:
        chunk (bytes): The data chunk to validate.
        received_checksum (str): The checksum received to compare against.
        
    Returns:
        bool: True if the checksums match, False otherwise.
    """
    computed_checksum = compute_checksum(chunk)
    return computed_checksum == received_checksum

# a = compute_checksum(b"hello")
# print( validate_checksum(b"hello", a) ) 
# a = b"9000000"
# print(sys.getsizeof(a))

# print(a.decode())

a =  "9"
b = b"7"
print (len(a))
print (len(b))

