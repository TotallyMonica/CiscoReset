import json
import sys
import serial
import serial.tools.list_ports

def format_command(cmd: str = '') -> bytes:
    return f"{cmd}\n".encode('utf-8')

def wait_until_prompt(dev: serial.Serial, prompt: str, debug: bool = False) -> bytes:
    output = dev.readline()
    if debug:
        while not output.decode().lower().strip().startswith(prompt.lower().strip()):
            print(f"DEBUG: {output}")
            output = dev.readline()
    else:
        while not output.decode().lower().strip().startswith(prompt.lower().strip()):
            output = dev.readline()

    return output

def dedup(original_list):
    deduped_list = []
    for val in original_list:
        if val not in deduped_list:
            deduped_list.append(val)
    return deduped_list

def parse_files_to_delete(output: list[str], debug: bool = False):
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
    ser.write(format_command("flash_init"))
    print("Initializing flash...")
    ser.timeout = 10
    output = b''
    while b'switch:' not in output:
        print(output)
        output = ser.readline()
    ser.write(format_command("dir flash:"))
    print("Getting directory listing...")
    listing = ser.readlines()
    for line in listing:
        decoded_line = line.decode()
        for file in files_without_extensions:
            if file in decoded_line:
                parsed_line = decoded_line.split(' ')[-1]
                ser.write(format_command(f"del flash:{parsed_line}"))
                output = ser.readline()
                print(output)
                while b'\rAre you sure you want to delete "flash:' not in output:
                    output = ser.readline()
                    print(output)
                ser.write(format_command('y'))
        print(line)

    ser.timeout = original_timeout

def setup_serial():
    is_valid = False
    while not is_valid:
        ports = [port for port in serial.tools.list_ports.comports()]

        print("Select your serial device:")
        for port in ports:
            print(f"{port.device}:\n\tManufacturer: {port.manufacturer}\n\tDescription: {port.description}\n\tHardware ID: {port.hwid}")
        dev = input()
        try:
            with serial.Serial(dev) as tmp:
                is_valid = True
        except PermissionError:
            print("Unknown device or device already open. Please try a different device.")

    return dev

def switch_defaults(serial_info: str, debug: bool = False):
    PASSWORD_RECOVERY_ENABLED = b"The system has been interrupted"
    PASSWORD_RECOVERY_DISABLED = b"The password-recovery mechanism"
    CONFIRMATION_PROMPT = b'(y/n)?'
    RECOVERY_PROMPT = b'switch:'

    STEPS = ["Unplug the switch.",
             "Hold the MODE button on the switch.",
             "Plug the switch in while holding the button",
             "When you are told, release the MODE button"]

    ser = serial.Serial(serial_info)
    ser.timeout = 15

    print("Trigger password recovery by following these steps: ")
    for i in range(len(STEPS)):
        print(f"{i+1}. {STEPS[i]}")


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
    ser.write(format_command('flash_init\n'))
    output = ser.readline()
    while RECOVERY_PROMPT not in output:
        if debug:
            print(f"DEBUG: {output}")
        output = ser.readline()
    if debug:
        print(f"DEBUG: {output}")
    print("Flash has been initialized, now listing directory")
    ser.write(format_command('dir flash:\n'))
    output = ser.readline()
    if debug:
        print(f"DEBUG: {output}")
    listing = ser.readlines()
    if debug:
        for line in listing:
            print(f"DEBUG: {line}")
    files_to_delete = parse_files_to_delete(listing, debug)
    if len(files_to_delete) == 0:
        print("Switch has been erased already.")
        ser.write(format_command())
        ser.timeout = 1
    else:
        print("Deleting files")
        for file in files_to_delete:
            print(f"Deleting {file}")
            ser.write(format_command(f'del flash:{file}'))
            output = ser.readline()
            while CONFIRMATION_PROMPT not in output:
                if debug:
                    print(f"DEBUG: {output}")
                output = ser.readline()
            if debug:
                print(f"DEBUG: {output}")
                print(f"Confirming deletion")
            ser.write(format_command('y'))
            output = ser.readline()
            if debug:
                print(f"DEBUG: {output}")
            output = ser.readline()
            if debug:
                print(f"DEBUG: {output}")
        print("Switch has been reset.")

    print("Resetting the switch")
    while RECOVERY_PROMPT not in output:
        output = ser.readline()
        if debug:
            print(f"DEBUG: {output}")

    ser.write(format_command('reset'))
    while CONFIRMATION_PROMPT not in output:
        output = ser.readline()
        if debug:
            print(f"DEBUG: {output}")
    ser.write(format_command('y'))
    print("Successfully reset! Will continue trailing the output, but ^C at any point to exit.")
    try:
        while True:
            if debug:
                print(f"DEBUG: {ser.readline()}")
    except KeyboardInterrupt:
        print("Keyboard interrupt found, cleaning up")
        ser.close()
        exit()

