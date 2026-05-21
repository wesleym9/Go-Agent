import subprocess
import json
import threading
import queue
import time

class KataGoAnalysis:
    def __init__(self, katago_path, model_path, config_path):
        self.katago_path = katago_path
        self.model_path = model_path
        self.config_path = config_path
        self.process = None
        self.output_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.reader_thread = None

    def start(self):
        cmd = [
            self.katago_path, "analysis",
            "-model", self.model_path,
            "-config", self.config_path
        ]
        # Log stderr to a file for debugging
        self.stderr_log = open("katago_stderr.log", "w")
        
        self.stop_event.clear()
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.stderr_log,
            text=True,
            bufsize=1
        )
        self.reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self.reader_thread.start()
        print("KataGo Analysis Engine started.")

    def check_and_restart(self):
        # Check if the subprocess has stopped or was never started
        if self.process is None or self.process.poll() is not None:
            print("KataGo subprocess is dead. Attempting restart...")
            try:
                self.stop()
            except Exception as e:
                print(f"Error while stopping dead engine: {e}")
            
            # Flush queue to avoid stale items
            while not self.output_queue.empty():
                try:
                    self.output_queue.get_nowait()
                except queue.Empty:
                    break
            
            self.start()

    def _read_output(self):
        while not self.stop_event.is_set():
            if self.process is None or self.process.stdout is None:
                break
            line = self.process.stdout.readline()
            if not line:
                break
            try:
                data = json.loads(line)
                self.output_queue.put(data)
            except json.JSONDecodeError:
                # Filter out standard startup/info outputs that are not JSON
                clean_line = line.strip()
                if clean_line:
                    print(f"KataGo info/error output: {clean_line}")
        
    def send_query(self, query_id, moves, board_size=19, komi=7.5, max_visits=1000):
        self.check_and_restart()
        query = {
            "id": query_id,
            "moves": moves,
            "rules": "tromp-taylor",
            "komi": komi,
            "boardXSize": board_size,
            "boardYSize": board_size,
            "includePolicy": True,
            "includePv": True,
            "maxVisits": max_visits
        }
        try:
            self.process.stdin.write(json.dumps(query) + "\n")
            self.process.stdin.flush()
        except Exception as e:
            print(f"Error writing to KataGo stdin: {e}. Retrying after engine restart...")
            self.check_and_restart()
            try:
                self.process.stdin.write(json.dumps(query) + "\n")
                self.process.stdin.flush()
            except Exception as retry_e:
                print(f"CRITICAL: Failed to communicate with KataGo even after restart: {retry_e}")
                raise retry_e

    def get_latest_analysis(self, timeout=None):
        if timeout is None or timeout == 0:
            try:
                return self.output_queue.get_nowait()
            except queue.Empty:
                return None
        else:
            try:
                return self.output_queue.get(timeout=timeout)
            except queue.Empty:
                return None

    def stop(self):
        self.stop_event.set()
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except Exception as e:
                print(f"Exception stopping subprocess: {e}")
            self.process = None
        if self.reader_thread:
            try:
                self.reader_thread.join(timeout=1)
            except Exception as e:
                print(f"Exception joining thread: {e}")
            self.reader_thread = None

    def switch_model(self, model_path, config_path):
        if self.model_path != model_path or self.config_path != config_path:
            print(f"Swapping engine model to {model_path} with config {config_path}")
            self.model_path = model_path
            self.config_path = config_path
            # Setting process to None will force check_and_restart to spawn a new process
            if self.process:
                try:
                    self.stop()
                except Exception as e:
                    print(f"Error stopping old engine: {e}")
            
            # Flush queue to avoid stale items
            while not self.output_queue.empty():
                try:
                    self.output_queue.get_nowait()
                except queue.Empty:
                    break
            
            self.start()


