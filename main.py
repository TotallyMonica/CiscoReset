import json
import sys
import serial
import serial.tools.list_ports

def dedup(original_list):
    deduped_list = []
    for val in original_list:
        if val not in deduped_list:
            deduped_list.append(val)
    return deduped_list

def parse_files_to_delete(output: list[str], debug: bool = True):
    common_prefixes = ["private-config", "config", "vlan"]
    files_to_delete = []
    for line in output:
        clean_line = line.decode().strip().split(' ')
        for prefix in common_prefixes:
            if prefix in clean_line[-1]:
                files_to_delete.append(clean_line[-1])
    if debug:
        print(f"DEBUG: {files_to_delete=}")
    files_to_delete = dedup(files_to_delete)
    if debug:
        print(f"DEBUG: {files_to_delete=}")
    return files_to_delete

def switch_reset_password_enabled(ser: serial.Serial):
    files_without_extensions = ["private-config", "config", "vlan"]
    original_timeout = ser.timeout
    ser.write(b"flash_init\n")
    print("Initializing flash...")
    ser.timeout = 10
    output = b''
    while b'switch:' not in output:
        print(output)
        output = ser.readline()
    ser.write(b"dir flash:\n")
    print("Getting directory listing...")
    listing = ser.readlines()
    for line in listing:
        decoded_line = line.decode()
        for file in files_without_extensions:
            if file in decoded_line:
                parsed_line = decoded_line.split(' ')[-1]
                ser.write(f"del flash:{parsed_line}\n".encode())
                output = ser.readline()
                print(output)
                while b'\rAre you sure you want to delete "flash:' not in output:
                    output = ser.readline()
                    print(output)
                ser.write(b'y\n')
        print(line)

    ser.timeout = original_timeout

def setup_serial():
    ports = [port for port in serial.tools.list_ports.comports()]

    print("Select your serial device:")
    for port in ports:
        print(f"{port.device}:\n\tManufacturer: {port.manufacturer}\n\tDescription: {port.description}\n\tHardware ID: {port.hwid}")
    dev = input()

    return dev

def switch_defaults(serial_info: str, debug: bool = True):
    PASSWORD_RECOVERY_ENABLED = b"The system has been interrupted"
    PASSWORD_RECOVERY_DISABLED = b"The password-recovery mechanism"
    CONFIRMATION_PROMPT = b'(y/n)?'
    RECOVERY_PROMPT = b'switch:'

    STEPS = ["Unplug the switch.",
             "Hold the MODE button on the switch.",
             "Plug the switch in while holding the button",
             "When you are told, release the MODE button"]

    print("Trigger password recovery by following these steps: ")
    for i in range(len(STEPS)):
        print(f"{i+1}. {STEPS[i]}")

    ser = serial.Serial(serial_info)
    ser.timeout = 15

    output = ser.readline()
    while b'\rXmodem file system is available.\n' not in output:
        if debug:
            print(f"DEBUG: {output}")
        output = ser.readline()
    if debug:
        print(f"DEBUG: {output}")
    print("Release the mode button now")

    output = ser.readline()
    while RECOVERY_PROMPT not in output:
        if debug:
            print(f"DEBUG: {output}")
        output = ser.readline()
    if debug:
        print(f"DEBUG: {output}")
    print("Entered recovery console, initializing flash.")
    ser.write('flash_init\n'.encode('utf-8'))
    output = ser.readline()
    while RECOVERY_PROMPT not in output:
        if debug:
            print(f"DEBUG: {output}")
        output = ser.readline()
    if debug:
        print(f"DEBUG: {output}")
    print("Flash has been initialized, now listing directory")
    ser.write('dir flash:\n'.encode('utf-8'))
    output = ser.readline()
    if debug:
        print(f"DEBUG: {output}")
    listing = ser.readlines()
    if debug:
        for line in listing:
            print(f"DEBUG: {line}")
    files_to_delete = parse_files_to_delete(listing, debug)
    print("Deleting files")
    for file in files_to_delete:
        print(f"Deleting {file}")
        ser.write(f'del flash:{file}\n'.encode('utf-8'))
        output = ser.readline()
        while CONFIRMATION_PROMPT not in output:
            if debug:
                print(f"DEBUG: {output}")
            output = ser.readline()
        if debug:
            print(f"DEBUG: {output}")
            print(f"Confirming deletion")
        ser.write(b'y\n')
        output = ser.readline()
        if debug:
            print(f"DEBUG: {output}")
        output = ser.readline()
        if debug:
            print(f"DEBUG: {output}")

    print("Files deleted, resetting the switch")
    while RECOVERY_PROMPT not in output:
        output = ser.readline()
        if debug:
            print(f"DEBUG: {output}")

    ser.write(b'reset\n')
    while CONFIRMATION_PROMPT not in output:
        output = ser.readline()
        if debug:
            print(f"DEBUG: {output}")
    ser.write(b'y\n')
    print("Successfully reset! Will continue trailing the output, but ^C at any point to exit.")
    try:
        while True:
            if debug:
                print(f"DEBUG: {ser.readline()}")
    except KeyboardInterrupt:
        print("Keyboard interrupt found, cleaning up")
        ser.close()
        exit()

def router_defaults(serial_info):
    print("Trigger password recovery by following these steps: ")
    print("1. Turn off the router")
    print("2. After waiting for the lights to shut off, turn the router back on")
    print("3. Press enter here once this has been completed")
    input()

    ser = serial.Serial(serial_info)
    ser.timeout = 1

    print("Sending ^C until we enter ROMMON")
    output = b''
    while not output.decode().lower().startswith("rommon"):
        for i in range(10):
            ser.write(b"\x03")
        output = ser.readline()
        print(output)

    print("We've entered ROMMON, setting the register to 0x2142.")
    ser.write(b"confreg 0x2142\n")
    output = ser.readline()
    print(output)
    output = ser.readline()
    print(output)
    ser.write(b"reset")

    output = b''
    while not output.decode().lower().startswith("would"):
        output = ser.readline()

def log_inputs(serial_info):
    inputs = []
    # ser = serial.Serial(serial_info)
    # ser.timeout = 15

    print("Trigger password recovery by following these steps: ")
    print("1. Turn off the router")
    print("2. After waiting for the lights to shut off, turn the router back on")
    print("3. Press enter here once this has been completed")
    input()

    ser = serial.Serial(serial_info)
    ser.timeout = 10

    # output = b''
    # while not output.decode().lower().startswith("rommon"):
    #     for i in range(1):
    #         ser.write(b"\x03")
    #     output = ser.readline()
    #     print(output)

    consecutive_blank_line_count = 0
    blank_line_threshold = 10
    while True:
        line = ser.readline()
        inputs.append({'out': line})
        print(f"{line}")
        if line == b'':
            consecutive_blank_line_count += 1
            ser.write(b'\n')
            print(f"{consecutive_blank_line_count=}")
        else:
            consecutive_blank_line_count = 0
        # if line.startswith(b'Image validated'):
        #     blank_line_threshold = 15
        if 'rommon' in line.decode().lower() or 'router' in line.decode().lower() or consecutive_blank_line_count >= blank_line_threshold:
            user_input = input('> ') + '\n'
            consecutive_blank_line_count = 0
            print(user_input)
            if user_input == '```END```\n':
                return inputs
            elif user_input == 'reset\n':
                ser.timeout = 15
            inputs.append({'in': user_input})
            ser.write(user_input.encode())
            read_line = ser.readline()
            print(f"{read_line}", end='')

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    settings = setup_serial()
    # print(router_defaults(settings))
    # print(switch_defaults(settings))
    print(json.dumps(log_inputs(settings)))

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
