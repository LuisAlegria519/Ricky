import http.server
import socketserver
import json
import threading
import webbrowser

HTML = """<!doctype html>
<html>
<head>
<title>Test</title>
</head>
<body>
<h1>Test Page</h1>
<input id="test_input" type="text" value="hello" />
<button onclick="testFunc()">Click Me</button>
<div id="output">Waiting...</div>

<script>
function testFunc() {
  console.log("testFunc called");
  document.getElementById('output').textContent = "Clicked!";
}

window.addEventListener('load', function() {
  console.log("Page loaded, testFunc is:", typeof testFunc);
});
</script>
</body>
</html>
"""

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(HTML.encode('utf-8'))

class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

server = Server(('127.0.0.1', 8765), Handler)
port = 8765
print(f"Test server running at http://127.0.0.1:{port}/")
t = threading.Thread(target=server.serve_forever, daemon=True)
t.start()
webbrowser.open(f'http://127.0.0.1:{port}/')

try:
    while True:
        import time
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopped")
