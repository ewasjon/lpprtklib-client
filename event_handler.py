import sys
import os
import signal

def write_stdout(s):
    sys.stdout.write(s)
    sys.stdout.flush()

def write_stderr(s):
    sys.stderr.write(s)
    sys.stderr.flush()

def kill_process(pid):
    try:
        os.kill(pid, signal.SIGTERM) 
        write_stderr(f"Process {pid} terminated successfully.\n")
    except ProcessLookupError:
        write_stderr(f"No process found with PID {pid}.\n")
    except PermissionError:
        write_stderr(f"Permission denied to terminate process {pid}.\n")
    except Exception as e:
        write_stderr(f"An error occurred: {e}\n")

def main():
    supervisord_pid = int(sys.argv[1])
    trigger_process = os.environ.get('TRIGGER_PROCESS')
    while 1:
        write_stdout('READY\n')
        line = sys.stdin.readline()
        headers = dict([x.split(':', 1) for x in line.split()])
        data = sys.stdin.read(int(headers['len']))
        data = dict([x.split(':', 1) for x in data.split()])
        write_stderr(f"Received headers: {headers}")
        write_stderr(f"Received data: {data}")

        if data['processname'] == trigger_process:
            write_stderr('Main process failed. Killing supervisord.')
            kill_process(supervisord_pid)

        write_stdout('RESULT 2\nOK')

if __name__ == '__main__':
    main()
    exit(0)