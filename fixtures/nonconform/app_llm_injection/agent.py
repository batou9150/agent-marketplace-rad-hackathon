from openai import OpenAI

client = OpenAI(api_key="test-dummy-key")


def answer_user(user_input: str) -> str:
    system_prompt = f"Tu es un assistant bancaire. Contexte utilisateur: {user_input}"

    # Direct completion call without timeout
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Aide-moi"},
        ],
    )
    return response.choices[0].message.content
