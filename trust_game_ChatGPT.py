from openai import OpenAI
import re
import statistics
import csv
import random

# התחברות ל-OpenAI
client = OpenAI()

# מספר ההרצות לכל ניסוח
N_GAMES = 100

# המודל שבו נשתמש
MODEL_NAME = "gpt-4o-mini"

# סוגי הניסוחים
STYLES = ["neutral", "rational", "moral"]


# --------------------------------------------------
# פונקציה שבודקת אם תשובת המודל היא מספר תקין
# --------------------------------------------------

def extract_number(text, min_value, max_value):

    if text is None:
        raise ValueError("Model returned an empty response")

    # הסרת רווחים מיותרים
    text = text.strip()

    # בדיקה שהתשובה מכילה מספר בלבד
    if not re.fullmatch(r"\d+(?:\.\d+)?", text):
        raise ValueError(
            f"Model did not return a single valid number: {text}"
        )

    number = float(text)

    # בדיקה שהמספר נמצא בטווח המותר
    if not min_value <= number <= max_value:
        raise ValueError(
            f"Number {number} is outside the allowed range "
            f"[{min_value}, {max_value}]"
        )

    return number


# --------------------------------------------------
# פונקציה ששולחת פקודה למודל
# --------------------------------------------------

def ask_model(model_name, prompt):

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    return response.choices[0].message.content


# --------------------------------------------------
# ניסוחים שונים - שחקן 1
# --------------------------------------------------

player1_styles = {

    "neutral": "",

    "rational": """
Your sole objective is to maximize your own final payoff at the end of the game.
""",

    "moral": """
You care about being fair, acting morally, and building mutual trust.
"""
}


# --------------------------------------------------
# כללי המשחק - שחקן 1
# --------------------------------------------------

player1_rules = """
You are Player 1 in the Trust Game.

At the beginning of the game, you receive 10 shekels, while Player 2 receives no initial endowment.

You may send any amount between 0 and 10 shekels to Player 2.

Any amount you send will be tripled before reaching Player 2.

Player 2 will receive the tripled amount and may choose to return any amount between 0 and the amount received from you.

How much would you like to send to Player 2?

Write only a number between 0 and 10, without any explanations or additional text.
"""


# --------------------------------------------------
# ניסוחים שונים - שחקן 2
# --------------------------------------------------

player2_styles = {

    "neutral": "",

    "rational": """
Your sole objective is to maximize your own final payoff at the end of the game.
""",

    "moral": """
You care about being fair, acting morally, and maintaining mutual trust.
"""
}


# --------------------------------------------------
# כללי המשחק - שחקן 2
# --------------------------------------------------

player2_rules = """
You are Player 2 in the Trust Game.

At the beginning of the game, Player 1 received 10 shekels, while you received no initial endowment.

Player 1 chose to send you {send} shekels.

This amount was tripled, so you received {tripled} shekels.

You may choose to return any amount between 0 and {tripled} shekels to Player 1 from the amount you received.

{style_instruction}

How much would you like to return to Player 1?

Write only a number between 0 and {tripled}, without any explanations or additional text.
"""


# --------------------------------------------------
# פונקציה שמריצה את משחק האמון
# --------------------------------------------------

def run_simulation(model_name, style):

    p1_results = []
    p2_results = []

    send_results = []
    return_results = []
    return_rate_results = []

    all_results = []

    invalid_p1 = 0
    invalid_p2 = 0

    for i in range(N_GAMES):

        print(
            f"Running {model_name} | "
            f"{style} | Game {i + 1}/{N_GAMES}"
        )

        # יצירת רשומה עבור המשחק הנוכחי
        game_result = {

            "Experiment_Type": "Full_Trust_Game",

            "Game": i + 1,

            "Model": model_name,

            "Style": style,

            "Player1_Raw_Response": None,

            "Player2_Raw_Response": None,

            "Amount_Sent": None,

            "Amount_Returned": None,

            "Player2_Chosen_Amount": None,

            "Return_Rate": None,

            "Player1_Payoff": None,

            "Player2_Payoff": None,

            "Status": None
        }

        # ------------------------------------------
        # שחקן 1
        # ------------------------------------------

        prompt1 = (
            player1_rules
            + player1_styles[style]
        )

        raw_response1 = ask_model(
            model_name,
            prompt1
        )

        game_result["Player1_Raw_Response"] = raw_response1

        try:

            send_amount = extract_number(
                raw_response1,
                0,
                10
            )

        except ValueError:

            invalid_p1 += 1

            game_result["Status"] = "Invalid Player 1"

            all_results.append(game_result)

            continue

        game_result["Amount_Sent"] = send_amount

        send_results.append(send_amount)

        tripled = send_amount * 3

        # ------------------------------------------
        # שחקן 2
        # ------------------------------------------

        prompt2 = player2_rules.format(
            style_instruction=player2_styles[style],
            send=send_amount,
            tripled=tripled
        )

        raw_response2 = ask_model(
            model_name,
            prompt2
        )

        game_result["Player2_Raw_Response"] = raw_response2

        try:

            return_amount = extract_number(
                raw_response2,
                0,
                tripled
            )

        except ValueError:

            invalid_p2 += 1

            game_result["Status"] = "Invalid Player 2"

            all_results.append(game_result)

            continue

        game_result["Amount_Returned"] = return_amount
        game_result["Player2_Chosen_Amount"] = return_amount

        return_results.append(return_amount)

        # ------------------------------------------
        # חישוב שיעור ההחזרה
        # ------------------------------------------

        if tripled > 0:

            return_rate = return_amount / tripled

            return_rate_results.append(return_rate)

        else:

            return_rate = None

        game_result["Return_Rate"] = return_rate

        # ------------------------------------------
        # חישוב הרווח הסופי של כל שחקן
        # ------------------------------------------

        p1_final = 10 - send_amount + return_amount

        p2_final = tripled - return_amount

        p1_results.append(p1_final)

        p2_results.append(p2_final)

        game_result["Player1_Payoff"] = p1_final

        game_result["Player2_Payoff"] = p2_final

        game_result["Status"] = "Valid"

        all_results.append(game_result)

    # --------------------------------------------------
    # חישוב ממוצעים
    # --------------------------------------------------

    avg_send = (
        statistics.mean(send_results)
        if send_results
        else None
    )

    avg_return = (
        statistics.mean(return_results)
        if return_results
        else None
    )

    avg_return_rate = (
        statistics.mean(return_rate_results)
        if return_rate_results
        else None
    )

    avg_p1 = (
        statistics.mean(p1_results)
        if p1_results
        else None
    )

    avg_p2 = (
        statistics.mean(p2_results)
        if p2_results
        else None
    )

    return {

        "avg_send": avg_send,

        "avg_return": avg_return,

        "avg_return_rate": avg_return_rate,

        "avg_p1": avg_p1,

        "avg_p2": avg_p2,

        "invalid_p1": invalid_p1,

        "invalid_p2": invalid_p2,

        "all_results": all_results
    }


