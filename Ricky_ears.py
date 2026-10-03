import os
import speech_recognition as sr

from ricky_assistant import RickyAssistant

def listen_to_ricky():
    # 1. Create the "ears" (the recognizer object)
    recognizer = sr.Recognizer()

    # 2. Tell Python to use your default microphone
    with sr.Microphone() as source:
        print("Ricky is adjusting for background noise... hold on.")
        # This listens for 1 second to figure out how loud the room is
        recognizer.adjust_for_ambient_noise(source, duration=1)
        
        print("Ricky is listening! Speak now...")
        
        # 3. Capture the audio
        audio_data = recognizer.listen(source)
        print("Got it! Processing your speech...")

        try:
            # 4. Send the audio to Google's free transcriber
            text = recognizer.recognize_google(audio_data)
            print("\n--- RICKY HEARD ---")
            print(f'"{text}"')
            print("-------------------\n")
            return text
        except sr.UnknownValueError:
            print("Ricky couldn't understand what you said. Try speaking clearer.")
        except sr.RequestError as e:
            print(f"Ricky couldn't reach the internet to translate the audio: {e}")
        return None


def run_menu(assistant: RickyAssistant):
    print("Welcome to Ricky. Choose a mode to continue.")
    while True:
        print("\nOptions: voice, email, quote, slice, email-slice, exit")
        command = input("Enter option: ").strip().lower()
        if command == "exit":
            print("Goodbye from Ricky.")
            break
        elif command == "voice":
            text = listen_to_ricky()
            if not text:
                print("No speech captured. Try again.")
                continue
            print("Ricky is answering your question...")
            answer = assistant.generate_response(f"Answer this user inquiry naturally: {text}")
            print("\n--- RICKY ANSWERS ---")
            print(answer)
        elif command == "email":
            subject = input("Incoming email subject: ").strip()
            body = input("Incoming email body: ").strip()
            tone = input("Reply tone (professional/friendly): ").strip() or "professional"
            reply = assistant.create_email_reply(subject, body, tone)
            print("\n--- Suggested reply ---")
            print(reply)
            if input("Send this reply? (y/n): ").strip().lower() == "y":
                recipient = input("Send to email address: ").strip()
                assistant.send_email(recipient, f"Re: {subject}", reply)
        elif command == "quote":
            try:
                volume = float(input("Volume in cubic centimeters: ").strip())
                hours = float(input("Estimated print time in hours: ").strip())
            except ValueError:
                print("Please enter valid numbers for volume and time.")
                continue
            quote = assistant.estimate_3d_print_quote(volume, print_time_hours=hours)
            print("\n--- 3D Print Quote ---")
            for key, value in quote.items():
                print(f"{key}: {value}")
        elif command == "slice":
            model_path = input("Model file path (.3mf or STL): ").strip()
            output_path = input("Output G-code path: ").strip()
            try:
                layer_height = float(input("Layer height (mm, default 0.2): ").strip() or 0.2)
                infill = int(input("Infill percentage (default 20): ").strip() or 20)
                speed = int(input("Print speed (mm/s, default 60): ").strip() or 60)
            except ValueError:
                print("Please enter valid numeric slicing settings.")
                continue
            print(assistant.slice_model(model_path, output_path, layer_height, infill, speed))
        elif command == "email-slice":
            search_from = input("Search from email address (client): ").strip() or None
            search_subject = input("Search subject contains (optional): ").strip() or None
            save_dir = input("Save attachments to folder (default current folder): ").strip() or "."
            latest_only_input = input("Use only the newest matching email? (Y/n): ").strip().lower() or "y"
            latest_only = latest_only_input != "n"
            try:
                os.makedirs(save_dir, exist_ok=True)
                layer_height = float(input("Layer height (mm, default 0.2): ").strip() or 0.2)
                infill = int(input("Infill percentage (default 20): ").strip() or 20)
                speed = int(input("Print speed (mm/s, default 60): ").strip() or 60)
            except ValueError:
                print("Please enter valid numeric slicing settings.")
                continue
            result = assistant.download_and_slice_3mf_from_email(
                save_dir=save_dir,
                search_from=search_from,
                search_subject=search_subject,
                layer_height=layer_height,
                infill=infill,
                print_speed=speed,
                latest_only=latest_only,
            )
            if result.get("error"):
                print(f"Failed: {result['error']}")
            else:
                print("\n--- Email 3MF Slice Results ---")
                for item in result["results"]:
                    print(f"Email from: {item.get('email_from')}")
                    print(f"Subject: {item.get('email_subject')}")
                    print(f"Date: {item.get('email_date')}")
                    print(f"Input: {item['input']}")
                    print(f"Output: {item['output']}")
                    print(item["summary"])
                    print("---")
        else:
            print("Unknown option. Choose voice, email, quote, slice, or exit.")


def main():
    assistant = RickyAssistant()
    assistant.verify_configuration()
    run_menu(assistant)


if __name__ == "__main__":
    main()
