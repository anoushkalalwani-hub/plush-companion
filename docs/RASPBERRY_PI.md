# Running Winston on a Raspberry Pi

The whole voice simulator runs on the Pi (Raspberry Pi 4 or 5) with a USB microphone and a USB speaker (D-026).

**Adult developer testing only.** The Pi holds your Groq key in `.env`, an exception to the "no keys on the device" rule (D-026). Keep the Pi with you. Never commit or share its `.env`. If the Pi or its SD card leaves your hands, replace the key in the Groq console.

Commands below run in the Pi's terminal.

## 1. System packages

Use Raspberry Pi OS (64-bit). Install git, the audio library the Python code needs, and espeak-ng, which is the backup voice:

```bash
sudo apt update && sudo apt install -y git libportaudio2 espeak-ng
```

## 2. uv (Python and dependencies)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close and reopen the terminal so `uv` is on your PATH.

## 3. The code

```bash
git clone https://github.com/anoushkalalwani-hub/plush-companion.git
```

```bash
cd plush-companion && git switch m3a-terminal-voice
```

```bash
uv sync --group voice
```

## 4. Winston's voice model (about 350 MB)

```bash
mkdir -p models/kokoro
```

```bash
curl -fL -o models/kokoro/kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx
```

```bash
curl -fL -o models/kokoro/voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin
```

## 5. Settings (`.env`)

Copy `.env` from your laptop. The quickest way is over your home network, run **on the laptop**, with your Pi's user name and IP address (`hostname -I` on the Pi shows the address):

```bash
scp /Users/anoushka/plush-companion/.env PI_USER@PI_ADDRESS:~/plush-companion/.env
```

Or copy it with a USB stick, and delete it from the stick afterwards.

## 6. Pick the USB speaker and microphone

Plug both in, then list the audio devices:

```bash
uv run --group voice python -m device.simulator --list-devices
```

Each line starts with a number, then the name, then how many inputs (`in`) and outputs (`out`) it has. Your speaker has outputs; your microphone has inputs. Add two lines to the Pi's `.env`, using a number from the list or a distinctive part of the name:

```
AUDIO_OUTPUT_DEVICE=USB Audio
AUDIO_INPUT_DEVICE=2
```

Use numbers if the speaker and microphone have similar names. Numbers can change when you replug devices; names don't.

## 7. Check the speaker

```bash
uv run --group voice --env-file .env python -m device.simulator.voice_preview am_michael
```

You should hear Winston's greeting. If you don't:

- Turn the speaker's own volume knob up, then run `alsamixer`. Press F6, pick the USB speaker, and raise the volume. `M` unmutes a channel.
- Check `AUDIO_OUTPUT_DEVICE` names the speaker, not HDMI or headphones.

## 8. Talk to Winston

```bash
uv run --group voice --env-file .env python -m device.simulator
```

Press Enter, speak, and press Enter again. Type `q` and press Enter to quit. Add `--type` to type instead of speaking.

## Troubleshooting

| You see | Do this |
|---|---|
| `PortAudio library not found` | `sudo apt install -y libportaudio2` |
| `voice unavailable: ... using the backup voice` | Kokoro failed and espeak-ng spoke instead. Check step 4's files exist. |
| `speaker refused the audio` | Pick the speaker by number in `AUDIO_OUTPUT_DEVICE`. |
| Nothing heard when you speak | Check `AUDIO_INPUT_DEVICE` names the USB microphone. Check its level in `alsamixer` (F4 shows capture levels). |
| Replies take several seconds to start | Kokoro is slower on a Pi than a laptop, especially a Pi 4. The pipeline (Groq) takes about 2 seconds; Kokoro adds a few more. |
| Many "talk to a grown-up" replies | Groq's free tier allows about one question a minute. |
