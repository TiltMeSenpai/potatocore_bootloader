from serial import Serial
from itertools import islice, count

def byte_add(a, b):
    return (a + b) & 0xff

def complement(a):
    return (0x100 - (a & 0xff)) & 0xff

def command(out_bytes, command):
    command_bytes = bytes(command)
    in_bytes = len(command)
    return f".{in_bytes:02x}{out_bytes:02x}{command.hex()}{complement(in_bytes + out_bytes + sum(command_bytes)):02x}\r\n".encode("utf8")

def run_command(port, out_bytes, cmd_buf):
    port.write(command(out_bytes, cmd_buf))
    port.flush()
    return port.readline()

def chunk_iterable(iterable, size):
    it = iter(iterable)
    while True:
        chunk = bytes(islice(it, size))
        if not chunk:
            break
        yield chunk

def chunk_file(f, chunk_size):
    for chunk in iter(lambda: f.read(chunk_size), b""):
        yield chunk

def flash(port="/dev/ttyACM0", path="build/top.bit", base_addr=0x200_000):
    with Serial(port) as port:
        with open(path, "rb") as f:
            for b_addr, chunk in zip(count(base_addr, 0x1000), chunk_file(f, 0x1000)):
                run_command(port, 0, b"\x06")
                run_command(port, 0, b"\x20" + b_addr.to_bytes(3, "big"))
                for addr, page in zip(count(b_addr, 128), chunk_iterable(chunk, 128)):
                    a = addr.to_bytes(3, "big")
                    run_command(port, 0, b"\x06")
                    run_command(port, 0, b"\x02" + a + page)
                    readback = run_command(port, len(page), b"\x03" + a)
                    expected = f".{page.hex()}\n".upper().encode("utf8")
                    if not expected.startswith(readback.strip()):
                        print(f"Error: (0x{addr:x} - {addr + 127:x}):\r\n{readback}\r\n{expected}")