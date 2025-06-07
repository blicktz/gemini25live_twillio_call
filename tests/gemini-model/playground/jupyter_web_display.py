import asyncio
import numpy as np
import tempfile
import os
import webbrowser
import threading
from flask import Flask, render_template_string
import base64
import io

class JupyterWebDisplay:
    def __init__(self, port=5000):
        self.app = Flask(__name__)
        self.port = port
        self.content_items = []
        self.setup_routes()
        
    def setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template_string(self.get_html_template(), content_items=self.content_items)
    
    def get_html_template(self):
        return '''
<!DOCTYPE html>
<html>
<head>
    <title>Gemini Audio Output</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .content-item { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .markdown-content { background-color: #f8f9fa; }
        .audio-content { background-color: #e8f5e8; }
    </style>
    <script>
        // Auto-refresh every 2 seconds
        setTimeout(function() { location.reload(); }, 2000);
    </script>
</head>
<body>
    <h1>🎵 Gemini Audio Output</h1>
    <button onclick="location.reload()">🔄 Refresh</button>
    
    {% for item in content_items %}
        <div class="content-item {{ item.type }}-content">
            {{ item.html|safe }}
        </div>
    {% endfor %}
    
    {% if not content_items %}
        <p><em>Waiting for content... Auto-refreshing every 2 seconds.</em></p>
    {% endif %}
</body>
</html>
        '''
    
    def add_markdown(self, markdown_text):
        """Add markdown content using IPython-style rendering"""
        # Simple markdown to HTML conversion for basic formatting
        html = markdown_text.replace('**', '<strong>').replace('**', '</strong>')
        html = html.replace('*', '<em>').replace('*', '</em>')
        
        self.content_items.append({
            'type': 'markdown',
            'html': f'<div>{html}</div>'
        })
        print(f"Added markdown: {markdown_text}")
    
    def add_audio(self, audio_data, rate=24000, autoplay=True):
        """Add audio content using HTML5 audio element (like IPython.display.Audio)"""
        # Convert numpy array to base64 encoded WAV data
        audio_base64 = self._numpy_to_wav_base64(audio_data, rate)
        
        autoplay_attr = 'autoplay' if autoplay else ''
        audio_html = f'''
        <div>
            <p><strong>Audio Output (Rate: {rate} Hz)</strong></p>
            <audio controls {autoplay_attr} style="width: 100%;">
                <source src="data:audio/wav;base64,{audio_base64}" type="audio/wav">
                Your browser does not support the audio element.
            </audio>
        </div>
        '''
        
        self.content_items.append({
            'type': 'audio',
            'html': audio_html
        })
        print(f"Added audio data (rate: {rate})")
    
    def _numpy_to_wav_base64(self, audio_data, rate):
        """Convert numpy array to base64 encoded WAV data (mimics IPython.display.Audio)"""
        # Create a BytesIO buffer to write WAV data
        buffer = io.BytesIO()
        
        # Write WAV header and data
        import wave
        with wave.open(buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(rate)
            # Ensure audio_data is int16
            if audio_data.dtype != np.int16:
                audio_data = audio_data.astype(np.int16)
            wav_file.writeframes(audio_data.tobytes())
        
        # Get the WAV data and encode as base64
        wav_data = buffer.getvalue()
        return base64.b64encode(wav_data).decode('utf-8')
    
    def start_server(self):
        """Start the Flask server"""
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
        
        # Wait for server to start, then open browser
        import time
        time.sleep(2)
        webbrowser.open(f'http://127.0.0.1:{self.port}')
        
        return server_thread

# Create global instance
jupyter_display = JupyterWebDisplay()

# IPython.display replacement functions
def display(content):
    """Replace IPython.display.display"""
    if hasattr(content, '_repr_markdown_'):
        jupyter_display.add_markdown(content._repr_markdown_())
    elif hasattr(content, 'data') and hasattr(content, 'rate'):
        # Handle Audio objects
        jupyter_display.add_audio(content.data, content.rate, getattr(content, 'autoplay', False))
    else:
        print(f"Displayed: {content}")

class Markdown:
    """Replace IPython.display.Markdown"""
    def __init__(self, data):
        self.data = data
    
    def _repr_markdown_(self):
        return self.data

class Audio:
    """Replace IPython.display.Audio - works exactly like the original"""
    def __init__(self, data, rate=22050, autoplay=False):
        self.data = data
        self.rate = rate
        self.autoplay = autoplay