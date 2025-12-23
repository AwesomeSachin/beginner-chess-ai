def rank_moves(move_data, move_model, risk_model, mode="Practical Move"):
    ranked = []

    for item in move_data:
        features = item["features"].reshape(1, -1)

        success_prob = move_model.predict_proba(features)[0][1]
        risk_label = risk_model.predict(features)[0]

        score = success_prob * 100

        if mode in ["Safe Move", "Learning Mode"]:
            if risk_label in ["Mistake", "Blunder"]:
                score -= 20

        ranked.append({
            "move": item["move"],
            "confidence": round(score, 1),
            "risk": risk_label,
            "features": item["features"]
        })

    ranked.sort(key=lambda x: x["confidence"], reverse=True)
    return ranked
