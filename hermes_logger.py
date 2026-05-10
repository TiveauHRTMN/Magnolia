import os
import httpx
from dotenv import load_dotenv

# Laad de Weerzone .env.local file die in de map erboven staat
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env.local'))

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")

def log_action(agent, action, details, status="success"):
    """Hermes waakt over de waarheid. Hij logt alles naar Weerzone Supabase."""
    print(f"📡 Hermes: Logging actie voor {agent}...")
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("⚠️ Hermes: Supabase credentials niet gevonden. Log lokaal overgeslagen.")
        return False
        
    url = f"{SUPABASE_URL}/rest/v1/agent_activity"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    payload = {
        "agent_name": agent,
        "action_type": action,
        "description": details,
        "metadata": {"status": status, "source": "magnolia_crypto_syndicate"}
    }
    
    try:
        res = httpx.post(url, headers=headers, json=payload)
        if res.status_code in [200, 201, 204]:
            print(f"✅ Hermes: Data veilig in Weerzone DB (agent_activity).")
            return True
        else:
            print(f"⚠️ Hermes waarschuwing: HTTP {res.status_code} - {res.text}")
            return False
    except Exception as e:
        print(f"❌ Hermes Fout: {e}")
        return False

if __name__ == "__main__":
    log_action("Hermes", "system_check", "Hermes is online en verbonden met agent_activity.")
