import http.server
import socketserver
import threading
import urllib.parse
import json
import webbrowser

HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Ricky Debug</title>
  <style>
    body{font-family:Arial;background:#eee;color:#000;padding:20px}
    input{padding:8px;margin:5px;width:200px}
    button{padding:8px;margin:5px}
    pre{background:#ddd;padding:10px;border:1px solid #999}
  </style>
</head>
<body>
  <h1>Debug Test</h1>
  <input id="prompt" type="text" placeholder="Type something..." />
  <button onclick="testClick()">Click Me</button>
  <pre id="out">Ready</pre>
  
  <script>
    function testClick() {
      document.getElementById('out').textContent = 'Button clicked!';
      console.log('Button clicked - sending to /test');
      fetch('/test', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: new URLSearchParams({msg: 'hello'})
      })
      .then(r => r.json())
      .then(j => document.getElementById('out').textContent = 'Response: ' + JSON.stringify(j))
      .catch(e => document.getElementById('out').textContent = 'Error: ' + e);
    }
  </script>
</body>
</html>
"""

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress logging
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(HTML.encode('utf-8'))
    
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8') if length else ''
        params = urllib.parse.parse_qs(body)
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        msg = params.get('msg', ['?'])[0]
        response = {'received': msg, 'status': 'ok'}
        self.wfile.write(json.dumps(response).encode('utf-8'))

class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

if __name__ == '__main__':
    server = ThreadedServer(('127.0.0.1', 8888), Handler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"Debug server running at http://127.0.0.1:{port}/")
    print("Try opening in a browser and clicking the button")
    try:
        webbrowser.open(f'http://127.0.0.1:{port}/')
    except:
        pass
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down")
