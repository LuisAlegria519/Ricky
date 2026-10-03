# Ricky AI Assistant

Ricky is a personal assistant focused on:
- answering emails
- giving 3D printing quotes
- handling verbal inquiries

## What you need to configure first

Ricky needs the following environment variables before the assistant can use all features:

- `RICKY_GEMINI_API_KEY` – Google Gemini API key from Google AI Studio
- `RICKY_GOOGLE_MAPS_API_KEY` – Google Maps API key with Distance Matrix API enabled
- `RICKY_GMAIL_EMAIL` – your Gmail address for sending email
- `RICKY_GMAIL_APP_PASSWORD` – a Gmail App Password (16-character code) generated from your Google Account security settings
- `RICKY_SLICER_CLI_PATH` – the full path to your slicer CLI executable (for example, the Elegoo Slicer command-line tool)
- `RICKY_SLICER_COMMAND_TEMPLATE` – optional command template for custom slicers like Elegoo Slicer

If the slicer path contains `elegoo`, Ricky will automatically use the Elegoo Slicer-style CLI flags.

## Recommended setup steps

1. Create a Gmail App Password:
   - Open your Google Account Security settings.
   - Find "App passwords" and generate a new 16-letter code.
   - Do not use your normal Gmail password.

2. Create a Google Maps API key:
   - Go to Google Cloud Console.
   - Enable the Distance Matrix API.
   - Copy the resulting API key.

3. Create a Gemini API key in Google AI Studio.

4. Install your slicing software and verify the CLI path works.

## Running Ricky

Open a terminal in this folder and run:

```powershell
python ricky_assistant.py
```

If you want to use voice commands, install `speech_recognition` and a supported microphone driver.

## Notes

- The assistant uses the Gemini API to generate email replies and answer questions.
- The Gmail App Password is required for email sending via SMTP.
- The `slice_model` function uses your slicer CLI command line tool and expects the binary path in `RICKY_SLICER_CLI_PATH`.
- For Elegoo Slicer or other custom slicer CLIs, you can optionally set `RICKY_SLICER_COMMAND_TEMPLATE`.
  Example:
  ```powershell
  setx RICKY_SLICER_COMMAND_TEMPLATE "{exe} --load \"{input}\" --output \"{output}\" --layer-height {layer_height} --infill {infill} --speed {print_speed}"
  ```
- Use the `email-slice` option in `Ricky_ears.py` to search your inbox for `.3mf` attachments from a client, download them, and automatically create G-code with your configured slicer.
- The 3D quote feature returns a simple estimate and can be adjusted with your actual material, labor, and finishing rates.
