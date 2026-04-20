"""ARGUS Client Package.

Provides the local machine agent components for the ARGUS ambient AI
screen intelligence system, including screen capture with pixel-diff
filtering, voice-activated wake word detection, WebSocket communication,
and safe action execution via PyAutoGUI.

Modules:
    argus_client: Main client orchestrator with observation and command loops.
    screen_capture: Screen capture using MSS with intelligent change detection.
    voice_listener: Speech recognition with configurable wake word activation.
    executor: Safe action execution with confidence thresholding.
"""
