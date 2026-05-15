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
        if not isinstance(action_proposal, dict):
            return False, "Decision is not a JSON object."

        action = str(action_proposal.get("action", "")).upper()
        if action not in {"HOLD", "SWAP", "DEPOSIT_KAMINO"}:
            return False, f"Unknown action: {action or 'missing'}."

        if action == "SWAP":
            params = action_proposal.get("params")
            if not isinstance(params, dict):
                return False, "SWAP params missing."
            if params.get("from") not in config.ALLOWED_TRADE_MINTS:
                return False, "Source mint is not in the allowed universe."
            if params.get("to") not in config.ALLOWED_TRADE_MINTS:
                return False, "Target mint is not in the allowed universe."
            try:
                amount_sol = float(params.get("amount_sol", 0))
            except (TypeError, ValueError):
                return False, "Invalid amount_sol."
            if amount_sol <= 0:
                return False, "Trade amount must be positive."

        return True, "Audit passed."


paperclip = PaperclipFleet()
