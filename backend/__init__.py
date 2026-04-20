"""ARGUS Backend Package.

Provides the server-side components for the ARGUS ambient AI screen
intelligence agent, including the FastAPI application, Gemini-powered
vision analysis, context management, cloud storage integration, and
Firestore persistence.

Modules:
    main: FastAPI application entrypoint with WebSocket and REST endpoints.
    gemini_agent: Gemini 2.0 Flash Vision integration for screen analysis.
    context_manager: Rolling observation window with time-based eviction.
    storage: Google Cloud Storage and local filesystem persistence.
    firestore_client: Google Cloud Firestore integration for structured data.
    security: Rate limiting, authentication, and input sanitization.
"""
