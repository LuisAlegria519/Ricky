import http.server
import socketserver
import threading
import json
import webbrowser
import urllib.parse


HTML_PAGE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Ricky Assistant — Status</title>
  <style>
    :root { --bg:#111; --card:#1b1b1f; --accent:#39a0ff; --muted:#888; }
    body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;background:linear-gradient(180deg,#08101a,#0d0b14);font-family:Segoe UI,Helvetica,Arial;color:#fff}
    .card{width:360px;padding:24px;border-radius:12px;background:rgba(0,0,0,0.35);box-shadow:0 8px 30px rgba(0,0,0,0.6);text-align:center}
    h1{font-size:18px;margin:0 0 12px}
    .status{height:120px;display:flex;align-items:center;justify-content:center}
    .dot{width:18px;height:18px;margin:6px;border-radius:50%;background:var(--muted);opacity:0.25}
    .listening .dot{background:lime;opacity:1;animation: pulse 1s infinite ease-in-out}
    .thinking .dot{background:var(--accent);opacity:1;animation: bounce 1s infinite linear}
    .idle .dot{background:var(--muted);opacity:0.4}
    @keyframes pulse{0%{transform:scale(1);opacity:0.6}50%{transform:scale(1.8);opacity:1}100%{transform:scale(1);opacity:0.6}}
    @keyframes bounce{0%{transform:translateY(0)}50%{transform:translateY(-12px)}100%{transform:translateY(0)}}
    .label{margin-top:12px;color:var(--muted);font-size:14px}
  </style>
</head>
<body>
  <div class="card">
    <h1>Ricky Assistant</h1>
    <div id="status" class="status idle">
      <div class="dot"></div>
      <div class="dot"></div>
      <div class="dot"></div>
    </div>
    <div id="label" class="label">Idle</div>
    <div style="margin-top:14px">
      <button id="wakeBtn" style="padding:8px 12px;border-radius:8px;border:0;background:var(--accent);color:#000;font-weight:600">Wake Ricky</button>
      <small style="display:block;margin-top:8px;color:var(--muted)">Or say "hey Ricky" / "yo Ricky" (browser may request mic permission)</small>
    </div>
  </div>
  <script>
    async function fetchState(){
      try{
        const r = await fetch('/state');
        if(!r.ok) return null;
        const j = await r.json();
        return j.state||'idle';
      }catch(e){return null}
    }
    function applyState(s){
      const st = document.getElementById('status');
      const label = document.getElementById('label');
      st.className = 'status '+(s||'idle');
      label.textContent = (s||'idle').replace(/(^.|_.)/g, x => x.replace('_',' '));
    }
    async function loop(){
      const s = await fetchState();
      if(s) applyState(s);
      setTimeout(loop, 400);
    }
    loop();

    // Wake button
    document.getElementById('wakeBtn').addEventListener('click', async function(){
      try{ await fetch('/activate', {method:'POST'}); }catch(e){}
    });

    // Optional browser-side wake-word detection using Web Speech API
    try{
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if(SpeechRecognition){
        const recog = new SpeechRecognition();
        recog.continuous = true;
        recog.interimResults = false;
        recog.lang = 'en-US';
        recog.onresult = function(evt){
          for(let i=evt.resultIndex;i<evt.results.length;i++){
            const t = evt.results[i][0].transcript.toLowerCase();
            if(t.includes('ricky') || t.includes('hey ricky') || t.includes('yo ricky')){
              fetch('/activate', {method:'POST'}).catch(()=>{});
            }
          }
        };
        recog.onerror = ()=>{};
        recog.start();
      }
    }catch(e){}
  </script>
</body>
</html>
"""


class StatusHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ('/', '/index.html'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
            return
        if parsed.path == '/state':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            payload = {'state': getattr(self.server, 'status', 'idle')}
            self.wfile.write(json.dumps(payload).encode('utf-8'))
            return
        if parsed.path == '/action':
          # Return a pending action and clear it
          action = getattr(self.server, 'pending_action', None)
          payload = {'action': action}
          # clear pending
          self.server.pending_action = None
          self.send_response(200)
          self.send_header('Content-Type', 'application/json')
          self.end_headers()
          self.wfile.write(json.dumps(payload).encode('utf-8'))
          return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/set_state':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8') if length else ''
            params = urllib.parse.parse_qs(parsed.query)
            if not params and body:
                params = urllib.parse.parse_qs(body)
            state = (params.get('state') or [None])[0]
            if state:
                self.server.status = state
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'OK')
                return
            if parsed.path == '/activate':
              # set a one-shot action the assistant can pick up
              self.server.pending_action = 'activate'
              self.send_response(200)
              self.end_headers()
              self.wfile.write(b'OK')
              return
        self.send_response(404)
        self.end_headers()


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True


def open_in_chrome(url):
    import os, subprocess, webbrowser
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    for path in chrome_paths:
        if os.path.exists(path):
            try:
                subprocess.Popen([path, url])
                return True
            except Exception:
                pass
    for b_name in ['google-chrome', 'chrome']:
        try:
            chrome = webbrowser.get(b_name)
            chrome.open(url)
            return True
        except Exception:
            pass
    try:
        webbrowser.open(url)
        return True
    except Exception:
        return False

def start_status_server(open_browser=True):
    server = ThreadedTCPServer(('127.0.0.1', 0), StatusHandler)
    server.status = 'idle'
    server.pending_action = None
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    if open_browser:
        open_in_chrome(f'http://127.0.0.1:{port}/')
    return server, port


def set_state(port, state):
    import urllib.request
    import urllib.parse
    data = urllib.parse.urlencode({'state': state}).encode('utf-8')
    req = urllib.request.Request(f'http://127.0.0.1:{port}/set_state', data=data, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=1) as resp:
            return resp.read()
    except Exception:
        return None
