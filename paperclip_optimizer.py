def evaluate_trade(swap_params, current_sol_balance):
    """
    Paperclip is koud en berekend. Hij weigert trades die wiskundig niet kloppen.
    """
    print("🖇️ Paperclip: Berekenen van Yield-to-Cost verhouding...")
    
    amount_lamports = swap_params.get("amount_lamports", 0)
    amount_sol = amount_lamports / 1_000_000_000
    
    if amount_sol <= 0:
        print("🖇️ Paperclip: Bedrag is 0. Trade afgewezen.")
        return False, "Bedrag is 0."
        
    # Risico 1: Gas Fee & Rent Reserve
    # Solana transacties kosten gas. Als we te weinig SOL overhouden, brickt de wallet.
    MIN_SOL_RESERVE = 0.01 
    
    # Als 'from' SOL is, trekken we het af. Als 'to' SOL is, tellen we het op (of negeren we de aftrek).
    from_mint = swap_params.get("from")
    to_mint = swap_params.get("to")
    
    projected_balance = current_sol_balance
    if from_mint == "So11111111111111111111111111111111111111112":
        projected_balance -= amount_sol
    
    if projected_balance < MIN_SOL_RESERVE:
        reason = f"Onvoldoende SOL reserve. Huidig: {current_sol_balance}, Geprojecteerd: {projected_balance}. Minimum: {MIN_SOL_RESERVE}."
        print(f"🖇️ Paperclip BLOKKEERT: {reason}")
        return False, reason
        
    # Risico 2: Micro-trades (Slippage vs Winst)
    if amount_sol < 0.001:
        reason = f"Trade volume te laag ({amount_sol} SOL). Slippage eet de winst op."
        print(f"🖇️ Paperclip BLOKKEERT: {reason}")
        return False, reason

    print(f"✅ Paperclip: Wiskunde klopt. Trade goedgekeurd. Verwachte ROI > Netwerkkosten.")
    return True, "Goedgekeurd door Paperclip."
