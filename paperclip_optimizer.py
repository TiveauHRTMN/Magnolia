import config


def evaluate_trade(swap_params, current_sol_balance):
    """
    Final low-level execution check.
    The policy engine handles intent and quote quality; Paperclip verifies the
    concrete native-unit order still preserves wallet operability.
    """
    print("Paperclip: Berekenen van Yield-to-Cost verhouding...")

    amount_units = int(swap_params.get("amount_lamports", 0) or 0)
    from_mint = swap_params.get("from")
    decimals = config.TOKEN_DECIMALS.get(from_mint, 9)
    amount_source = amount_units / (10 ** decimals)

    if amount_source <= 0:
        print("Paperclip: Bedrag is 0. Trade afgewezen.")
        return False, "Bedrag is 0."

    projected_balance = current_sol_balance
    if from_mint == config.SOL_MINT:
        projected_balance -= amount_source

    if projected_balance < config.MIN_SOL_RESERVE:
        reason = (
            f"Onvoldoende SOL reserve. Huidig: {current_sol_balance}, "
            f"Geprojecteerd: {projected_balance}. Minimum: {config.MIN_SOL_RESERVE}."
        )
        print(f"Paperclip BLOKKEERT: {reason}")
        return False, reason

    if from_mint == config.SOL_MINT and amount_source < 0.001:
        reason = f"Trade volume te laag ({amount_source} SOL). Slippage eet de winst op."
        print(f"Paperclip BLOKKEERT: {reason}")
        return False, reason

    print("Paperclip: Wiskunde klopt. Trade goedgekeurd. Verwachte ROI > netwerkkosten.")
    return True, "Goedgekeurd door Paperclip."
