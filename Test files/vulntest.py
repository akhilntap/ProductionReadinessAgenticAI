import subprocess
import os

def process_user_input(user_input):
    # Vulnerability 1: Command Injection
    # Unsafe use of subprocess.run with shell=True and unsanitized input
    subprocess.run(f'ls {user_input}', shell=True, check=True)

    # Vulnerability 2: Path Traversal
    # Directly using user-provided path without validation
    with open(user_input, 'r') as f:
        print(f.read())

    # Vulnerability 3: Insecure use of eval()
    # Allows execution of arbitrary code
    result = eval(user_input)
    print(result)

user_input = input("Enter command/path/expression: ")
process_user_input(user_input)

# Vulnerability 4: Insecure temporary file creation
temp_file = os.tmpnam()
with open(temp_file, "w") as f:
    f.write("Sensitive information")
# The file is created with insecure permissions and is predictable