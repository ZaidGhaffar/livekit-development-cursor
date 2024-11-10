# ** Project Overview **

 I'm building a real-time phone-calling assistant, but with a unique twist – my assistant uses a limited set of responses to keep things efficient and free of cost! 🎉 Instead of relying on a costly TTS, I convert responses into audio files (MP3s) and built a small model to predict which file to play, enabling smooth real-time conversation. 🎶

I'm leveraging LiveKit's amazing features like VoicePipelineAgent and currently using Groq for speech-to-text, then pass that text to my model or Groq's LLM to predict the audio file name to play. and than play the audio file.
code to play files we need to modify it in order to use it with livekit :
class SoundInit:
    def __init__(self) -> None:
        self.path_mp3file =  r'C:\\AI\\new journey\\the fastest journey\\phone_calling_the_24hr_project\\app\\Backend\\Voice_files'
        pygame.mixer.init()
        self.is_playing = threading.Event()

    def play_sound(self, file_name):
        pygame.mixer.init()
        try:
            pygame.mixer.music.load(os.path.join(self.path_mp3file, file_name))
            self.is_playing.set()  # Set the flag to indicate audio is playing
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            self.is_playing.clear()  # Clear the flag when audio stops playing
        except Exception as e:
            print(f"Error playing {file_name}: {e}")
            self.is_playing.clear()


you see here :
assistant = VoicePipelineAgent(
        vad=ctx.proc.userdata["vad"],
        stt=openai.STT.with_groq(),
        llm=openai.LLM.with_groq(model="gpt-4o-mini"),
        tts=openai.TTS(),
        chat_ctx=initial_ctx,
    )



Instead of using the tts of VoicePipelineAgent, I want to add a new feature to my assistant where it can play audio files from a local server.
for e.g:
tts=customtts,
something like that
all the code should be written in python.


# Documentation
here's the documentation of livekit: https://docs.livekit.io/home/


# Instructions
Since Livekit in open source that means you can use anything like going into thier pipeline & changing the tts to play the audio files from a local server. or changing VoicePipelineAgent pipeline you can do whatever yo want.
You have totally free hand do whatever you wanna do


