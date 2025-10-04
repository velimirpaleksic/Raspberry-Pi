# print_pycups.py
import cups
import time

def list_printers():
    conn = cups.Connection()
    return conn.getPrinters()  # dict: name -> detail

def print_file_with_pycups(file_path: str, printer: str = None, title: str = "Raspberry Pi Print"):
    conn = cups.Connection()
    printers = conn.getPrinters()
    if not printer:
        # pokušaj default, pa uzmi prvi
        try:
            printer = conn.getDefault()
        except Exception:
            printer = next(iter(printers), None)
    if not printer:
        raise RuntimeError("No printers available")

    job_id = conn.printFile(printer, file_path, title, {})  # returning job id
    return job_id

def wait_for_job(conn, job_id, timeout=30):
    # jednostavno čekanje dok job ne nestane iz queue-a
    start = time.time()
    while time.time() - start < timeout:
        jobs = conn.getJobs()  # aktivni jobovi
        if job_id not in jobs:
            return True
        time.sleep(0.5)
    return False

# Usage
# conn = cups.Connection()
# jid = print_file_with_pycups("/home/pi/docs/output.pdf", printer="HP_MyPrinter")
# ok = wait_for_job(conn, jid)