import os
import signal
import subprocess
import sys

def kill_port(port):
    print(f"Searching for process on port {port}...")
    try:
        # Get the PID(s) using netstat
        output = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True).decode()
        pids = set()
        for line in output.strip().split('\n'):
            if "LISTENING" in line:
                pid = line.strip().split()[-1]
                pids.add(pid)
        
        if not pids:
            print(f"No process found on port {port}.")
            return

        for pid in pids:
            print(f"Found process with PID: {pid}. Attempting to kill...")
            try:
                # Use taskkill on Windows
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, check=True)
                print(f"✅ Successfully killed PID {pid}")
            except Exception as e:
                print(f"❌ Failed to kill PID {pid}: {e}")
                
    except subprocess.CalledProcessError:
        print(f"No process found on port {port} (or error running netstat).")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    kill_port(8000)
