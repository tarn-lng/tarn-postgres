"""Hostile wire peers: no SCRAM proof bypass, allocation underflow, or reuse."""
import base64
import socket
import struct
import subprocess
import sys
import threading


def exact(conn, n):
    out = b''
    while len(out) < n:
        chunk = conn.recv(n - len(out))
        if not chunk:
            raise EOFError(out)
        out += chunk
    return out


def packet(tag, data):
    return tag + struct.pack('!I', len(data) + 4) + data


def message(conn):
    tag = exact(conn, 1)
    size, = struct.unpack('!I', exact(conn, 4))
    return tag, exact(conn, size - 4)


def fixture(kind):
    listener = socket.create_server(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    errors = []

    def peer():
        try:
            with listener.accept()[0] as conn:
                conn.settimeout(5)
                length, = struct.unpack('!I', exact(conn, 4))
                exact(conn, length - 4)
                if kind == 'small-length':
                    conn.sendall(b'R\x00\x00\x00\x03')
                elif kind == 'large-length':
                    conn.sendall(b'R\x7f\xff\xff\xff')
                elif kind == 'ready-before-auth':
                    conn.sendall(packet(b'Z', b'I'))
                elif kind in ('bad-proof', 'missing-proof'):
                    conn.sendall(packet(b'R', struct.pack('!I', 10) + b'SCRAM-SHA-256\x00\x00'))
                    tag, initial = message(conn)
                    assert tag == b'p'
                    mechanism, rest = initial.split(b'\x00', 1)
                    size, = struct.unpack('!I', rest[:4])
                    first = rest[4:]
                    assert size == len(first) and first.startswith(b'n,,n=,r=')
                    nonce = first.split(b'r=', 1)[1]
                    challenge = b'r=' + nonce + b'extension,s=' + base64.b64encode(b'0123456789abcdef') + b',i=4096'
                    conn.sendall(packet(b'R', struct.pack('!I', 11) + challenge))
                    assert message(conn)[0] == b'p'
                    if kind == 'bad-proof':
                        conn.sendall(packet(b'R', struct.pack('!I', 12) + b'v=' + base64.b64encode(bytes(32))))
                    conn.sendall(packet(b'R', struct.pack('!I', 0)) + packet(b'Z', b'I'))
                else:
                    conn.sendall(packet(b'R', struct.pack('!I', 0)) + packet(b'Z', b'I'))
                    assert message(conn)[0] == b'Q'
                    if kind == 'row-description':
                        conn.sendall(packet(b'T', b'\x00\x01name\x00'))
                    else:
                        conn.sendall(packet(b'D', b'\x00\x01\x00\x00\x00\x10x'))
        except (BrokenPipeError, ConnectionResetError):
            pass
        except BaseException as exc:
            errors.append(repr(exc))
        finally:
            listener.close()

    thread = threading.Thread(target=peer)
    thread.start()
    mode = 'query' if kind in ('row-description', 'data-row') else 'connect'
    result = subprocess.run([sys.argv[1], f'postgresql://test:secret@127.0.0.1:{port}/test?sslmode=disable', mode],
                            capture_output=True, timeout=10)
    thread.join(5)
    assert not thread.is_alive() and not errors, (kind, errors)
    assert result.returncode == 0 and result.stdout == b'rejected\n', (kind, result.returncode, result.stdout, result.stderr)


for case in ('small-length', 'large-length', 'ready-before-auth', 'bad-proof', 'missing-proof', 'row-description', 'data-row'):
    fixture(case)
print('Hostile authentication, framing, rows and connection poisoning: 7 cases passed')
