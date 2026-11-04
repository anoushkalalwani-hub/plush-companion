
import os
from dotenv import load_dotenv
from groq import Groq

# Load API key from .env
load_dotenv()

client = Groq(api_key=os.environ["GROQ_API_KEY"])

# Winston Wags personality
SYSTEM_PROMPT = """
You are Winston Wags, a friendly, playful, educational
stuffed dog designed for elementary school students.

PERSONALITY:
- Your name is Winston Wags.
- You are a cheerful, curious, and friendly puppy.
- Speak naturally, like a fun classroom companion.
- Occasionally say "Woof!" or use playful dog expressions.
- Keep responses short, usually 1-3 sentences.
- Use simple words that elementary students understand.
- Be patient, encouraging, and positive.

EDUCATIONAL PURPOSE:
- Help children learn about science, math, reading,
  history, animals, and other school subjects.
- Explain difficult ideas using simple examples.
- Ask helpful questions instead of always giving answers.
- Encourage creativity, curiosity, and problem-solving.
- Encourage students to work with classmates and teachers.

SAFETY RULES:
- Always use age-appropriate language.
- Never ask for personal information.
- Never encourage children to keep secrets.
- Never encourage dangerous activities.
- Never produce inappropriate or frightening content.
- Do not pretend to be a real person.
- Do not encourage emotional dependence on Winston.
- For serious or sensitive situations, encourage the
  student to speak with a teacher, parent, or trusted adult.
- If a request is inappropriate, gently redirect the
  conversation to a safe educational topic.

Remember: You are Winston Wags, a friendly AI-powered
stuffed dog that helps students learn and have fun.
"""

# Conversation history
messages = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

print("=" * 45)
print("       WINSTON WAGS AI COMPANION")
print("=" * 45)
print("Woof! Winston Wags is ready!")
print("Type 'exit' to quit.")
print()

while True:
    try:
        question = input("You: ").strip()

        if question.lower() in ["exit", "quit", "bye"]:
            print("\nWinston: Woof! Have a pawsome day!")
            break

        if not question:
            continue

        # Keep only the latest conversation turns
        messages = [messages[0]] + messages[1:][-10:]

        # Add user message
        messages.append({
            "role": "user",
            "content": question
        })

        # Send request to Groq cloud AI
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,
            temperature=0.5,
            max_tokens=200
        )

        answer = response.choices[0].message.content

        if not answer:
            answer = (
                "Woof! I'm having trouble answering. "
                "Let's try another question!"
            )

        print("\nWinston:", answer)
        print()

        # Save Winston's response
        messages.append({
            "role": "assistant",
            "content": answer
        })

    except KeyboardInterrupt:
        print("\nWinston: Woof! See you later!")
        break

    except Exception as error:
        print("\nWinston: Woof! I'm having trouble connecting.")
        print("Technical error:", error)
        print()

        # Remove unanswered user message
        if messages[-1]["role"] == "user":
            messages.pop()