def router_defaults(serial_info, debug: bool = False):
    SHELL_PROMPT = "router"
    ROMMON_PROMPT = "rommon"
    CONFIRMATION_PROMPT = "[confirm]"
    RECOVERY_REGISTER = "0x2142"
    NORMAL_REGISTER = "0x2102"
    SAVE_PROMPT = "[yes/no]: "

    # In the startup sequence, we don't need to wait for an extremely long time
    ser = serial.Serial(serial_info)
    ser.timeout = 1

    print("Trigger password recovery by following these steps: ")
    print("1. Turn off the router")
    print("2. After waiting for the lights to shut off, turn the router back on")
    print("3. Press enter here once this has been completed")
    input()


    if debug:
        print('='*30)
    print("Sending ^C until we enter ROMMON")
    if debug:
        print('='*30)
    output = b''
    output = ser.readline()
    if debug:
        while not output.decode().lower().strip().startswith(ROMMON_PROMPT.lower().strip()):
            print(f"DEBUG: {output}")
            ser.write(b"\x03")
            output = ser.readline()
    else:
        while not output.decode().lower().strip().startswith(ROMMON_PROMPT.lower().strip()):
            ser.write(b"\x03")
            output = ser.readline()
    if debug:
        print(f"DEBUG: {output}")

    if debug:
        print('='*30)
    print("We've entered ROMMON, setting the register to 0x2142.")
    if debug:
        print('='*30)
    commands = [f'confreg {RECOVERY_REGISTER}', 'reset']
    iter = 1
    for cmd in commands:
        ser.write(format_command(cmd))
        output = ser.readline()
        if debug:
            print(f"DEBUG: {output}")
        output = ser.readline()
        if debug:
            print(f"DEBUG: {output}")
        iter += 1
        # Sometimes it will print out some flavor text, we just wanna ignore that until we get to the prompt again
        if not cmd == commands[-1]:
            wait_until_prompt(ser, f"{ROMMON_PROMPT} {iter}", debug)
    while output.decode().lower().startswith(ROMMON_PROMPT):
        ser.write(format_command())
        if debug:
            print(f"DEBUG: {output}")

    # Increase the timeout period as it can take a while for it to start up
    ser.timeout = 15

    # Wait until we're at our prompt
    if debug:
        print('='*30)
    print("We've finished with ROMMON, now booting up the router.")
    if debug:
        print('='*30)
    output = ser.readline()
    while not output.decode().lower().startswith(SHELL_PROMPT):
        if debug:
            print(f"DEBUG: {output}")
        output = ser.readline()
        if output == b'':
            ser.write(b'\r\n')

    # We can safely assume we're at the prompt, so now let's begin running our commands
    if debug:
        print('='*30)
    print("Setting the registers back to regular")
    if debug:
        print('='*30)
    ser.timeout = 1
    commands = ['enable', 'conf t', f'config-register {NORMAL_REGISTER}', 'end']
    for cmd in commands:
        ser.write(format_command(cmd))
        output = ser.readline()
        if debug:
            print(f"DEBUG: {output}")
        output = ser.readline()
        if debug:
            print(f"DEBUG: {output}")
        # Sometimes it will print out some flavor text, we just wanna ignore that until we get to the prompt again
        while not output.decode().lower().startswith(SHELL_PROMPT):
            output = ser.readline()
            if debug:
                print(f"DEBUG: {output}")

    # Now save the reset configuration
    if debug:
        print('='*30)
    print("Resetting the configuration")
    if debug:
        print('='*30)
    ser.write(format_command('erase nvram:'))
    output = ser.readline()
    if debug:
        print(f"DEBUG: {output}")
    output = ser.readline()
    if debug:
        print(f"DEBUG: {output}")
    ser.write(format_command())
    output = ser.readline()
    if debug:
        print(f"DEBUG: {output}")
    output = ser.readline()
    if debug:
        print(f"DEBUG: {output}")

    if debug:
        print('='*30)
    print("Reloading the router")
    if debug:
        print('=' * 30)

    read_count = 0

    ser.write(format_command("reload"))
    while SAVE_PROMPT not in output.decode().lower():
        output = ser.readline()
        read_count += 1
        if debug:
            print(output)
    ser.write(format_command("yes"))
    while CONFIRMATION_PROMPT not in output.decode().lower():
        output = ser.readline()
        read_count += 1
        if debug:
            print(output)
    ser.write(format_command())
    print("Successfully reset! Will continue trailing the output, but ^C at any point to exit.")
    try:
        while True:
            if debug:
                print(f"DEBUG: {ser.readline()}")
    except KeyboardInterrupt:
        print("Keyboard interrupt found, cleaning up")
        ser.close()
        exit()

def log_inputs(serial_info):
    inputs = []

    print("Trigger password recovery by following these steps: ")
    print("1. Turn off the router")
    print("2. After waiting for the lights to shut off, turn the router back on")
    print("3. Press enter here once this has been completed")
    input()

    ser = serial.Serial(serial_info)
    ser.timeout = 10

    output = b''
    while not output.decode().lower().startswith("rommon"):
        ser.write(b"\x03")
        output = ser.readline()
        print(output)

    consecutive_blank_line_count = 0
    blank_line_threshold = 10
    while True:
        line = ser.readline()
        inputs.append({'out': line})
        print(f"{line}")
        if line == b'':
            consecutive_blank_line_count += 1
            ser.write(b'\r\n')      # Seems to be when we're in the regular boot mode, we need to write b'\r\n at the end of the line'
            print(f"{consecutive_blank_line_count=}")
        else:
            consecutive_blank_line_count = 0
        if line.startswith(b'Image validated'):
            blank_line_threshold = 15
        if ('rommon' in line.decode().lower() or 'router' in line.decode().lower()
                or consecutive_blank_line_count >= blank_line_threshold
                or 'System configuration has been modified. Save? [yes/no]: '.lower() in line.decode().lower()):
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

def main(args: list = sys.argv):
    settings = setup_serial()
    # print(router_defaults(settings, debug=True))
    print(switch_defaults(settings, debug=True))

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main(sys.argv)
    # print(json.dumps(log_inputs(settings)))

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
