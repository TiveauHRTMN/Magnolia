import jupiter_swap

def final_test():
    print("🧪 FINALE TEST: DNS Bypass Strategie...")
    # Test alleen de quote aanvraag (stap 1 van swap)
    # SOL naar USDC, 0.01 SOL
    result = jupiter_swap.swap(
        "So11111111111111111111111111111111111111112",
        "EPjFW36vnC7H1VSEmG6vSP9nbt1uEAL65951Pn666ob",
        10000000
    )
    if result:
        print("✅ TEST GESLAAGD! De blokkade is doorbroken.")
    else:
        print("❌ TEST GEFAALD. Er is nog een hindernis.")

if __name__ == "__main__":
    final_test()
