def explain_move(best, rejected, elo):
    explanations = {}

    f = best["features"]
    why_best = []

    if f[-4] <= 0:
        why_best.append("It does not leave any piece hanging.")

    if f[-3] > 0:
        why_best.append("It improves king safety.")

    if f[-2] > 0:
        why_best.append("It improves piece development.")

    why_best.append(
        f"Players around {elo} Elo succeed more often with this move."
    )

    explanations["why_best"] = " ".join(why_best)

    why_not = []
    for r in rejected:
        rf = r["features"]
        reasons = []

        if rf[-4] > 0:
            reasons.append("leaves a piece hanging")

        if rf[-3] <= 0:
            reasons.append("does not improve king safety")

        if r["risk"] in ["Mistake", "Blunder"]:
            reasons.append("has a high mistake rate")

        if reasons:
            why_not.append(
                f"{r['move']} is risky because it " + ", ".join(reasons) + "."
            )

    explanations["why_not"] = why_not

    explanations["learning_tip"] = (
        "Develop pieces, protect your king, and avoid hanging material."
    )

    return explanations
