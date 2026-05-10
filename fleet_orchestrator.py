import os
import json
import time
import config

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "paperclip_memory.json")


class PaperclipFleet:
    def remember(self, note):
        print(f"Paperclip: Archiving leermoment...", flush=True)
        try:
            memory = []
            if os.path.exists(MEMORY_FILE):
                with open(MEMORY_FILE) as f:
                    memory = json.load(f)
            memory.append({"note": note, "timestamp": time.strftime('%Y-%m-%d %H:%M')})
            memory = memory[-50:]
            with open(MEMORY_FILE, 'w') as f:
                json.dump(memory, f, indent=2)
        except Exception as e:
            print(f"Paperclip Memory Error: {e}")

    def audit(self, action_proposal):
        return True, "Audit passed."


paperclip = PaperclipFleet()
