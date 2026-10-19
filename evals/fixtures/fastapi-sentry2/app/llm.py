import anthropic

client = anthropic.Anthropic()


def answer(question: str, user_email: str) -> str:
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=512,
        messages=[{"role": "user", "content": f"{user_email} asks: {question}"}],
    )
    return msg.content[0].text
