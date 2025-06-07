import asyncio
import numpy as np
import tempfile
import os
import webbrowser
import threading
from flask import Flask, render_template, send_file
import wave
from pathlib import Path

class WebDisplay:
    def __init__(self, port=5000):
        # Get the directory where this script is located
        script_dir = Path(__file__).parent
        template_dir = script_dir / 'templates'
        
        self.app = Flask(__name__, template_folder=str(template_dir))
        self.port = port
        self.temp_dir = tempfile.mkdtemp()
        self.audio_files = []
        self.markdown_content = []
        self.setup_routes()
        
    def setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template('display.html', 
                                 markdown_content=self.markdown_content,
                                 audio_files=self.audio_files)
        
        @self.app.route('/audio/<filename>')
        def serve_audio(filename):
            return send_file(os.path.join(self.temp_dir, filename))
    
    def display_markdown(self, markdown_text):
        """Replace IPython.display.Markdown functionality"""
        self.markdown_content.append(markdown_text)
        print(f"Added markdown: {markdown_text}")
    
    def display_audio(self, audio_data, rate=24000, autoplay=True):
        """Replace IPython.display.Audio functionality"""
        # Save audio data as WAV file
        filename = f"audio_{len(self.audio_files)}.wav"
        filepath = os.path.join(self.temp_dir, filename)
        
        # Convert numpy array to WAV file
        with wave.open(filepath, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(rate)
            wav_file.writeframes(audio_data.tobytes())
        
        self.audio_files.append({
            'filename': filename,
            'autoplay': autoplay
        })
        print(f"Added audio file: {filename}")
    
    def start_server(self):
        """Start the Flask server in a separate thread"""
        def run_server():
            try:
                self.app.run(host='127.0.0.1', port=self.port, debug=False, use_reloader=False)
            except OSError as e:
                if "Address already in use" in str(e):
                    print(f"Port {self.port} is already in use. Trying port {self.port + 1}")
                    self.port += 1
                    self.app.run(host='127.0.0.1', port=self.port, debug=False, use_reloader=False)
                else:
                    raise e
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        # Wait a moment for server to start, then open browser
        import time
        time.sleep(2)
        webbrowser.open(f'http://127.0.0.1:{self.port}')
        
        return server_thread
    
    def cleanup(self):
        """Clean up temporary files"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

# Create a global instance
web_display = WebDisplay()

# Replacement functions for IPython.display
def display(content):
    """Replace IPython.display.display"""
    if hasattr(content, '_repr_markdown_'):
        web_display.display_markdown(content._repr_markdown_())
    elif hasattr(content, 'data'):
        # Handle Audio objects
        if hasattr(content, 'rate'):
            web_display.display_audio(content.data, content.rate, getattr(content, 'autoplay', False))
    else:
        print(f"Displayed: {content}")

class Markdown:
    """Replace IPython.display.Markdown"""
    def __init__(self, data):
        self.data = data
    
    def _repr_markdown_(self):
        return self.data

class Audio:
    """Replace IPython.display.Audio"""
    def __init__(self, data, rate=22050, autoplay=False):
        self.data = data
        self.rate = rate
        self.autoplay = autoplay