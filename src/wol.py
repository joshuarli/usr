#!/usr/bin/env python3
import argparse
import socket
import sys


IPV4_ADDR_LEN = 15


def create_magic_packet(mac_bytes):
    packet = bytearray()
    packet += bytearray([0xFF] * 6)
    for _ in range(16):
        packet += bytearray(mac_bytes)
    return bytes(packet)


def parse_mac(mac_str):
    mac_str = mac_str.strip()
    # Try colon format
    if ':' in mac_str:
        parts = mac_str.split(':')
    elif '-' in mac_str:
        parts = mac_str.split('-')
    else:
        # Try without separators
        mac_str_clean = mac_str.replace('.', '')
        if len(mac_str_clean) == 12:
            parts = [mac_str_clean[i:i+2] for i in range(0, 12, 2)]
        else:
            raise ValueError(f'Invalid MAC address: {mac_str}')
    
    if len(parts) != 6:
        raise ValueError(f'Invalid MAC address: {mac_str}')
    
    mac_bytes = []
    for p in parts:
        mac_bytes.append(int(p, 16))
    return bytes(mac_bytes)


def get_mac_addresses_from_file(filename):
    macs = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or len(line) < 17:
                    continue
                try:
                    mac_bytes = parse_mac(line)
                    macs.append(mac_bytes)
                except ValueError:
                    print(f'Invalid MAC address format in file: {filename}', file=sys.stderr)
                    continue
    except IOError:
        print(f'Could not open file {filename}', file=sys.stderr)
        return None
    
    if not macs:
        print('No valid MAC addresses found in file', file=sys.stderr)
        return None
    return macs


def send_magic_packet(packet, broadcast_address='255.255.255.255', interface=None):
    if not packet:
        print('Invalid packet.', file=sys.stderr)
        return False
    
    if broadcast_address and len(broadcast_address) > IPV4_ADDR_LEN:
        print('Invalid broadcast address.', file=sys.stderr)
        return False
    if not broadcast_address:
        broadcast_address = '255.255.255.255'
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.bind(('', 0))
        
        if interface:
            if sys.platform == 'darwin':
                # Try IP_BOUND_IF on macOS
                try:
                    import struct
                    # IP_BOUND_IF = 25 on macOS
                    if_index = socket.if_nametoindex(interface)
                    s.setsockopt(socket.IPPROTO_IP, 25, struct.pack('I', if_index))
                except Exception as e:
                    print(f"Failed to bind interface: '{e}'.", file=sys.stderr)
                    s.close()
                    return False
            elif sys.platform.startswith('linux'):
                try:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, interface.encode() + b'\x00')
                except Exception as e:
                    print(f"Failed to bind interface: '{e}'.", file=sys.stderr)
                    s.close()
                    return False
            else:
                # Try generic approach
                try:
                    s.setsockopt(socket.SOL_SOCKET, 25, interface.encode() + b'\x00')  # SO_BINDTODEVICE value
                except Exception as e:
                    print(f"Failed to bind interface: '{e}'.", file=sys.stderr)
                    s.close()
                    return False
        
        s.sendto(packet, (broadcast_address, 9))
        s.close()
        return True
    except Exception as e:
        print(f"Failed to send magic packet: '{e}'.", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-f', dest='file_name', help='File containing MAC addresses')
    parser.add_argument('args', nargs='*', help='MAC address, broadcast address, interface')
    
    args = parser.parse_args()
    
    if len(sys.argv) < 2:
        print(f'Usage:\n{sys.argv[0]} [<mac address> | -f macs-list.txt] [<broadcast address>] [<interface>]', file=sys.stderr)
        if sys.platform != 'win32':
            pass  # interface mentioned in usage
        sys.exit(1)
    
    mac_addresses = []
    
    if args.file_name:
        print(f'Parsing file name: {args.file_name} . Invalid MAC addresses will be discarded.')
        macs = get_mac_addresses_from_file(args.file_name)
        if not macs:
            sys.exit(1)
        mac_addresses = macs
    else:
        if not args.args:
            print(f'Usage:\n{sys.argv[0]} [<mac address> | -f macs-list.txt] [<broadcast address>] [<interface>]', file=sys.stderr)
            sys.exit(1)
        try:
            mac_bytes = parse_mac(args.args[0])
            mac_addresses = [mac_bytes]
        except ValueError:
            print('Invalid mac address. Please specify a valid mac address in the format xx:xx:xx:xx:xx:xx', file=sys.stderr)
            sys.exit(1)
    
    broadcast_address = None
    interface = None
    
    # Determine positions based on whether file was used
    if args.file_name:
        # args.args contain broadcast and/or interface
        idx = 0
        if idx < len(args.args):
            # Check if it's broadcast
            try:
                # Try to parse as IP
                socket.inet_aton(args.args[idx])
                if len(args.args[idx]) <= IPV4_ADDR_LEN:
                    broadcast_address = args.args[idx]
                    idx += 1
            except OSError:
                pass
        if idx < len(args.args) and sys.platform != 'win32':
            interface = args.args[idx]
    else:
        # args.args[0] is MAC, args.args[1] might be broadcast, args.args[2] might be interface
        if len(args.args) > 1:
            try:
                socket.inet_aton(args.args[1])
                if len(args.args[1]) <= IPV4_ADDR_LEN:
                    broadcast_address = args.args[1]
            except OSError:
                pass
        if len(args.args) > 2 and sys.platform != 'win32':
            interface = args.args[2]
    
    # Create and send magic packets
    for mac_bytes in mac_addresses:
        packet = create_magic_packet(mac_bytes)
        if not send_magic_packet(packet, broadcast_address, interface):
            print('Failed to send magic packet.', file=sys.stderr)
            sys.exit(1)
        else:
            mac_hex = ':'.join(f'{b:02x}' for b in mac_bytes)
            print(f'Magic packet sent to {mac_hex}...')
    
    sys.exit(0)


if __name__ == '__main__':
    main()
