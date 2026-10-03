"""
Ricky Assistant

This module provides a small command-line assistant for handling email
replies, downloading 3D model attachments (.3mf), slicing them using an
external slicer, estimating print costs, and performing small API
queries (e.g., Google Maps). It is written to be readable and
educational; comments explain what each section does so you can learn
"""
import email
import imaplib
import json
import math
import os
import re
import smtplib
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from email import policy
from email.message import EmailMessage

# Optional third-party import for speech recognition. The try/except
# keeps the dependency optional so the assistant can run without it.
try:
    import speech_recognition as sr
except ImportError:
    sr = None


class RickyAssistant:
    """Main assistant class grouping features for email, 3D printing,
    and small utility functions.

    Each method below has a short comment explaining its purpose so
    you can learn how the assistant is structured.
    """

    def __init__(self):
        self._load_env()
        self.gemini_api_key = os.environ.get("RICKY_GEMINI_API_KEY")
        self.google_maps_api_key = os.environ.get("RICKY_GOOGLE_MAPS_API_KEY")
        self.gmail_app_password = os.environ.get("RICKY_GMAIL_APP_PASSWORD")
        self.gmail_email = os.environ.get("RICKY_GMAIL_EMAIL")
        self.slicer_cli_path = os.environ.get("RICKY_SLICER_CLI_PATH")
        self.slicer_command_template = os.environ.get("RICKY_SLICER_COMMAND_TEMPLATE")
        self.default_location = os.environ.get("RICKY_DEFAULT_LOCATION", "")

    def _load_env(self):
        """Load configuration from .env file if it exists."""
        env_paths = [".env", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")]
        for p in env_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            if "=" in line:
                                k, v = line.split("=", 1)
                                k = k.strip()
                                v = v.strip()
                                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                                    v = v[1:-1]
                                os.environ[k] = v
                except Exception:
                    pass

    def verify_configuration(self):
        """Check required environment variables and warn if missing.

        Returns False when any required configuration is missing.
        """
        # Refresh configuration values in case environment has been updated
        self.gemini_api_key = os.environ.get("RICKY_GEMINI_API_KEY")
        self.google_maps_api_key = os.environ.get("RICKY_GOOGLE_MAPS_API_KEY")
        self.gmail_app_password = os.environ.get("RICKY_GMAIL_APP_PASSWORD")
        self.gmail_email = os.environ.get("RICKY_GMAIL_EMAIL")
        self.slicer_cli_path = os.environ.get("RICKY_SLICER_CLI_PATH")
        self.slicer_command_template = os.environ.get("RICKY_SLICER_COMMAND_TEMPLATE")
        self.default_location = os.environ.get("RICKY_DEFAULT_LOCATION", "")

        missing = []
        if not self.gemini_api_key:
            missing.append("RICKY_GEMINI_API_KEY")
        if not self.google_maps_api_key:
            missing.append("RICKY_GOOGLE_MAPS_API_KEY")
        if not self.gmail_app_password:
            missing.append("RICKY_GMAIL_APP_PASSWORD")
        if not self.gmail_email:
            missing.append("RICKY_GMAIL_EMAIL")
        if not self.slicer_cli_path:
            missing.append("RICKY_SLICER_CLI_PATH")

        if missing:
            print("WARNING: The following environment variables are missing:")
            for name in missing:
                print(f"  - {name}")
            print("Ricky will still run, but some features may be unavailable.")
            print("Please set those variables before using the full assistant.\n")
            return False
        return True

    def generate_response(self, prompt: str, model: str = "gemini-1.5-flash") -> str:
        """Generate text using a configured LLM (Gemini 1.5)."""
        self.gemini_api_key = os.environ.get("RICKY_GEMINI_API_KEY")
        if not self.gemini_api_key:
            return f"[GENERATION DISABLED] Prompt received: {prompt}"

        if "gemini" not in model:
            model = "gemini-1.5-flash"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_api_key}"
        headers = {
            "Content-Type": "application/json",
        }
        body = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024
            }
        }
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            try:
                if hasattr(self, "set_state"):
                    self.set_state("thinking")
            except Exception:
                pass
            with urllib.request.urlopen(request, timeout=30) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                candidates = response_data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
                return "[NO RESPONSE FROM GEMINI]"
        except Exception as exc:
            return f"[GENERATION ERROR] {exc}"
        finally:
            try:
                if hasattr(self, "set_state"):
                    self.set_state("idle")
            except Exception:
                pass

    def create_email_reply(self, incoming_subject: str, incoming_body: str, tone: str = "professional") -> str:
        """Draft a polite email reply using the text generation helper."""
        prompt = (
            "You are Ricky, a helpful assistant who answers emails clearly and professionally. "
            f"Write a reply to the following email. Use a {tone} tone and include a polite closing.\n\n"
            f"Incoming Subject: {incoming_subject}\n"
            f"Incoming Body: {incoming_body}\n\n"
            "Reply:"
        )
        return self.generate_response(prompt)

    def send_email(self, recipient: str, subject: str, body: str) -> bool:
        """Send a plain-text email via Gmail's SMTP server.

        Requires `RICKY_GMAIL_EMAIL` and `RICKY_GMAIL_APP_PASSWORD` to be set.
        """
        if not self.gmail_app_password or not self.gmail_email:
            print("Gmail credentials missing. Set RICKY_GMAIL_EMAIL and RICKY_GMAIL_APP_PASSWORD.")
            return False

        message = EmailMessage()
        message["From"] = self.gmail_email
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
                smtp.login(self.gmail_email, self.gmail_app_password)
                smtp.send_message(message)
            print(f"Email sent to {recipient}.")
            return True
        except Exception as exc:
            print(f"Failed to send email: {exc}")
            return False

    def _unique_filepath(self, save_dir: str, filename: str) -> str:
        """Return a non-colliding filepath by appending a numeric suffix.

        Useful when saving multiple attachments that may share names.
        """
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(save_dir, filename)
        index = 1
        while os.path.exists(candidate):
            candidate = os.path.join(save_dir, f"{base}_{index}{ext}")
            index += 1
        return candidate

    def download_3mf_attachments_from_email(
        self,
        save_dir: str = ".",
        search_from: str = None,
        search_subject: str = None,
        max_emails: int = 10,
        latest_only: bool = True,
    ) -> dict:
        """Connect to Gmail via IMAP and save any .3mf attachments found.

        Returns a dict containing either `error` or a list of `attachments`.
        """
        if not self.gmail_email or not self.gmail_app_password:
            return {"error": "Gmail credentials are not configured.", "attachments": []}

        os.makedirs(save_dir, exist_ok=True)
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com") as imap:
                imap.login(self.gmail_email, self.gmail_app_password)
                imap.select("INBOX")

                criteria = []
                if search_from:
                    criteria.extend(["FROM", f'"{search_from}"'])
                if search_subject:
                    criteria.extend(["SUBJECT", f'"{search_subject}"'])
                if not criteria:
                    criteria = ["ALL"]

                status, message_ids = imap.search(None, *criteria)
                if status != "OK":
                    return {"error": "Failed to search email inbox.", "attachments": []}

                ids = message_ids[0].split()
                if latest_only:
                    ids = ids[-1:]
                else:
                    ids = ids[-max_emails:]
                attachments = []
                for msg_id in reversed(ids):
                    status, data = imap.fetch(msg_id, "(RFC822)")
                    if status != "OK":
                        continue
                    raw_message = data[0][1]
                    message = email.message_from_bytes(raw_message, policy=policy.default)
                    message_from = message.get("From")
                    message_subject = message.get("Subject")
                    message_date = message.get("Date")
                    message_id_str = msg_id.decode("utf-8") if isinstance(msg_id, bytes) else str(msg_id)
                    for part in message.iter_attachments():
                        filename = part.get_filename()
                        if filename and filename.lower().endswith(".3mf"):
                            filepath = self._unique_filepath(save_dir, filename)
                            with open(filepath, "wb") as file_handle:
                                file_handle.write(part.get_payload(decode=True))
                            attachments.append({
                                "path": filepath,
                                "email_from": message_from,
                                "email_subject": message_subject,
                                "email_date": message_date,
                                "message_id": message_id_str,
                            })
                if not attachments:
                    return {"error": "No .3mf attachments found.", "attachments": []}
                return {"error": None, "attachments": attachments}
        except Exception as exc:
            return {"error": f"Email download failed: {exc}", "attachments": []}

    def download_and_slice_3mf_from_email(
        self,
        save_dir: str = ".",
        search_from: str = None,
        search_subject: str = None,
        layer_height: float = 0.2,
        infill: int = 20,
        print_speed: int = 60,
        filament_diameter_mm: float = 1.75,
        latest_only: bool = True,
    ) -> dict:
        """Download .3mf attachments and run the slicer to produce G-code.

        Returns a summary list for each processed attachment.
        """
        download_result = self.download_3mf_attachments_from_email(
            save_dir=save_dir,
            search_from=search_from,
            search_subject=search_subject,
            latest_only=latest_only,
        )
        if download_result.get("error"):
            return {"error": download_result["error"], "results": []}

        results = []
        for attachment in download_result["attachments"]:
            output_path = os.path.splitext(attachment["path"])[0] + ".gcode"
            summary = self.slice_model(
                attachment["path"],
                output_path,
                layer_height=layer_height,
                infill=infill,
                print_speed=print_speed,
                filament_diameter_mm=filament_diameter_mm,
            )
            results.append({
                "input": attachment["path"],
                "output": output_path,
                "summary": summary,
                "email_from": attachment.get("email_from"),
                "email_subject": attachment.get("email_subject"),
                "email_date": attachment.get("email_date"),
                "message_id": attachment.get("message_id"),
            })
        return {"error": None, "results": results}

    def estimate_3d_print_quote(
        self,
        volume_cc: float,
        material_type: str = "PLA",
        print_time_hours: float = 1.0,
        flat_rate: float = 5.0,
        labor_rate_per_hour: float = 5.0,
        markup_percent: float = 0.0,
    ) -> dict:
        """Calculate a 3D print cost estimate based on grams and printer time.
        
        PLA: $0.10 for every 100g (density 1.24 g/cc)
        PETG: $0.20 for every 100g (density 1.27 g/cc)
        Flat setup rate: $5.00
        Hourly printing rate: $5.00/hour
        """
        density = 1.24 if material_type.upper() == "PLA" else 1.27
        cost_per_g = (0.10 / 100.0) if material_type.upper() == "PLA" else (0.20 / 100.0)
        
        weight_g = volume_cc * density
        material_cost = weight_g * cost_per_g
        labor_cost = print_time_hours * labor_rate_per_hour
        subtotal = material_cost + labor_cost + flat_rate
        markup = subtotal * (markup_percent / 100.0)
        total = subtotal + markup
        
        return {
            "volume_cc": round(volume_cc, 2),
            "weight_g": round(weight_g, 2),
            "material_type": material_type.upper(),
            "material_cost": round(material_cost, 2),
            "labor_cost": round(labor_cost, 2),
            "flat_rate": round(flat_rate, 2),
            "markup_percent": markup_percent,
            "markup_cost": round(markup, 2),
            "total_quote": round(total, 2),
        }

    def slice_model(
        self,
        model_path: str,
        output_path: str,
        layer_height: float = 0.2,
        infill: int = 20,
        print_speed: int = 60,
        filament_diameter_mm: float = 1.75,
    ) -> str:
        """Invoke the configured slicer to generate G-code from a model.

        The method builds a command, runs it, and attempts to extract
        filament/time metrics from the resulting G-code file.
        """
        if not self.slicer_cli_path:
            return "Slicer CLI path not configured. Set RICKY_SLICER_CLI_PATH."

        if not os.path.isfile(model_path):
            return f"Model file not found: {model_path}"

        command = self.build_slicer_command(model_path, output_path, layer_height, infill, print_speed)
        if not command:
            return "Slicer command could not be built. Check your RICKY_SLICER_CLI_PATH or RICKY_SLICER_COMMAND_TEMPLATE."

        try:
            if isinstance(command, str):
                result = subprocess.run(command, capture_output=True, text=True, timeout=300, shell=True)
            else:
                result = subprocess.run(command, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                stderr = result.stderr.strip() or result.stdout.strip()
                return f"Slicer failed: {stderr}"
            summary = f"Slicing completed successfully. Output: {output_path}"
            metrics = self.extract_gcode_metrics(output_path, filament_diameter_mm)
            if metrics.get("error"):
                summary += f"\nMetrics unavailable: {metrics['error']}"
            else:
                summary += (
                    f"\nEstimated filament: {metrics['filament_length_mm']} mm "
                    f"({metrics['filament_weight_g']} g, {metrics['filament_volume_cc']} cc)"
                )
                if metrics.get("print_time"):
                    summary += f"\nEstimated print time: {metrics['print_time']}"
            return summary
        except FileNotFoundError:
            return f"Slicer binary not found at {self.slicer_cli_path}."
        except subprocess.TimeoutExpired:
            return "Slicer command timed out."
        except Exception as exc:
            return f"Error running slicer: {exc}"

    def extract_gcode_metrics(self, gcode_path: str, filament_diameter_mm: float = 1.75) -> dict:
        """Parse a G-code file to estimate filament usage and print time.

        The method looks for common slicer comments and also tracks E
        extrusion values to compute filament length when explicit
        comments are missing.
        """
        if not os.path.isfile(gcode_path):
            return {"error": f"G-code file not found: {gcode_path}"}

        filament_mm = None
        print_time = None
        absolute_e = True
        last_e = 0.0
        e_started = False

        try:
            with open(gcode_path, "r", encoding="utf-8", errors="ignore") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue

                    if "M83" in line:
                        absolute_e = False
                    elif "M82" in line:
                        absolute_e = True

                    if filament_mm is None:
                        m = re.search(r"filament used\s*[:=]\s*([0-9.]+)\s*(m|mm)", line, re.I)
                        if m:
                            amount = float(m.group(1))
                            unit = m.group(2).lower()
                            filament_mm = amount * 1000.0 if unit == "m" else amount

                    if print_time is None:
                        t = re.search(r"estimated printing time\s*[:=]\s*(.+)", line, re.I)
                        if not t:
                            t = re.search(r"estimated print time\s*[:=]\s*(.+)", line, re.I)
                        if not t:
                            t = re.search(r"estimated time\s*[:=]\s*(.+)", line, re.I)
                        if t:
                            print_time = t.group(1).strip()

                    comment_split = line.split(";", 1)[0].strip()
                    if not comment_split:
                        continue

                    if comment_split.startswith("G") or comment_split.startswith("M"):
                        parts = comment_split.split()
                        has_e = False
                        current_e = None
                        for part in parts:
                            if part.startswith("E") and len(part) > 1:
                                try:
                                    current_e = float(part[1:])
                                    has_e = True
                                except ValueError:
                                    pass

                        if has_e and current_e is not None:
                            if comment_split.startswith("G92"):
                                last_e = current_e
                                e_started = True
                                continue

                            if not e_started:
                                last_e = current_e
                                e_started = True

                            delta = current_e - last_e if absolute_e else current_e
                            if absolute_e:
                                last_e = current_e
                            if delta > 0:
                                filament_mm = (filament_mm or 0.0) + delta
        except Exception as exc:
            return {"error": f"Failed to read G-code: {exc}"}

        if filament_mm is None:
            return {"error": "Filament usage could not be detected in the generated G-code."}

        filament_volume_cc = math.pi * (filament_diameter_mm / 2) ** 2 * filament_mm / 1000.0
        filament_weight_g = filament_volume_cc * 1.24
        return {
            "filament_length_mm": round(filament_mm, 2),
            "filament_volume_cc": round(filament_volume_cc, 2),
            "filament_weight_g": round(filament_weight_g, 2),
            "print_time": print_time,
        }

    def build_slicer_command(
        self,
        model_path: str,
        output_path: str,
        layer_height: float,
        infill: int,
        print_speed: int,
    ):
        """Create the command (list or string) to invoke the slicer CLI.

        A user can override the default behavior via
        `RICKY_SLICER_COMMAND_TEMPLATE` in the environment.
        """
        if self.slicer_command_template:
            return self.slicer_command_template.format(
                exe=self.slicer_cli_path,
                input=model_path,
                output=output_path,
                layer_height=layer_height,
                infill=infill,
                print_speed=print_speed,
            )

        if not self.slicer_cli_path:
            return None

        basename = os.path.basename(self.slicer_cli_path).lower()
        if "elegoo" in basename:
            return [
                self.slicer_cli_path,
                "--load",
                model_path,
                "--output",
                output_path,
                "--layer-height",
                str(layer_height),
                "--infill",
                str(infill),
                "--speed",
                str(print_speed),
            ]

        if "curaengine" in basename or "cura" in basename:
            return [
                self.slicer_cli_path,
                "--load",
                model_path,
                "--output",
                output_path,
                "--layer-height",
                str(layer_height),
                "--infill",
                str(infill),
                "--speed",
                str(print_speed),
            ]

        return [
            self.slicer_cli_path,
            "--load",
            model_path,
            "--layer-height",
            str(layer_height),
            "--infill",
            str(infill),
            "--speed",
            str(print_speed),
            "--output",
            output_path,
        ]

    def estimate_travel_time(self, origin: str, destination: str) -> str:
        """Query Google Distance Matrix API to estimate travel time."""
        if not self.google_maps_api_key:
            return "Google Maps API key is not configured."

        params = {
            "origins": origin,
            "destinations": destination,
            "key": self.google_maps_api_key,
        }
        url = "https://maps.googleapis.com/maps/api/distancematrix/json?" + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("status") != "OK":
                    return f"Maps API error: {data.get('status')}"
                element = data["rows"][0]["elements"][0]
                if element.get("status") != "OK":
                    return f"Route error: {element.get('status')}"
                distance = element["distance"]["text"]
                duration = element["duration"]["text"]
                return f"Estimated distance: {distance}, time: {duration}."
        except Exception as exc:
            return f"Google Maps request failed: {exc}"

    def listen(self, prompt: str = None) -> str:
        """Capture speech from the microphone and transcribe it.

        Uses the `speech_recognition` package; if it's not installed the
        method returns a helpful message instead of raising an ImportError.
        """
        if sr is None:
            return "Speech recognition library is not installed."

        recognizer = sr.Recognizer()
        audio = None
        try:
            try:
                if hasattr(self, "set_state"):
                    self.set_state("listening")
            except Exception:
                pass
            with sr.Microphone() as source:
                if prompt:
                    print(prompt)
                recognizer.adjust_for_ambient_noise(source, duration=1)
                audio = recognizer.listen(source)
            try:
                return recognizer.recognize_google(audio)
            except sr.UnknownValueError:
                return "I couldn't understand the speech."
            except sr.RequestError as exc:
                return f"Speech service error: {exc}"
        finally:
            try:
                if hasattr(self, "set_state"):
                    self.set_state("idle")
            except Exception:
                pass
    def build_slicer_command(
        self,
        model_path: str,
        output_path: str,
        layer_height: float,
        infill: int,
        print_speed: int,
    ):
        """Return a command (string or list) to invoke the slicer CLI.

        If `RICKY_SLICER_COMMAND_TEMPLATE` is provided, format and use
        that. Otherwise try reasonable defaults for common slicer
        executables.
        """
        if self.slicer_command_template:
            return self.slicer_command_template.format(
                exe=self.slicer_cli_path,
                input=model_path,
                output=output_path,
                layer_height=layer_height,
                infill=infill,
                print_speed=print_speed,
            )

        if not self.slicer_cli_path:
            return None

        basename = os.path.basename(self.slicer_cli_path).lower()
        if "elegoo" in basename:
            return [
                self.slicer_cli_path,
                "--load",
                model_path,
                "--output",
                output_path,
                "--layer-height",
                str(layer_height),
                "--infill",
                str(infill),
                "--speed",
                str(print_speed),
            ]

        if "curaengine" in basename or "cura" in basename:
            return [
                self.slicer_cli_path,
                "--load",
                model_path,
                "--output",
                output_path,
                "--layer-height",
                str(layer_height),
                "--infill",
                str(infill),
                "--speed",
                str(print_speed),
            ]

        return [
            self.slicer_cli_path,
            "--load",
            model_path,
            "--layer-height",
            str(layer_height),
            "--infill",
            str(infill),
            "--speed",
            str(print_speed),
            "--output",
            output_path,
        ]

    def estimate_travel_time(self, origin: str, destination: str) -> str:
        """Query Google Distance Matrix API to estimate travel time.

        Returns a short human-readable string or an error message.
        """
        if not self.google_maps_api_key:
            return "Google Maps API key is not configured."

        params = {
            "origins": origin,
            "destinations": destination,
            "key": self.google_maps_api_key,
        }
        url = "https://maps.googleapis.com/maps/api/distancematrix/json?" + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("status") != "OK":
                    return f"Maps API error: {data.get('status')}"
                element = data["rows"][0]["elements"][0]
                if element.get("status") != "OK":
                    return f"Route error: {element.get('status')}"
                distance = element["distance"]["text"]
                duration = element["duration"]["text"]
                return f"Estimated distance: {distance}, time: {duration}."
        except Exception as exc:
            return f"Google Maps request failed: {exc}"

    def listen(self, prompt: str = None) -> str:
        """Record audio from the microphone and return recognized text.

        Uses the `speech_recognition` package. If it's not available the
        method returns a message explaining the missing dependency.
        """
        if sr is None:
            return "Speech recognition library is not installed."

        recognizer = sr.Recognizer()
        audio = None
        try:
            try:
                if hasattr(self, "set_state"):
                    self.set_state("listening")
            except Exception:
                pass
            with sr.Microphone() as source:
                if prompt:
                    print(prompt)
                recognizer.adjust_for_ambient_noise(source, duration=1)
                audio = recognizer.listen(source)
            try:
                return recognizer.recognize_google(audio)
            except sr.UnknownValueError:
                return "I couldn't understand the speech."
            except sr.RequestError as exc:
                return f"Speech service error: {exc}"
        finally:
            try:
                if hasattr(self, "set_state"):
                    self.set_state("idle")
            except Exception:
                pass

    def run_interactive(self):
        """Very small REPL to exercise the assistant features manually.

        Type a command to run a feature; this is useful for manual
        testing and learning how each piece behaves.
        """
        print("Welcome to Ricky. Type a command or say 'voice' to talk to Ricky.")
        self.verify_configuration()
        while True:
            print("\nCommands: email, quote, slice, travel, voice, exit")
            choice = input("Enter command: ").strip().lower()
            if choice == "exit":
                print("Goodbye from Ricky.")
                break
            if choice == "email":
                subject = input("Incoming email subject: ")
                body = input("Incoming email body: ")
                reply = self.create_email_reply(subject, body)
                print("\n--- Suggested reply ---")
                print(reply)
                if input("Send this reply? (y/n): ").strip().lower() == "y":
                    recipient = input("Send to email address: ")
                    self.send_email(recipient, f"Re: {subject}", reply)
            elif choice == "quote":
                volume = float(input("Volume in cubic centimeters: "))
                hours = float(input("Estimated print time in hours: "))
                quote = self.estimate_3d_print_quote(volume, print_time_hours=hours)
                print(json.dumps(quote, indent=2))
            elif choice == "slice":
                model_path = input("Model file path: ")
                output_path = input("Output G-code path: ")
                print(self.slice_model(model_path, output_path))
            elif choice == "travel":
                origin = input("Origin address: ")
                destination = input("Destination address: ")
                print(self.estimate_travel_time(origin, destination))
            elif choice == "voice":
                print("Listening for your question...")
                voice_text = self.listen("Speak now.")
                print(f"You said: {voice_text}")
                answer = self.generate_response(f"Answer this user inquiry naturally: {voice_text}")
                print("\nRicky answers:")
                print(answer)
            else:
                print("Unknown command. Please choose one of the available commands.")

    def start_ui_action_poller(self, port, poll_interval: float = 0.5):
        """Start a background thread that polls the status UI for activation actions.

        When the UI posts an activation, the assistant will listen once, generate
        a response, and print it to the console.
        """
        import threading
        import urllib.request
        import json
        import time

        def _poll():
            url = f'http://127.0.0.1:{port}/action'
            while True:
                try:
                    with urllib.request.urlopen(url, timeout=2) as resp:
                        data = json.loads(resp.read().decode('utf-8') or '{}')
                        action = data.get('action')
                        if action == 'activate':
                            print("\nActivated from UI — listening now...")
                            try:
                                if hasattr(self, 'set_state'):
                                    self.set_state('listening')
                            except Exception:
                                pass
                            voice_text = self.listen('Speak now.')
                            print(f"You said: {voice_text}")
                            try:
                                if hasattr(self, 'set_state'):
                                    self.set_state('thinking')
                            except Exception:
                                pass
                            answer = self.generate_response(f"Answer this user inquiry naturally: {voice_text}")
                            print('\nRicky answers:')
                            print(answer)
                            try:
                                if hasattr(self, 'set_state'):
                                    self.set_state('idle')
                            except Exception:
                                pass
                except Exception:
                    # ignore network errors and retry
                    pass
                time.sleep(poll_interval)

        thread = threading.Thread(target=_poll, daemon=True)
        thread.start()
        return thread


if __name__ == "__main__":
    # Start the web UI server and open the page in a browser (replaces REPL).
    assistant = RickyAssistant()
    try:
        import web_ui
        server, port = web_ui.start_web_ui(assistant, open_browser=True)
        assistant.set_state = lambda s: setattr(server, 'status', s)
        print(f"Web UI running at http://127.0.0.1:{port}/")
        # Keep the main thread alive while server runs
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            try:
                server.shutdown()
            except Exception:
                pass
    except Exception as exc:
        print(f"Failed to start web UI: {exc}")
        print("Falling back to terminal REPL.")
        assistant.set_state = lambda s: None
        assistant.run_interactive()
