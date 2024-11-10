import os
import pygame
import threading
from typing import AsyncIterator, Optional, Callable, Any, Dict
import logging
from dataclasses import dataclass
from functools import partial
import wave
import asyncio
from collections import deque

logger = logging.getLogger(__name__)

class SimpleEventEmitter:
    def __init__(self):
        self._events = {}

    def on(self, event: str, callback: Optional[Callable] = None):
        def decorator(cb):
            if event not in self._events:
                self._events[event] = []
            self._events[event].append(cb)
            return cb

        if callback is None:
            return decorator
        return decorator(callback)

    def emit(self, event: str, *args, **kwargs):
        if event in self._events:
            for callback in self._events[event]:
                callback(*args, **kwargs)

@dataclass
class TTSCapabilities:
    streaming: bool = True
    async_api: bool = True

class TTSStream:
    def __init__(self, tts):
        self.tts = tts
        self.text_queue = deque()
        self.current_text = ""
        self._ended = False
        self._closed = False
        self._accumulated_text = ""
        
    def push_text(self, text: str):
        """Add text to the stream"""
        if self._ended or self._closed:
            return
        self._accumulated_text += text
        self.text_queue.append(text)
        
    def end_input(self):
        """Mark the stream as ended for input"""
        self._ended = True
        print(f"\nComplete LLM Response ↗️: {self._accumulated_text}\n")
        
    async def aclose(self):
        """Close the stream"""
        self._closed = True
        self.text_queue.clear()
        self._accumulated_text = ""
        await self.tts.stop()
        
    async def __aiter__(self):
        try:
            while (not self._ended or self.text_queue) and not self._closed:
                if not self.text_queue:
                    await asyncio.sleep(0.1)  # Small delay to prevent busy waiting
                    continue
                    
                text = self.text_queue.popleft()
                async for chunk in self.tts.synthesize(text):
                    if self._closed:
                        break
                    yield chunk
        finally:
            if not self._closed:
                await self.aclose()

class CustomTTS(SimpleEventEmitter):
    def __init__(self, audio_path: str) -> None:
        super().__init__()
        self.audio_path = audio_path
        pygame.mixer.init()
        self.is_playing = threading.Event()
        self.capabilities = TTSCapabilities()
        self._current_audio = None
        self.sample_rate = 24000  # Standard sample rate
        self.num_channels = 1     # Mono audio
        self._agent_output = None  # Required by VoicePipelineAgent
        self._current_text = None
        
    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        """
        Instead of synthesizing speech, this method will find and stream
        the appropriate audio file.
        """
        self._current_text = text
        try:
            # For now, assuming the text is the filename
            audio_file = os.path.join(self.audio_path, f"{text}.wav")
            
            if not os.path.exists(audio_file):
                logger.error(f"Audio file not found: {audio_file}")
                return
            
            # Get audio duration and other metrics
            with wave.open(audio_file, 'rb') as wav_file:
                duration = wav_file.getnframes() / wav_file.getframerate()
                # Update sample rate and channels from the actual file
                self.sample_rate = wav_file.getframerate()
                self.num_channels = wav_file.getnchannels()
                
            # Emit metrics before starting
            metrics = {
                "chars": len(text),
                "duration": duration,
                "cost": 0
            }
            self.emit("metrics_collected", metrics)
            
            # Set agent output to indicate we're processing
            self._agent_output = True
            
            # Read and stream the audio file
            chunk_size = 1024 * 16
            with open(audio_file, 'rb') as f:
                self._current_audio = f
                while chunk := f.read(chunk_size):
                    yield chunk
                self._current_audio = None
                    
        except Exception as e:
            logger.error(f"Error playing audio: {e}")
            self._current_audio = None
        finally:
            self._agent_output = None
            self._current_text = None

    def stream(self) -> TTSStream:
        """
        Create a new stream for text-to-speech synthesis.
        This method is required by VoicePipelineAgent.
        """
        return TTSStream(self)
            
    def get_sample_rate(self) -> int:
        """Return the sample rate of the audio output"""
        return self.sample_rate
            
    async def stop(self):
        """Stop the current audio playback"""
        if self._current_audio:
            self._current_audio.close()
            self._current_audio = None
        self._agent_output = None
        self._current_text = None
            
    async def close(self):
        """Cleanup resources"""
        await self.stop()
        pygame.mixer.quit()

    def __del__(self):
        """Cleanup on deletion"""
        pygame.mixer.quit()
