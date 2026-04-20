"""Voice listener with configurable wake word detection for ARGUS.

Provides speech recognition using the SpeechRecognition library with
Google's Web Speech API. Supports wake word activation (default: "argus")
and graceful fallback to keyboard input when no microphone is available.

Typical usage:
    from client.voice_listener import VoiceListener

    listener = VoiceListener()
    wake = listener.listen_for_wake_word()
    if wake:
        command = listener.listen_for_command()
"""

import logging
import os
from typing import Optional

import speech_recognition as sr
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class VoiceListener:
    """Speech recognition listener with wake word activation.

    Monitors the default microphone for a configurable wake word and
    captures follow-up commands. Falls back to keyboard input when
    no microphone is detected.

    Attributes:
        wake_word: The activation phrase to listen for (lowercase).
        recognizer: SpeechRecognition Recognizer instance.
        microphone_available: Whether a working microphone was detected.
    """

    def __init__(self) -> None:
        """Initialize the voice listener.

        Configures the wake word from the ``WAKE_WORD`` environment
        variable (default: ``argus``), creates a Recognizer instance,
        and probes for a working microphone.
        """
        self.wake_word: str = os.getenv("WAKE_WORD", "argus").lower()
        self.recognizer: sr.Recognizer = sr.Recognizer()
        self.microphone_available: bool = False
        self._check_microphone()

    def _check_microphone(self) -> None:
        """Probe for a working microphone and calibrate ambient noise.

        Attempts to open the default microphone and adjust for ambient
        noise levels. Sets ``microphone_available`` based on whether a
        microphone was successfully accessed.
        """
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            self.microphone_available = True
            logger.info("Microphone ready")
        except (OSError, AttributeError) as exc:
            logger.warning("No microphone found: %s", exc)
            logger.info("Falling back to keyboard input mode")
            self.microphone_available = False

    def listen_for_wake_word(self) -> Optional[str]:
        """Listen for the configured wake word via microphone.

        Blocks for up to 5 seconds waiting for speech, then checks
        whether the transcribed text contains the wake word.

        Returns:
            The transcribed text if the wake word was detected,
            None if no wake word was heard, the microphone is
            unavailable, or recognition failed.
        """
        if not self.microphone_available:
            return None
        try:
            with sr.Microphone() as source:
                audio: sr.AudioData = self.recognizer.listen(
                    source, timeout=5, phrase_time_limit=5
                )
            text: str = self.recognizer.recognize_google(audio).lower()
            logger.debug("Heard: %s", text)
            if self.wake_word in text:
                return text
            return None
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            return None
        except Exception as exc:
            logger.warning("Wake word detection error: %s", exc)
            return None

    def listen_for_command(self) -> str:
        """Listen for a voice command after wake word activation.

        If no microphone is available, falls back to keyboard input.
        Blocks for up to 10 seconds waiting for speech.

        Returns:
            The transcribed command string, or an empty string if
            recognition failed or no speech was detected.
        """
        if not self.microphone_available:
            try:
                return input("  > Type your command: ").strip()
            except (EOFError, KeyboardInterrupt):
                return ""
        try:
            logger.info("Listening for command...")
            with sr.Microphone() as source:
                audio: sr.AudioData = self.recognizer.listen(
                    source, timeout=10, phrase_time_limit=10
                )
            text: str = self.recognizer.recognize_google(audio)
            logger.info("Command received: %s", text)
            return text
        except sr.WaitTimeoutError:
            logger.info("No command heard (timeout)")
            return ""
        except sr.UnknownValueError:
            logger.info("Could not understand command")
            return ""
        except Exception as exc:
            logger.warning("Command listening error: %s", exc)
            return ""
