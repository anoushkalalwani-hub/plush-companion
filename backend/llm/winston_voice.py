
import os
import io
import wave
import subprocess

import sounddevice as sd
from dotenv import load_dotenv
from groq import Groq


# ==========================================
# WINSTON WAGS - AI VOICE CHATBOT
# Windows PC Version
# ==========================================

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise RuntimeError(
        "GROQ_API_KEY not found. Add it to your .env file."
    )

client = Groq(api_key=api_key)


# ==========================================
# WINSTON'S PERSONALITY
# ==========================================

SYSTEM_PROMPT = """
You are Winston Wags, a friendly AI-powered
stuffed dog for elementary school classrooms.

PERSONALITY:
- You are cheerful, playful, patient, and kind.
- Speak in simple, age-appropriate language.
- Keep answers short, usually 1-3 sentences.
- Occasionally say "Woof!"
- Encourage curiosity and learning.

EDUCATIONAL PURPOSE:
- Help children understand math, science,
  reading, history, and other school subjects.
- Explain ideas using simple examples.
- Encourage students to think independently.
- Guide students back to their schoolwork.

SAFETY:
- Never ask for personal information.
- Never encourage keeping secrets.
- Never encourage unsafe activities.
- Avoid inappropriate or frightening content.
- Do not pretend to be a real animal or person.
- Do not encourage emotional dependence.
- For sensitive situations, suggest speaking
  with a teacher, parent, or trusted adult.
- Redirect inappropriate questions toward
  safe, educational subjects.

You are Winston Wags, a helpful classroom puppy.
"""

messages = [
    {"role": "system", "content": SYSTEM_PROMPT}
]


# ==========================================
# MICROPHONE SETTINGS
# ==========================================

SAMPLE_RATE = 16000
RECORD_SECONDS = 5

# Your Realtek microphone and speakers
sd.default.device = (1, 3)


# ==========================================
# WINDOWS TEXT-TO-SPEECH
# ==========================================

def speak(text):
    """Speak using Windows' built-in speech engine."""

    print("Speaking...", flush=True)

    powershell_code = """
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speaker.SetOutputToDefaultAudioDevice()
$speaker.Rate = 0
$speaker.Volume = 100
$speaker.Speak([Console]::In.ReadToEnd())
$speaker.Dispose()
"""

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                powershell_code
            ],
            input=text,
            text=True,
            capture_output=True,
            timeout=60
        )

        if result.returncode != 0:
            print("Speech error:", result.stderr)
        else:
            print("Finished speaking.")

    except subprocess.TimeoutExpired:
        print("Speech timed out.")


# ==========================================
# RECORD AUDIO
# ==========================================

def record_audio():
    """Record five seconds of microphone audio."""

    print("\nListening for 5 seconds...")
    print("Speak now!")

    audio = sd.rec(
        int(RECORD_SECONDS * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16"
    )

    sd.wait()

    print("Recording complete!")

    buffer = io.BytesIO()

    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(audio.tobytes())

    buffer.seek(0)

    return buffer


# ==========================================
# SPEECH TO TEXT - GROQ WHISPER
# ==========================================

def transcribe(audio):
    """Convert recorded audio into text."""

    print("Converting speech to text...")

    result = client.audio.transcriptions.create(
        file=("recording.wav", audio.getvalue()),
        model="whisper-large-v3-turbo",
        language="en"
    )

    return result.text.strip()


# ==========================================
# AI RESPONSE - GROQ
# ==========================================

def ask_winston(question):
    """Generate Winston's AI response."""

    global messages

    recent_history = messages[1:][-10:]

    request_messages = [
        messages[0],
        *recent_history,
        {"role": "user", "content": question}
    ]

    print("Winston is thinking...")

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=request_messages,
        temperature=0.5,
        max_tokens=200
    )

    answer = response.choices[0].message.content

    if not answer:
        answer = "Woof! Could you please ask me again?"

    messages = request_messages + [
        {"role": "assistant", "content": answer}
    ]

    return answer


# ==========================================
# MAIN PROGRAM
# ==========================================

def main():

    print("=" * 45)
    print("       WINSTON WAGS VOICE CHATBOT")
    print("=" * 45)

    print("Press Enter to talk to Winston.")
    print("Type 'exit' to quit.")

    greeting = "Woof! Hello! I'm Winston Wags!"

    print("\nWinston:", greeting)
    speak(greeting)

    while True:

        try:
            command = input(
                "\nPress Enter to speak: "
            ).strip()

            if command.lower() in ("exit", "quit"):
                speak("Woof! Have a pawsome day!")
                break

            # Record microphone audio
            audio = record_audio()

            # Convert speech into text
            question = transcribe(audio)

            if not question:
                print(
                    "Winston: I didn't hear you. Try again!"
                )
                continue

            print("\nYou:", question)

            # Generate AI response
            answer = ask_winston(question)

            print("\nWinston:", answer)

            # Speak the response aloud
            speak(answer)

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break

        except Exception as error:
            print("\nERROR:", error)
            print("Please try again.")


if __name__ == "__main__":
    main()
