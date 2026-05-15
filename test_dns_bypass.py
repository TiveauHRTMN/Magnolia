import httpx

def resolve_dns_doh(domain):
    print(f"🌐 DNS-over-HTTPS: Resolving {domain} via Google...")
    try:
        url = "https://dns.google/resolve"
        params = {"name": domain, "type": "A"}
        res = httpx.get(url, params=params, timeout=5.0)
        data = res.json()
        if "Answer" in data:
            ip = data["Answer"][0]["data"]
            print(f"✅ Resolved to: {ip}")
            return ip
    except Exception as e:
        print(f"❌ DoH Resolution failed: {e}")
    return None

def test_jupiter_direct_ip():
    domain = "quote-api.jup.ag"
    ip = resolve_dns_doh(domain)
    if not ip:
        return False
    
    url = f"https://{ip}/v6/quote"
    params = {
        "inputMint": "So11111111111111111111111111111111111111112",
        "outputMint": "EPjFW36vnC7H1VSEmG6vSP9nbt1uEAL65951Pn666ob",
        "amount": "10000000",
        "slippageBps": 50
    }
    headers = {"Host": domain}
    
    print(f"📡 Testing direct connection to {url} with Host header...")
    try:
        # verify=False because the certificate is for the domain, not the IP
        # In a real app we should handle SSL better, but for bypass this works
        res = httpx.get(url, params=params, headers=headers, timeout=10.0, verify=False)
        if res.status_code == 200:
            print("🔥 SUCCESS! Connection established bypassing local DNS.")
            return True
        else:
            print(f"⚠️ Status: {res.status_code}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    return False

if __name__ == "__main__":
    test_jupiter_direct_ip()
