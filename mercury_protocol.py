"""
Mercury200.02 interface functions, which lay on top of the RS-485
Resources: https://github.com/mrkrasser/MercuryStats
"""


def crc16(data: bytes):
    '''
    CRC-16-ModBus checksum
    '''
    data = bytearray(data)
    poly = 0xA001
    crc = 0xFFFF
    for b in data:
        crc ^= (0xFF & b)
        for _ in range(0, 8):
            if (crc & 0x0001):
                crc = ((crc >> 1) & 0xFFFF) ^ poly
            else:
                crc = ((crc >> 1) & 0xFFFF)
    return crc


def verify_checksum(byte_list):
    """array of bytes converted to int [45, 34, 220,..]"""
    tail = byte_list[-2:]
    head = byte_list[:-2]
    
    tail_bytes = '0x'+''.join([hex(b)[2:] if len(hex(b)[2:])==2 else '0'+hex(b)[2:] for b in tail[::-1]])
    if tail_bytes == hex(crc16(bytearray(head))):
        return True
    return False


def decode_tarif_data(data):
    """
    T1, T2, T3, T4.
    data is expected in RAW bytes array converted to int
    with no command and no checksum
    """
    if len(data) !=16 :
        print(f"Wrong bytes number in response: '{data}'")
        return [[]]*4

    tarif_data = [data[x*4:x*4+4] for x in range(len(data)//4)]
    counters = []
    for t in tarif_data:
        counters.append(bytes_to_int(t)/100)
    return counters


def decode_status_data(data):
    """
    voltage, current in Amps and Power in Watts
        data is expected in RAW bytes array converted to int
    with no command and no checksum
    """
    if len(data) !=7 :
        print(f"Wrong bytes number in response: '{data}'")
        return [[]]*3
    voltage = bytes_to_int(data[:2])/10
    current = bytes_to_int(data[2:4])/100
    power = bytes_to_int(data[4:])
    
    return voltage, current, power


def bytes_to_int(bytes_data):
    return int(''.join([hex(x)[2:] if len(hex(x)[2:])==2 else '0'+hex(x)[2:] for x in bytes_data]))


def split_pairs(inp):
    pairs = [inp[2*i:2*i+2] for i in range(len(inp) // 2)]
    if len(inp) % 2 == 1:
        pairs.append(f'{inp[-1]}_')
    return pairs
    

def device_id_to_bytes(device_id:str):
    """
    converts RAW device ID Example: '04025230' to list of 3 bytes
    converted to int example: [0, 98, 142]
    """
    # convert device_id -> hex
    device_hex = hex(int(str(device_id)[-6:]))
    #print(device_hex)
    while len(device_hex) < 8:
        device_hex = '0x0' + device_hex[2:]
    #print(device_hex)
    device_bytes = split_pairs(device_hex)[1:]
    device_bytes_int = [int.from_bytes(bytes.fromhex(b),byteorder='little') for b in device_bytes]
    return tuple(device_bytes_int)


def mercury_request(device_id, request_id):
    """
    Create a byte string for sending to RS485
    device id: '04023330' (string)
    request_id: '27' string
    """
    # convert device_id -> hex
    device_hex = hex(int(device_id[-6:]))
    #print(device_hex)
    while len(device_hex) < 8:
        device_hex = '0x0' + device_hex[2:]
    #print(device_hex)
    device_bytes = split_pairs(device_hex)[1:]
    request_string = ["00"] + device_bytes + [request_id]

    #calculate checksum
    bytes_request = bytearray()
    for b in request_string:
        bytes_request.extend(bytes.fromhex(b))

    checksum = bytearray(bytes.fromhex(hex(crc16(bytes_request))[2:]))
    for b in checksum[::-1]: #Probably we do not need to invert
        request_string.append(hex(b)[2:])
    print(request_string)
    
    # convert to int
    request_string_in_int_bytes = [int.from_bytes(bytes.fromhex(b),byteorder='little') for b in request_string]

    # add number of bytes to the beginning
    request_string_in_int_bytes = [len(request_string_in_int_bytes)] + request_string_in_int_bytes
    
    return request_string_in_int_bytes