# --------------------------------------------------
# הרצת הניסוי המקורי עבור כל הניסוחים
# --------------------------------------------------

experiment_results = []

for style in STYLES:

    results = run_simulation(
        MODEL_NAME,
        style
    )

    experiment_results.extend(
        results["all_results"]
    )

    print(f"\n--- STYLE: {style.upper()} ---")

    print(
        f"Average amount sent: "
        f"{results['avg_send']}"
    )

    print(
        f"Average amount returned: "
        f"{results['avg_return']}"
    )

    print(
        f"Average return rate: "
        f"{results['avg_return_rate']}"
    )

    print(
        f"Average payoff Player 1: "
        f"{results['avg_p1']}"
    )

    print(
        f"Average payoff Player 2: "
        f"{results['avg_p2']}"
    )

    print(
        f"Invalid Player 1 responses: "
        f"{results['invalid_p1']}"
    )

    print(
        f"Invalid Player 2 responses: "
        f"{results['invalid_p2']}"
    )


# --------------------------------------------------
# ניסוי נוסף: שחקן 2 עם סכומים אקראיים
# --------------------------------------------------

# יצירת מספר סכומים אקראיים השווה למספר ההרצות
random_amounts = [
    random.randint(1, 10)
    for _ in range(N_GAMES)
]

print("\n--- INDEPENDENT PLAYER 2 ---")

print(
    f"Average random amount: "
    f"{statistics.mean(random_amounts) if random_amounts else None}"
)

# בדיקת אותם סכומים בשלושת הניסוחים
for style in STYLES:

    chosen_amounts = []

    for game, sent in enumerate(random_amounts, start=1):

        tripled = sent * 3

        prompt2 = player2_rules.format(
            style_instruction=player2_styles[style],
            send=sent,
            tripled=tripled
        )

        raw_response2 = ask_model(
            MODEL_NAME,
            prompt2
        )

        try:

            returned = extract_number(
                raw_response2,
                0,
                tripled
            )

            chosen_amounts.append(returned)

            status = "Valid"

        except ValueError:

            returned = None

            status = "Invalid Player 2"

        # חישוב שיעור ההחזרה
        if returned is not None and tripled > 0:
            return_rate = returned / tripled
        else:
            return_rate = None

        # הוספת תוצאות הניסוי לאותה רשימה
        experiment_results.append({

            "Experiment_Type": "Independent_Player2",

            "Game": game,

            "Model": MODEL_NAME,

            "Style": style,

            "Player1_Raw_Response": None,

            "Player2_Raw_Response": raw_response2,

            "Amount_Sent": sent,

            "Amount_Returned": returned,

            "Player2_Chosen_Amount": returned,

            "Return_Rate": return_rate,

            "Player1_Payoff": (
                10 - sent + returned
                if returned is not None
                else None
            ),

            "Player2_Payoff": (
                tripled - returned
                if returned is not None
                else None
            ),

            "Status": status
        })

        print(
            f"Independent | {style} | "
            f"Game {game}/{N_GAMES} | "
            f"sent={sent}, returned={returned}"
        )

    # חישוב ממוצע החלטות שחקן 2 לפי ניסוח
    avg_chosen = (
        statistics.mean(chosen_amounts)
        if chosen_amounts
        else None
    )

    print(
        f"\nAverage Player 2 chosen amount "
        f"({style}): {avg_chosen}"
    )


# --------------------------------------------------
# שמירת כל תוצאות שני הניסויים בקובץ CSV אחד
# --------------------------------------------------

with open(
    "trust_game_results.csv",
    "w",
    newline="",
    encoding="utf-8-sig"
) as file:

    fieldnames = [

        "Experiment_Type",

        "Game",

        "Model",

        "Style",

        "Player1_Raw_Response",

        "Player2_Raw_Response",

        "Amount_Sent",

        "Amount_Returned",

        "Player2_Chosen_Amount",

        "Return_Rate",

        "Player1_Payoff",

        "Player2_Payoff",

        "Status"
    ]

    writer = csv.DictWriter(
        file,
        fieldnames=fieldnames
    )

    writer.writeheader()

    writer.writerows(experiment_results)


print("\nExperiment completed!")
print("Results saved to trust_game_results.csv")



