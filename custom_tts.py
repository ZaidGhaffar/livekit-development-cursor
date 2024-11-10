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
import numpy as np
from livekit.rtc import AudioFrame

logger = logging.getLogger(__name__)

@dataclass
class TTSMetrics:
    """Custom metrics class that matches LiveKit's expectations"""
    num_chars: int  # Changed from chars to num_chars
    duration_ms: float  # Changed from duration to duration_ms
    cost_usd: float  # Changed from cost to cost_usd

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

    def emit(self, event: str, data: Any = None):
        if event in self._events:
            for callback in self._events[event]:
                try:
                    if data is not None:
                        callback(data)
                    else:
                        callback()
                except Exception as e:
                    logger.error(f"Error in event callback: {e}")

@dataclass
class TTSCapabilities:
    streaming: bool = True
    async_api: bool = True

class AudioFrameWrapper:
    """Wrapper class to provide the frame attribute"""
    def __init__(self, frame: AudioFrame):
        self.frame = frame

class TTSStream:
    def __init__(self, tts):
        self.tts = tts
        self.text_queue = deque()
        self._ended = False
        self._closed = False
        self._accumulated_text = ""
        
    def push_text(self, text: str):
        """Add text to the stream"""
        if self._ended or self._closed:
            return
        self._accumulated_text += text
        
    def end_input(self):
        """Mark the stream as ended for input"""
        self._ended = True
        print(f"\nComplete LLM Response ↗️: {self._accumulated_text}")
        # Now that we have the complete response, add it to the queue
        if self._accumulated_text.strip():
            self.text_queue.append(self._accumulated_text.strip())
        
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
                    await asyncio.sleep(0.1)
                    continue
                    
                text = self.text_queue.popleft()
                # Process the complete response
                audio_filename = self._get_audio_filename(text)
                async for frame in self.tts.synthesize(audio_filename):
                    if self._closed:
                        break
                    # Wrap the AudioFrame in our wrapper class
                    yield AudioFrameWrapper(frame)
        finally:
            if not self._closed:
                await self.aclose()
                
    def _get_audio_filename(self, text: str) -> str:
        """Convert LLM response to audio filename"""
        # Simple mapping for now - if the intent is greeting, return greetings.wav
        text = text.lower().strip()
        if any(greeting in text for greeting in ["hello", "hi", "hey", "greetings"]):
            return "greetings.wav"
        # Add more mappings as needed
        return "greetings.wav"  # Default response

class CustomTTS(SimpleEventEmitter):
    def __init__(self, audio_path: str) -> None:
        super().__init__()
        self.audio_path = audio_path
        pygame.mixer.init()
        self.is_playing = threading.Event()
        self.capabilities = TTSCapabilities()
        self._current_audio = None
        self.sample_rate = 24000
        self.num_channels = 1
        self._agent_output = None
        
    def _create_audio_frame(self, audio_data: np.ndarray, frame_size: int) -> AudioFrame:
        if frame_size <= 0:
            frame_size = len(audio_data)
            
        if len(audio_data) < frame_size * self.num_channels:
            padding = frame_size * self.num_channels - len(audio_data)
            audio_data = np.pad(audio_data, (0, padding))
            
        frame = AudioFrame(
            data=audio_data.tobytes(),
            samples_per_channel=frame_size,
            sample_rate=self.sample_rate,
            num_channels=self.num_channels
        )
        return frame
        
    async def synthesize(self, filename: str) -> AsyncIterator[AudioFrame]:
        try:
            audio_file = os.path.join(self.audio_path, filename)
            
            if not os.path.exists(audio_file):
                logger.error(f"Audio file not found: {audio_file}")
                return
            
            with wave.open(audio_file, 'rb') as wav_file:
                self.sample_rate = wav_file.getframerate()
                self.num_channels = wav_file.getnchannels()
                duration = wav_file.getnframes() / self.sample_rate
                audio_data = np.frombuffer(wav_file.readframes(wav_file.getnframes()), dtype=np.int16)
            
            # Use the correct metric names
            metrics = TTSMetrics(
                num_chars=len(filename),  # Changed from chars to num_chars
                duration_ms=duration * 1000,  # Convert seconds to milliseconds
                cost_usd=0.0  # This is already correct
            )
            self.emit("metrics_collected", metrics)
            
            self._agent_output = True
            
            frame_size = int(self.sample_rate * 0.02)  # 20ms frames
            
            for i in range(0, len(audio_data), frame_size * self.num_channels):
                chunk = audio_data[i:i + frame_size * self.num_channels]
                if len(chunk) > 0:
                    frame = self._create_audio_frame(chunk, frame_size)
                    yield frame
                    await asyncio.sleep(0.02)
                    
        except Exception as e:
            logger.error(f"Error playing audio: {e}")
        finally:
            self._agent_output = None

    def stream(self) -> TTSStream:
        return TTSStream(self)
            
    def get_sample_rate(self) -> int:
        return self.sample_rate
            
    async def stop(self):
        if self._current_audio:
            self._current_audio.close()
            self._current_audio = None
        self._agent_output = None
            
    async def close(self):
        await self.stop()
        pygame.mixer.quit()

    def __del__(self):
        pygame.mixer.quit()
