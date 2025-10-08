# print_hplip.py
import subprocess

def print_file_hplip(file_path: str, printer: str = None) -> bool:
    """
    Send PDF to HP printer using HPLIP.
    Returns True if printing command executed successfully, False otherwise.
    """
    cmd = ["hp-print"]
    if printer:
        cmd += ["-d", printer]
    cmd.append(file_path)

    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Printing failed: {e}")
        return False
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False