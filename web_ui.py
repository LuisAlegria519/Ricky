import http.server
import socketserver
import threading
import urllib.parse
import json
import webbrowser
import cgi
import tempfile
import os
import math
import re
import email
import imaplib
from email import policy

# Helper function to mask sensitive information
def mask_string(val, is_password=False):
    if not val:
        return ""
    if is_password:
        return "********"
    if len(val) <= 10:
        return "***"
    return val[:6] + "..." + val[-4:]

# Helper function to fetch recent emails
def fetch_inbox_emails(assistant):
    if not assistant.gmail_email or not assistant.gmail_app_password:
        return {"error": "Gmail credentials not configured. Please set them in Settings."}
    try:
        emails = []
        with imaplib.IMAP4_SSL("imap.gmail.com") as imap:
            imap.login(assistant.gmail_email, assistant.gmail_app_password)
            imap.select("INBOX")
            # Search for all messages and slice the last 15
            status, message_ids = imap.search(None, "ALL")
            if status == "OK":
                ids = message_ids[0].split()
                for msg_id in reversed(ids[-15:]):
                    status, data = imap.fetch(msg_id, "(RFC822)")
                    if status != "OK":
                        continue
                    raw = data[0][1]
                    msg = email.message_from_bytes(raw, policy=policy.default)
                    
                    sender = msg.get("From", "")
                    subject = msg.get("Subject", "")
                    date = msg.get("Date", "")
                    msg_id_str = msg_id.decode("utf-8") if isinstance(msg_id, bytes) else str(msg_id)
                    
                    # Check attachments
                    has_3d = False
                    attachments = []
                    for part in msg.iter_attachments():
                        filename = part.get_filename()
                        if filename:
                            attachments.append(filename)
                            if filename.lower().endswith(('.3mf', '.stl')):
                                has_3d = True
                    
                    # Extract snippet and body text
                    body_text = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            ctype = part.get_content_type()
                            cdisp = str(part.get('Content-Disposition', ''))
                            if ctype == 'text/plain' and 'attachment' not in cdisp:
                                body_text = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                break
                        if not body_text:
                            for part in msg.walk():
                                ctype = part.get_content_type()
                                cdisp = str(part.get('Content-Disposition', ''))
                                if ctype == 'text/html' and 'attachment' not in cdisp:
                                    body_text = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                    # Strip HTML tags
                                    body_text = re.sub('<[^<]+?>', '', body_text)
                                    break
                    else:
                        body_text = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                    
                    snippet = body_text[:140] + "..." if len(body_text) > 140 else body_text
                    
                    emails.append({
                        "id": msg_id_str,
                        "from": sender,
                        "subject": subject,
                        "date": date,
                        "snippet": snippet.strip(),
                        "body": body_text.strip(),
                        "attachments": attachments,
                        "has_3d_attachment": has_3d
                    })
        return {"emails": emails}
    except Exception as exc:
        return {"error": f"Failed to fetch emails: {exc}"}


HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Ricky AI — Personal Workspace</title>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-gradient: radial-gradient(circle at top right, #0b111e, #05070a);
      --card-bg: rgba(13, 20, 35, 0.55);
      --card-border: rgba(255, 255, 255, 0.06);
      --accent-primary: #7000ff;
      --accent-secondary: #00d4ff;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --status-idle: #22c55e;
      --status-listening: #ef4444;
      --status-thinking: #3b82f6;
      --status-slicing: #f59e0b;
    }
    
    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    body {
      font-family: 'Outfit', sans-serif;
      background: var(--bg-gradient);
      color: var(--text-main);
      height: 100vh;
      overflow: hidden;
      display: flex;
    }
    
    /* Layout */
    .app-container {
      display: flex;
      width: 100vw;
      height: 100vh;
    }
    
    /* Sidebar */
    .sidebar {
      width: 280px;
      background: rgba(8, 12, 22, 0.8);
      backdrop-filter: blur(20px);
      border-right: 1px solid var(--card-border);
      padding: 30px 24px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
    
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 40px;
    }
    
    .logo-orb {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
      box-shadow: 0 0 15px rgba(0, 212, 255, 0.4);
      position: relative;
    }
    
    .brand h2 {
      font-size: 20px;
      font-weight: 700;
      letter-spacing: 0.5px;
      background: linear-gradient(135deg, #fff, var(--text-muted));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    
    .nav-menu {
      display: flex;
      flex-direction: column;
      gap: 8px;
      flex-grow: 1;
    }
    
    .nav-item {
      display: flex;
      align-items: center;
      gap: 14px;
      padding: 14px 18px;
      border-radius: 12px;
      border: none;
      background: transparent;
      color: var(--text-muted);
      font-family: inherit;
      font-size: 15px;
      font-weight: 500;
      cursor: pointer;
      text-align: left;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .nav-item:hover, .nav-item.active {
      color: #fff;
      background: rgba(255, 255, 255, 0.05);
      border-left: 3px solid var(--accent-secondary);
      padding-left: 21px;
    }
    
    .nav-item svg {
      width: 20px;
      height: 20px;
      stroke: currentColor;
      fill: none;
      stroke-width: 2;
    }
    
    .sidebar-footer {
      color: var(--text-muted);
      font-size: 12px;
      letter-spacing: 0.5px;
      border-top: 1px solid rgba(255, 255, 255, 0.05);
      padding-top: 20px;
    }
    
    /* Main Content */
    .main-viewport {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    
    .top-header {
      height: 80px;
      border-bottom: 1px solid var(--card-border);
      padding: 0 40px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: rgba(8, 12, 22, 0.4);
      backdrop-filter: blur(10px);
      z-index: 10;
    }
    
    .top-header h1 {
      font-size: 22px;
      font-weight: 600;
    }
    
    .status-panel {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    
    .status-badge {
      display: flex;
      align-items: center;
      gap: 8px;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--card-border);
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 500;
    }
    
    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--status-idle);
      box-shadow: 0 0 10px var(--status-idle);
      transition: all 0.3s ease;
    }
    
    .status-dot.listening {
      background: var(--status-listening);
      box-shadow: 0 0 12px var(--status-listening);
      animation: pulse-dot 1s infinite;
    }
    
    .status-dot.thinking {
      background: var(--status-thinking);
      box-shadow: 0 0 12px var(--status-thinking);
      animation: pulse-dot 1s infinite;
    }
    
    .status-dot.slicing {
      background: var(--status-slicing);
      box-shadow: 0 0 12px var(--status-slicing);
      animation: pulse-dot 1s infinite;
    }
    
    @keyframes pulse-dot {
      0% { transform: scale(1); opacity: 0.6; }
      50% { transform: scale(1.3); opacity: 1; }
      100% { transform: scale(1); opacity: 0.6; }
    }
    
    /* Content Panels */
    .tab-content {
      flex: 1;
      overflow-y: auto;
      padding: 40px;
      display: none;
    }
    
    .tab-content.active {
      display: block;
    }
    
    /* Glass Card */
    .glass-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 20px;
      padding: 30px;
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.35);
      margin-bottom: 24px;
    }
    
    /* Common Elements */
    input[type=text], input[type=number], input[type=password], textarea, select {
      width: 100%;
      background: rgba(5, 7, 12, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 12px;
      padding: 14px 18px;
      color: #fff;
      font-family: inherit;
      font-size: 15px;
      margin-top: 8px;
      margin-bottom: 20px;
      transition: all 0.3s;
    }
    
    input:focus, textarea:focus, select:focus {
      outline: none;
      border-color: var(--accent-secondary);
      box-shadow: 0 0 10px rgba(0, 212, 255, 0.15);
      background: rgba(5, 7, 12, 0.8);
    }
    
    label {
      font-size: 13px;
      font-weight: 500;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
      color: #fff;
      font-family: inherit;
      font-weight: 600;
      font-size: 15px;
      padding: 14px 28px;
      border-radius: 12px;
      border: none;
      cursor: pointer;
      transition: all 0.3s;
      box-shadow: 0 4px 15px rgba(112, 0, 255, 0.3);
    }
    
    .btn:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(0, 212, 255, 0.5);
    }
    
    .btn-secondary {
      background: rgba(255, 255, 255, 0.06);
      color: var(--text-main);
      border: 1px solid var(--card-border);
      box-shadow: none;
    }
    
    .btn-secondary:hover {
      background: rgba(255, 255, 255, 0.12);
      box-shadow: none;
      border-color: rgba(255, 255, 255, 0.2);
    }
    
    /* Chat View */
    .chat-layout {
      display: flex;
      flex-direction: column;
      height: calc(100vh - 200px);
    }
    
    .chat-history {
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      background: rgba(5, 7, 12, 0.3);
      border-radius: 16px;
      border: 1px solid var(--card-border);
      display: flex;
      flex-direction: column;
      gap: 16px;
      margin-bottom: 20px;
    }
    
    .chat-bubble {
      max-width: 75%;
      padding: 16px 20px;
      border-radius: 18px;
      line-height: 1.5;
      font-size: 15px;
    }
    
    .chat-bubble.ricky {
      align-self: flex-start;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.03);
      border-bottom-left-radius: 4px;
    }
    
    .chat-bubble.user {
      align-self: flex-end;
      background: linear-gradient(135deg, rgba(112, 0, 255, 0.25), rgba(0, 212, 255, 0.25));
      border: 1px solid rgba(0, 212, 255, 0.25);
      border-bottom-right-radius: 4px;
    }
    
    .chat-input-row {
      display: flex;
      gap: 12px;
      align-items: center;
    }
    
    .chat-input-row input {
      margin: 0;
      flex-grow: 1;
    }
    
    .voice-pulse-btn {
      width: 50px;
      height: 50px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--card-border);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.3s;
      flex-shrink: 0;
      position: relative;
    }
    
    .voice-pulse-btn:hover {
      background: rgba(255, 255, 255, 0.1);
      border-color: rgba(255, 255, 255, 0.2);
    }
    
    .voice-pulse-btn.active {
      background: var(--status-listening);
      border-color: var(--status-listening);
      box-shadow: 0 0 15px var(--status-listening);
    }
    
    .voice-pulse-btn.active svg {
      stroke: #fff;
    }
    
    .voice-pulse-btn svg {
      width: 22px;
      height: 22px;
      stroke: var(--text-muted);
      fill: none;
      stroke-width: 2;
    }
    
    .wave-canvas-container {
      width: 120px;
      height: 40px;
      display: none;
      margin-left: 10px;
    }
    
    .wave-canvas-container.active {
      display: block;
    }
    
    /* 3D Print Hub */
    .drop-zone {
      border: 2px dashed rgba(255, 255, 255, 0.15);
      border-radius: 16px;
      padding: 40px;
      text-align: center;
      cursor: pointer;
      transition: all 0.3s;
      margin-bottom: 24px;
      background: rgba(5, 7, 12, 0.2);
    }
    
    .drop-zone:hover, .drop-zone.dragover {
      border-color: var(--accent-secondary);
      background: rgba(0, 212, 255, 0.03);
    }
    
    .drop-zone svg {
      width: 48px;
      height: 48px;
      stroke: var(--text-muted);
      fill: none;
      stroke-width: 1.5;
      margin-bottom: 16px;
    }
    
    .slice-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 24px;
    }
    
    .output-metrics-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-top: 20px;
    }
    
    .metric-card {
      background: rgba(5, 7, 12, 0.4);
      border: 1px solid var(--card-border);
      padding: 16px;
      border-radius: 12px;
      text-align: center;
    }
    
    .metric-val {
      font-size: 18px;
      font-weight: 700;
      color: var(--accent-secondary);
      margin-top: 6px;
    }
    
    .quote-summary {
      background: linear-gradient(135deg, rgba(112, 0, 255, 0.1), rgba(0, 212, 255, 0.1));
      border: 1px solid rgba(0, 212, 255, 0.2);
      border-radius: 16px;
      padding: 24px;
      margin-top: 24px;
    }
    
    .quote-row {
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      font-size: 15px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .quote-row.total {
      border-bottom: none;
      font-weight: 700;
      font-size: 20px;
      color: #fff;
      padding-top: 16px;
    }
    
    /* Inbox Tab */
    .inbox-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
      max-height: 400px;
      overflow-y: auto;
      padding-right: 8px;
    }
    
    .email-item {
      background: rgba(5, 7, 12, 0.3);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 16px 20px;
      cursor: pointer;
      display: flex;
      justify-content: space-between;
      align-items: center;
      transition: all 0.2s;
    }
    
    .email-item:hover {
      background: rgba(255, 255, 255, 0.04);
      border-color: rgba(255, 255, 255, 0.15);
    }
    
    .email-meta {
      flex: 1;
    }
    
    .email-sender {
      font-weight: 600;
      font-size: 15px;
      margin-bottom: 4px;
    }
    
    .email-subj {
      font-size: 14px;
      color: var(--text-main);
      margin-bottom: 6px;
    }
    
    .email-snippet {
      font-size: 13px;
      color: var(--text-muted);
    }
    
    .email-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    
    .attachment-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(0, 212, 255, 0.1);
      border: 1px solid rgba(0, 212, 255, 0.2);
      color: var(--accent-secondary);
      font-size: 11px;
      font-weight: 600;
      padding: 4px 8px;
      border-radius: 8px;
      text-transform: uppercase;
    }
    
    .email-detail-container {
      display: none;
      margin-top: 24px;
      border-top: 1px solid var(--card-border);
      padding-top: 24px;
    }
    
    .email-body-view {
      background: rgba(0, 0, 0, 0.2);
      padding: 20px;
      border-radius: 12px;
      border: 1px solid var(--card-border);
      font-size: 14px;
      line-height: 1.6;
      max-height: 200px;
      overflow-y: auto;
      margin-bottom: 20px;
      white-space: pre-wrap;
    }
    
    /* Toast alerts */
    .toast-box {
      position: fixed;
      bottom: 30px;
      right: 30px;
      z-index: 100;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    
    .toast {
      background: rgba(13, 20, 35, 0.95);
      border-left: 4px solid var(--accent-secondary);
      padding: 16px 24px;
      border-radius: 8px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
      color: #fff;
      font-size: 14px;
      font-weight: 500;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      animation: slide-in 0.3s cubic-bezier(0.18, 0.89, 0.32, 1.28);
    }
    
    @keyframes slide-in {
      from { transform: translateX(100%); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
  </style>
</head>
<body>

  <div class="app-container">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="brand">
        <div class="logo-orb"></div>
        <h2>Ricky AI</h2>
      </div>
      
      <nav class="nav-menu">
        <button class="nav-item active" id="nav-chat" onclick="showTab('chat')">
          <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
          <span>AI Assistant</span>
        </button>
        <button class="nav-item" id="nav-slicer" onclick="showTab('slicer')">
          <svg viewBox="0 0 24 24"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
          <span>3D Print Hub</span>
        </button>
        <button class="nav-item" id="nav-gmail" onclick="showTab('gmail')">
          <svg viewBox="0 0 24 24"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
          <span>Gmail Hub</span>
        </button>
        <button class="nav-item" id="nav-maps" onclick="showTab('maps')">
          <svg viewBox="0 0 24 24"><polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21"></polygon><line x1="9" y1="3" x2="9" y2="18"></line><line x1="15" y1="6" x2="15" y2="21"></line></svg>
          <span>Travel Center</span>
        </button>
        <button class="nav-item" id="nav-settings" onclick="showTab('settings')">
          <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
          <span>Settings</span>
        </button>
      </nav>
      
      <div class="sidebar-footer">
        <p>Ricky Workspace</p>
        <p style="opacity: 0.5; font-size: 10px; margin-top: 4px;">Google Hackathon 2026</p>
      </div>
    </aside>

    <!-- Main Viewport -->
    <main class="main-viewport">
      <!-- Top Header -->
      <header class="top-header">
        <h1 id="viewport-title">AI Assistant</h1>
        
        <div class="status-panel">
          <div class="status-badge">
            <div class="status-dot" id="status-dot"></div>
            <span id="status-text">Idle</span>
          </div>
        </div>
      </header>

      <!-- TAB: Chat -->
      <div class="tab-content active" id="tab-chat-view">
        <div class="chat-layout">
          <div class="chat-history" id="chat-history">
            <div class="chat-bubble ricky">
              Hello! I'm Ricky, your personal workspace assistant. I can help you review slicing metrics, estimate quotes, check inbox tasks, draft replies, and find routes. Feel free to type or use Voice mode!
            </div>
          </div>
          
          <div class="chat-input-row">
            <input type="text" id="chat-prompt" placeholder="Ask Ricky a question..." onkeydown="if(event.key==='Enter') sendChat()" />
            <div class="wave-canvas-container" id="wave-container">
              <canvas id="wave-canvas" width="120" height="40"></canvas>
            </div>
            <button class="voice-pulse-btn" id="voice-btn" onclick="toggleVoiceSpeech()" title="Voice Mode">
              <svg viewBox="0 0 24 24"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg>
            </button>
            <button class="btn" onclick="sendChat()">Send</button>
          </div>
        </div>
      </div>

      <!-- TAB: Slicer -->
      <div class="tab-content" id="tab-slicer-view">
        <div class="glass-card">
          <h3 style="margin-bottom: 15px;">Slicing & Estimator Hub</h3>
          <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 24px;">Upload a 3D model (.3mf or .stl) to calculate print times, parse G-code parameters, and generate an automated cost invoice.</p>
          
          <div class="drop-zone" id="drop-zone" onclick="document.getElementById('model-file-input').click()">
            <svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
            <h4 style="margin-bottom: 8px;">Drag & Drop 3D File Here</h4>
            <p style="color: var(--text-muted); font-size: 13px;">Supports .3mf or .stl (Max 25MB) or click to browse</p>
            <input type="file" id="model-file-input" style="display: none;" accept=".stl,.3mf" onchange="handleFileSelect(event)" />
          </div>
          
          <div id="file-info" style="display: none; margin-bottom: 20px; font-weight: 500; font-size: 14px; color: var(--accent-secondary);">
            Selected file: <span id="file-name-span"></span>
          </div>

          <div class="slice-grid">
            <div>
              <label>Material Filament</label>
              <select id="material-type">
                <option value="PLA" selected>PLA Filament ($0.10/100g)</option>
                <option value="PETG">PETG Filament ($0.20/100g)</option>
              </select>
            </div>
            <div>
              <label>Layer Height (mm)</label>
              <select id="layer-height">
                <option value="0.08">0.08mm (Extra Fine)</option>
                <option value="0.12">0.12mm (Fine)</option>
                <option value="0.20" selected>0.20mm (Standard)</option>
                <option value="0.28">0.28mm (Draft)</option>
              </select>
            </div>
          </div>
          
          <div class="slice-grid" style="margin-top: -10px;">
            <div>
              <label>Infill Density (%)</label>
              <input type="number" id="infill" value="20" min="5" max="100" />
            </div>
            <div>
              <label>Print Speed (mm/s)</label>
              <input type="number" id="print-speed" value="60" min="10" max="300" />
            </div>
          </div>
          
          <div style="margin-top: 10px; display: flex; justify-content: flex-end; padding-bottom: 20px;">
            <button class="btn" style="width: 100%;" onclick="uploadAndSliceModel()">Slice 3D Model</button>
          </div>
        </div>

        <div class="glass-card" id="metrics-card" style="display: none;">
          <h3>Slicing Results</h3>
          <div id="demo-mode-alert" style="display: none; background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.2); padding: 12px 18px; border-radius: 10px; color: #fbbf24; font-size: 13px; margin: 15px 0;">
            <strong>Demo Sandbox Mode:</strong> A mock slice was generated because no local slicing CLI path is set. Configure your slicer binary in the Settings tab to run actual slicing.
          </div>
          <div class="output-metrics-grid">
            <div class="metric-card">
              <label>Filament Weight</label>
              <div class="metric-val" id="m-weight">-- g</div>
            </div>
            <div class="metric-card">
              <label>Filament Volume</label>
              <div class="metric-val" id="m-volume">-- cc</div>
            </div>
            <div class="metric-card">
              <label>Filament Length</label>
              <div class="metric-val" id="m-length">-- mm</div>
            </div>
            <div class="metric-card">
              <label>Est. Print Time</label>
              <div class="metric-val" id="m-time">--</div>
            </div>
          </div>
          
          <div class="quote-summary">
            <h4 style="border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 12px; margin-bottom: 12px;">3D Cost Quote Breakdown</h4>
            <div class="quote-row">
              <span>Material Cost (<span id="q-material-type">PLA</span> at <span id="q-material-rate">$0.10/100g</span>)</span>
              <span id="q-material">$0.00</span>
            </div>
            <div class="quote-row">
              <span>Labor Cost ($5.00/hour)</span>
              <span id="q-labor">$0.00</span>
            </div>
            <div class="quote-row">
              <span>Flat Setup Rate</span>
              <span id="q-flat">$0.00</span>
            </div>
            <div class="quote-row total">
              <span>Estimated Quote Invoice</span>
              <span id="q-total">$0.00</span>
            </div>
          </div>
          
          <div style="margin-top: 24px; display: flex; gap: 14px;">
            <button class="btn btn-secondary" id="download-gcode-btn" onclick="downloadGcodeFile()">
              <svg viewBox="0 0 24 24" style="width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 2;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
              <span>Download G-code File</span>
            </button>
          </div>
        </div>
      </div>

      <!-- TAB: Gmail -->
      <div class="tab-content" id="tab-gmail-view">
        <div class="glass-card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h3>Connected Gmail Inbox</h3>
            <button class="btn btn-secondary" style="padding: 10px 18px; font-size: 13px;" onclick="refreshEmailsList()">Refresh Inbox</button>
          </div>
          
          <div class="inbox-list" id="inbox-list">
            <p style="color: var(--text-muted); text-align: center; padding: 40px 0;">Scanning mailbox... Make sure credentials are configured in Settings.</p>
          </div>
          
          <!-- Detailed view & reply template -->
          <div class="email-detail-container" id="email-detail-box">
            <h4 id="email-detail-subject" style="margin-bottom: 6px;">--</h4>
            <div style="display: flex; justify-content: space-between; font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">
              <span id="email-detail-sender">From: --</span>
              <span id="email-detail-date">--</span>
            </div>
            <div class="email-body-view" id="email-detail-body">--</div>
            
            <div class="glass-card" style="background: rgba(0,0,0,0.15); margin-bottom: 0;">
              <h4 style="margin-bottom: 15px;">Smart Email Composer</h4>
              <div class="slice-grid">
                <div>
                  <label>Select Draft Tone</label>
                  <select id="reply-tone">
                    <option value="professional">Professional / Polite</option>
                    <option value="casual">Friendly / Casual</option>
                    <option value="appreciative">Appreciative / Warm</option>
                  </select>
                </div>
                <div style="display: flex; align-items: flex-end; padding-bottom: 20px;">
                  <button class="btn" style="width: 100%;" onclick="generateEmailReplyDraft()">AI Draft Reply</button>
                </div>
              </div>
              
              <label>Draft Reply Content</label>
              <textarea id="reply-body-draft" rows="8" placeholder="Generated draft reply will appear here... You can edit this message before sending."></textarea>
              
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span id="smtp-status" style="font-size: 13px; color: var(--text-muted);">Ready to send.</span>
                <button class="btn" onclick="sendGmailReply()">Send Reply Email</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- TAB: Maps -->
      <div class="tab-content" id="tab-maps-view">
        <div class="glass-card">
          <h3 style="margin-bottom: 15px;">Travel Logistics Estimator</h3>
          <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 24px;">Integrate with the Google Maps Distance Matrix API to fetch distances and calculate transit estimates.</p>
          
          <div class="slice-grid">
            <div>
              <label>Origin Address</label>
              <input type="text" id="maps-origin" placeholder="e.g. 100 State St, Boston, MA" />
            </div>
            <div>
              <label>Destination Address</label>
              <input type="text" id="maps-destination" placeholder="e.g. Cambridge, MA" />
            </div>
          </div>
          
          <button class="btn" onclick="calculateTravelEstimates()">Calculate Travel Distance</button>
        </div>
        
        <div class="glass-card" id="travel-results-card" style="display: none;">
          <h3>Estimated Route</h3>
          <div style="display: flex; align-items: center; gap: 20px; margin-top: 20px;">
            <div style="flex-grow: 1; height: 4px; background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary)); position: relative; border-radius: 2px;">
              <div style="width: 12px; height: 12px; border-radius: 50%; background: #fff; position: absolute; left: 0; top: -4px;"></div>
              <div style="width: 12px; height: 12px; border-radius: 50%; background: #00d4ff; position: absolute; right: 0; top: -4px; box-shadow: 0 0 10px #00d4ff;"></div>
            </div>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 14px; color: var(--text-muted); margin-top: 10px;">
            <span id="travel-origin-lbl">Origin</span>
            <span id="travel-dest-lbl">Destination</span>
          </div>
          <div class="output-metrics-grid" style="margin-top: 30px;">
            <div class="metric-card" style="grid-column: span 2;">
              <label>Driving Distance</label>
              <div class="metric-val" id="travel-dist-val">-- km</div>
            </div>
            <div class="metric-card" style="grid-column: span 2;">
              <label>Estimated Duration</label>
              <div class="metric-val" id="travel-time-val">-- mins</div>
            </div>
          </div>
        </div>
      </div>

      <!-- TAB: Settings -->
      <div class="tab-content" id="tab-settings-view">
        <div class="glass-card">
          <h3 style="margin-bottom: 24px;">Workspace Configuration</h3>
          
          <div class="slice-grid">
            <div>
              <label>Google Gemini API Key</label>
              <input type="password" id="config-gemini" placeholder="Enter Gemini API key (AI Studio)" />
            </div>
            <div>
              <label>Google Maps API Key</label>
              <input type="password" id="config-maps" placeholder="Enter Google Maps API key" />
            </div>
          </div>

          <div class="slice-grid" style="margin-top: -10px;">
            <div>
              <label>Gmail SMTP / IMAP Email</label>
              <input type="text" id="config-email" placeholder="username@gmail.com" />
            </div>
            <div>
              <label>Gmail App Password</label>
              <input type="password" id="config-password" placeholder="16-character SMTP application code" />
            </div>
          </div>

          <div class="slice-grid" style="margin-top: -10px;">
            <div>
              <label>3D Slicer CLI Path (Optional)</label>
              <input type="text" id="config-slicer" placeholder="e.g. C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer.exe" />
            </div>
            <div>
              <label>Slicer Command Template (Optional)</label>
              <input type="text" id="config-template" placeholder="{exe} --load &quot;{input}&quot; --output &quot;{output}&quot; ..." />
            </div>
          </div>
          
          <div>
            <label>Default Origin Location</label>
            <input type="text" id="config-location" placeholder="e.g. Boston, MA" />
          </div>

          <button class="btn" onclick="saveConfiguration()">Test & Save Configuration</button>
        </div>
      </div>
    </main>
  </div>

  <!-- Toast Container -->
  <div class="toast-box" id="toast-box"></div>

  <!-- Javascript Logic -->
  <script>
    // Tab switching
    function showTab(tabId) {
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
      
      const pane = document.getElementById(`tab-${tabId}-view`);
      const btn = document.getElementById(`nav-${tabId}`);
      
      if(pane) pane.classList.add('active');
      if(btn) btn.classList.add('active');
      
      // Update header title
      const titleMap = {
        'chat': 'AI Assistant Workspace',
        'slicer': '3D Slicing & Quote Hub',
        'gmail': 'Gmail Communication Center',
        'maps': 'Logistics Distance Estimator',
        'settings': 'Workspace settings'
      };
      document.getElementById('viewport-title').textContent = titleMap[tabId] || 'Ricky Workspace';
      
      if (tabId === 'gmail') {
        refreshEmailsList();
      }
    }
    
    // Notifications system
    function notify(message, type='success') {
      const box = document.getElementById('toast-box');
      const toast = document.createElement('div');
      toast.className = 'toast';
      if(type === 'error') toast.style.borderLeftColor = '#ef4444';
      if(type === 'warning') toast.style.borderLeftColor = '#f59e0b';
      
      toast.innerHTML = `<span>${message}</span>`;
      box.appendChild(toast);
      
      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';
        toast.style.transition = 'all 0.4s';
        setTimeout(() => toast.remove(), 400);
      }, 4000);
    }

    // Server State Polling
    async function pollState() {
      try {
        const r = await fetch('/state');
        if(r.ok) {
          const j = await r.json();
          const state = j.state || 'idle';
          
          const dot = document.getElementById('status-dot');
          const txt = document.getElementById('status-text');
          
          dot.className = 'status-dot';
          if (state !== 'idle') dot.classList.add(state);
          txt.textContent = state.charAt(0).toUpperCase() + state.slice(1);
          
          if(state === 'listening') {
            startSoundWave();
          } else {
            stopSoundWave();
          }
        }
      } catch(e) {}
      setTimeout(pollState, 1000);
    }
    pollState();

    // Canvas Soundwave Animation
    const canvas = document.getElementById("wave-canvas");
    const ctx = canvas.getContext("2d");
    let waveId = null;
    let wavePhase = 0;
    
    function drawSoundwave() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.lineWidth = 1.5;
      
      // Main cyan wave
      ctx.strokeStyle = "rgba(0, 212, 255, 0.7)";
      ctx.beginPath();
      for (let x = 0; x < canvas.width; x++) {
        const y = canvas.height / 2 + 
                  Math.sin(x * 0.04 + wavePhase) * 12 * Math.sin(x * 0.008) +
                  Math.sin(x * 0.07 - wavePhase) * 4 * Math.sin(x * 0.005);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      
      // Purple secondary wave
      ctx.strokeStyle = "rgba(112, 0, 255, 0.5)";
      ctx.beginPath();
      for (let x = 0; x < canvas.width; x++) {
        const y = canvas.height / 2 + 
                  Math.sin(x * 0.03 - wavePhase) * 8 * Math.sin(x * 0.007) +
                  Math.sin(x * 0.08 + wavePhase) * 3 * Math.sin(x * 0.004);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      
      wavePhase += 0.12;
      waveId = requestAnimationFrame(drawSoundwave);
    }
    
    function startSoundWave() {
      document.getElementById('wave-container').classList.add('active');
      if (!waveId) drawSoundwave();
    }
    
    function stopSoundWave() {
      document.getElementById('wave-container').classList.remove('active');
      if (waveId) {
        cancelAnimationFrame(waveId);
        waveId = null;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
    }

    // AI Chat Panel
    async function sendChat() {
      const inp = document.getElementById('chat-prompt');
      const prompt = inp.value.strip ? inp.value.strip() : inp.value.trim();
      if(!prompt) return;
      
      inp.value = '';
      appendBubble(prompt, 'user');
      
      const resBubble = appendBubble('Thinking...', 'ricky');
      try {
        const r = await fetch('/generate', {
          method: 'POST',
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          body: new URLSearchParams({prompt})
        });
        const j = await r.json();
        resBubble.textContent = j.result || 'No response returned.';
      } catch(e) {
        resBubble.textContent = 'Failed to connect to assistant service: ' + e;
      }
      scrollToBottom();
    }
    
    function appendBubble(txt, sender) {
      const hist = document.getElementById('chat-history');
      const bubble = document.createElement('div');
      bubble.className = `chat-bubble ${sender}`;
      bubble.textContent = txt;
      hist.appendChild(bubble);
      scrollToBottom();
      return bubble;
    }
    
    function scrollToBottom() {
      const hist = document.getElementById('chat-history');
      hist.scrollTop = hist.scrollHeight;
    }

    // Native Web Speech API integration (Voice Input)
    let recognitionObj = null;
    function toggleVoiceSpeech() {
      const btn = document.getElementById('voice-btn');
      
      try {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
          notify("Voice Speech API is not supported in this browser. Try Chrome/Edge.", "error");
          return;
        }
        
        if (recognitionObj) {
          recognitionObj.stop();
          return;
        }
        
        recognitionObj = new SpeechRecognition();
        recognitionObj.lang = 'en-US';
        recognitionObj.interimResults = false;
        recognitionObj.maxAlternatives = 1;
        
        recognitionObj.onstart = function() {
          btn.classList.add('active');
          notify("Listening... Speak clearly into microphone.");
          startSoundWave();
          // Update status on server
          fetch('/state', {method:'POST', body:new URLSearchParams({state: 'listening'})}).catch(()=>{});
        };
        
        recognitionObj.onresult = function(evt) {
          const speechText = evt.results[0][0].transcript;
          document.getElementById('chat-prompt').value = speechText;
          sendChat();
        };
        
        recognitionObj.onerror = function(e) {
          notify("Speech Recognition Error: " + e.error, "error");
          btn.classList.remove('active');
          stopSoundWave();
          recognitionObj = null;
        };
        
        recognitionObj.onend = function() {
          btn.classList.remove('active');
          stopSoundWave();
          recognitionObj = null;
        };
        
        recognitionObj.start();
      } catch(exc) {
        notify("Voice recording initialization failed: " + exc, "error");
      }
    }

    // 3D Slicing Uploads
    let currentUploadedGcode = '';
    const dropZone = document.getElementById('drop-zone');
    
    ['dragenter', 'dragover'].forEach(eventName => {
      dropZone.addEventListener(eventName, e => {
        e.preventDefault();
        dropZone.classList.add('dragover');
      }, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
      dropZone.addEventListener(eventName, e => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
      }, false);
    });
    
    dropZone.addEventListener('drop', e => {
      const dt = e.dataTransfer;
      const files = dt.files;
      if(files.length) {
        document.getElementById('model-file-input').files = files;
        displaySelectedFileName(files[0].name);
      }
    });
    
    function handleFileSelect(e) {
      const files = e.target.files;
      if(files.length) {
        displaySelectedFileName(files[0].name);
      }
    }
    
    function displaySelectedFileName(name) {
      document.getElementById('file-info').style.display = 'block';
      document.getElementById('file-name-span').textContent = name;
      notify(`Model file selected: ${name}`);
    }
    
    async function uploadAndSliceModel() {
      const input = document.getElementById('model-file-input');
      if (!input.files || !input.files[0]) {
        notify("Please select or drop a 3D model file first.", "error");
        return;
      }
      
      const file = input.files[0];
      const materialType = document.getElementById('material-type').value;
      const layerHeight = document.getElementById('layer-height').value;
      const infill = document.getElementById('infill').value;
      const speed = document.getElementById('print-speed').value;
      
      notify("Uploading model and executing slicer... This may take a minute.", "warning");
      
      const fd = new FormData();
      fd.append('model_file', file);
      fd.append('material_type', materialType);
      fd.append('layer_height', layerHeight);
      fd.append('infill', infill);
      fd.append('print_speed', speed);
      
      try {
        const r = await fetch('/upload_model', {
          method: 'POST',
          body: fd
        });
        const j = await r.json();
        
        if (j.success) {
          notify("Model sliced successfully!");
          document.getElementById('metrics-card').style.display = 'block';
          
          if(j.is_mock) {
            document.getElementById('demo-mode-alert').style.display = 'block';
          } else {
            document.getElementById('demo-mode-alert').style.display = 'none';
          }
          
          // Render Metrics
          const m = j.metrics || {};
          document.getElementById('m-weight').textContent = (m.filament_weight_g !== undefined) ? `${m.filament_weight_g} g` : '-- g';
          document.getElementById('m-volume').textContent = (m.filament_volume_cc !== undefined) ? `${m.filament_volume_cc} cc` : '-- cc';
          document.getElementById('m-length').textContent = (m.filament_length_mm !== undefined) ? `${m.filament_length_mm} mm` : '-- mm';
          document.getElementById('m-time').textContent = m.print_time || 'Unknown';
          
          // Render Quote
          const q = j.quote || {};
          document.getElementById('q-material-type').textContent = q.material_type || 'PLA';
          document.getElementById('q-material-rate').textContent = q.material_type === 'PLA' ? '$0.10/100g' : '$0.20/100g';
          document.getElementById('q-material').textContent = `$${q.material_cost ? q.material_cost.toFixed(2) : '0.00'}`;
          document.getElementById('q-labor').textContent = `$${q.labor_cost ? q.labor_cost.toFixed(2) : '0.00'}`;
          document.getElementById('q-flat').textContent = `$${q.flat_rate ? q.flat_rate.toFixed(2) : '5.00'}`;
          document.getElementById('q-total').textContent = `$${q.total_quote ? q.total_quote.toFixed(2) : '0.00'}`;
          
          currentUploadedGcode = j.gcode_path || '';
        } else {
          notify("Slicing failed: " + (j.error || 'unknown server error'), "error");
        }
      } catch(e) {
        notify("Connection failed: " + e, "error");
      }
    }
    
    function downloadGcodeFile() {
      if(!currentUploadedGcode) {
        notify("No G-code is currently compiled.", "error");
        return;
      }
      const url = `/download_gcode?path=${encodeURIComponent(currentUploadedGcode)}`;
      window.open(url);
    }

    // Gmail Communications Hub
    let inboxEmailsList = [];
    async function refreshEmailsList() {
      const container = document.getElementById('inbox-list');
      container.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 40px 0;">Scanning mailbox... Please hold.</p>';
      
      try {
        const r = await fetch('/emails');
        const j = await r.json();
        
        if (j.error) {
          container.innerHTML = `<p style="color: #ef4444; text-align: center; padding: 40px 0;">${j.error}</p>`;
          return;
        }
        
        inboxEmailsList = j.emails || [];
        if (inboxEmailsList.length === 0) {
          container.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 40px 0;">Your inbox is empty.</p>';
          return;
        }
        
        container.innerHTML = '';
        inboxEmailsList.forEach(mail => {
          const item = document.createElement('div');
          item.className = 'email-item';
          item.onclick = () => selectEmailItem(mail.id);
          
          let attachHtml = '';
          if (mail.has_3d_attachment) {
            attachHtml = '<span class="attachment-badge">3D Model</span>';
          }
          
          item.innerHTML = `
            <div class="email-meta">
              <div class="email-sender">${escapeHtml(mail.from)}</div>
              <div class="email-subj">${escapeHtml(mail.subject)}</div>
              <div class="email-snippet">${escapeHtml(mail.snippet)}</div>
            </div>
            <div class="email-actions">
              ${attachHtml}
              <span style="font-size: 12px; color: var(--text-muted);">${formatDateShort(mail.date)}</span>
            </div>
          `;
          container.appendChild(item);
        });
        
        notify("Inbox loaded successfully.");
      } catch(e) {
        container.innerHTML = `<p style="color: #ef4444; text-align: center; padding: 40px 0;">Connection failure: ${e}</p>`;
      }
    }
    
    let activeSelectedEmail = null;
    function selectEmailItem(id) {
      const mail = inboxEmailsList.find(m => m.id === id);
      if(!mail) return;
      
      activeSelectedEmail = mail;
      document.getElementById('email-detail-box').style.display = 'block';
      document.getElementById('email-detail-subject').textContent = mail.subject;
      document.getElementById('email-detail-sender').textContent = `From: ${mail.from}`;
      document.getElementById('email-detail-date').textContent = mail.date;
      document.getElementById('email-detail-body').textContent = mail.body;
      
      // Clear composer draft
      document.getElementById('reply-body-draft').value = '';
      
      // Scroll to detail view
      document.getElementById('email-detail-box').scrollIntoView({ behavior: 'smooth' });
    }
    
    async function generateEmailReplyDraft() {
      if(!activeSelectedEmail) {
        notify("Select an email first.", "error");
        return;
      }
      
      const tone = document.getElementById('reply-tone').value;
      notify("Drafting AI reply proposal... Please wait.", "warning");
      
      try {
        const r = await fetch('/reply', {
          method: 'POST',
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          body: new URLSearchParams({
            subject: activeSelectedEmail.subject,
            body: activeSelectedEmail.body,
            tone: tone
          })
        });
        const j = await r.json();
        
        if(j.reply) {
          document.getElementById('reply-body-draft').value = j.reply;
          notify("Reply drafted successfully.");
        } else {
          notify("Failed to generate draft: " + (j.error || 'unknown error'), "error");
        }
      } catch(e) {
        notify("Draft failed: " + e, "error");
      }
    }
    
    async function sendGmailReply() {
      if(!activeSelectedEmail) return;
      const draft = document.getElementById('reply-body-draft').value;
      if(!draft.trim()) {
        notify("Draft is empty. Generate or type a message first.", "error");
        return;
      }
      
      const statusLbl = document.getElementById('smtp-status');
      statusLbl.textContent = 'Sending email...';
      notify("Sending SMTP email message...", "warning");
      
      try {
        const r = await fetch('/send_email', {
          method: 'POST',
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          body: new URLSearchParams({
            recipient: activeSelectedEmail.from.match(/<([^>]+)>/) ? activeSelectedEmail.from.match(/<([^>]+)>/)[1] : activeSelectedEmail.from,
            subject: `Re: ${activeSelectedEmail.subject}`,
            body: draft
          })
        });
        const j = await r.json();
        if(j.success) {
          statusLbl.textContent = 'Sent successfully!';
          notify("Email response dispatched successfully!");
          document.getElementById('reply-body-draft').value = '';
        } else {
          statusLbl.textContent = 'Delivery failed.';
          notify("Delivery failed: " + (j.error || 'unknown error'), "error");
        }
      } catch(e) {
        statusLbl.textContent = 'Delivery failed.';
        notify("SMTP connection error: " + e, "error");
      }
    }

    // Google Maps Travel Estimator
    async function calculateTravelEstimates() {
      const origin = document.getElementById('maps-origin').value;
      const dest = document.getElementById('maps-destination').value;
      
      if(!origin.trim() || !dest.trim()) {
        notify("Please enter both origin and destination.", "error");
        return;
      }
      
      notify("Calculating travel duration via Google Maps...", "warning");
      
      try {
        const r = await fetch('/travel', {
          method: 'POST',
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          body: new URLSearchParams({origin, destination: dest})
        });
        const j = await r.json();
        
        if (j.result && !j.result.includes("failed") && !j.result.includes("error")) {
          notify("Transit details fetched.");
          document.getElementById('travel-results-card').style.display = 'block';
          
          document.getElementById('travel-origin-lbl').textContent = origin;
          document.getElementById('travel-dest-lbl').textContent = dest;
          
          // Parse values (Distance: 12.3 km, Time: 25 mins)
          const distMatch = j.result.match(/distance:\s*([^,]+)/i);
          const timeMatch = j.result.match(/time:\s*([^.]+)/i) || j.result.match(/duration:\s*([^.]+)/i);
          
          document.getElementById('travel-dist-val').textContent = distMatch ? distMatch[1].trim() : j.result;
          document.getElementById('travel-time-val').textContent = timeMatch ? timeMatch[1].trim() : '--';
          
          document.getElementById('travel-results-card').scrollIntoView({ behavior: 'smooth' });
        } else {
          notify("Maps computation failed: " + (j.result || 'verify coordinates'), "error");
        }
      } catch(e) {
        notify("Maps query error: " + e, "error");
      }
    }

    // Settings Configuration Panel
    async function loadConfiguration() {
      try {
        const r = await fetch('/config');
        const j = await r.json();
        
        document.getElementById('config-gemini').value = j.gemini_key || '';
        document.getElementById('config-maps').value = j.maps_key || '';
        document.getElementById('config-email').value = j.gmail_email || '';
        document.getElementById('config-password').value = j.gmail_password || '';
        document.getElementById('config-slicer').value = j.slicer_path || '';
        document.getElementById('config-template').value = j.slicer_template || '';
        document.getElementById('config-location').value = j.default_location || '';
      } catch(e) {
        notify("Failed to load environment configuration: " + e, "error");
      }
    }
    loadConfiguration();

    async function saveConfiguration() {
      const gemini = document.getElementById('config-gemini').value;
      const maps = document.getElementById('config-maps').value;
      const email = document.getElementById('config-email').value;
      const pass = document.getElementById('config-password').value;
      const slicer = document.getElementById('config-slicer').value;
      const template = document.getElementById('config-template').value;
      const loc = document.getElementById('config-location').value;
      
      notify("Validating and writing configuration...", "warning");
      
      try {
        const r = await fetch('/config', {
          method: 'POST',
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          body: new URLSearchParams({
            gemini_key: gemini,
            maps_key: maps,
            gmail_email: email,
            gmail_password: pass,
            slicer_path: slicer,
            slicer_template: template,
            default_location: loc
          })
        });
        const j = await r.json();
        
        if(j.success) {
          notify("Configuration saved and reloaded successfully!");
          // Mask inputs after save
          loadConfiguration();
        } else {
          notify("Failed to save configuration: " + (j.message || 'unknown error'), "error");
        }
      } catch(e) {
        notify("Connection issue saving settings: " + e, "error");
      }
    }

    // Utilities
    function escapeHtml(text) {
      if(!text) return '';
      const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
      };
      return text.replace(/[&<>"']/g, function(m) { return map[m]; });
    }
    
    function formatDateShort(dateStr) {
      if(!dateStr) return '';
      try {
        const d = new Date(dateStr);
        if(isNaN(d.getTime())) return dateStr;
        return d.toLocaleDateString(undefined, {month:'short', day:'numeric'});
      } catch(e) {
        return dateStr;
      }
    }
  </script>
</body>
</html>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress console logging noise to focus on app operations

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path in ('/', '/index.html'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML.encode('utf-8'))
            return
            
        if parsed.path == '/state':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            payload = {'state': getattr(self.server, 'status', 'idle')}
            self.wfile.write(json.dumps(payload).encode('utf-8'))
            return
            
        if parsed.path == '/emails':
            assistant = getattr(self.server, 'assistant', None)
            if assistant:
                res = fetch_inbox_emails(assistant)
                self._json(res)
                return
            self._json({'error': 'No assistant active.'})
            return
            
        if parsed.path == '/config':
            assistant = getattr(self.server, 'assistant', None)
            if assistant:
                config_data = {
                    "gemini_key": mask_string(assistant.gemini_api_key or ""),
                    "maps_key": mask_string(assistant.google_maps_api_key or ""),
                    "gmail_email": assistant.gmail_email or "",
                    "gmail_password": mask_string(assistant.gmail_app_password or "", is_password=True),
                    "slicer_path": assistant.slicer_cli_path or "",
                    "slicer_template": assistant.slicer_command_template or "",
                    "default_location": assistant.default_location or ""
                }
                self._json(config_data)
                return
            self._json({'error': 'No assistant active.'})
            return

        if parsed.path == '/download_gcode':
            gcode_path = params.get('path', [''])[0]
            if gcode_path and os.path.exists(gcode_path) and gcode_path.lower().endswith('.gcode'):
                # Security sanity check: verify inside current directory to block arbitrary reads
                abs_gcode = os.path.abspath(gcode_path)
                abs_cwd = os.path.abspath(os.getcwd())
                if abs_gcode.startswith(abs_cwd) or "temp" in abs_gcode.lower() or "uploads" in abs_gcode.lower():
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/octet-stream')
                    self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(gcode_path)}"')
                    self.end_headers()
                    with open(gcode_path, 'rb') as f:
                        self.wfile.write(f.read())
                    return
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Access Denied or Invalid Path.")
            return
            
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        ctype = self.headers.get('Content-Type','')
        length = int(self.headers.get('Content-Length', 0))
        
        body = ''
        params = {}
        if 'application/x-www-form-urlencoded' in ctype:
            body = self.rfile.read(length).decode('utf-8') if length else ''
            params = urllib.parse.parse_qs(body)
            
        def get(k):
            v = params.get(k)
            return v[0] if v else ''

        try:
            if parsed.path == '/state':
                # Allow setting states directly from frontend (e.g. listening)
                state = get('state')
                if state:
                    self.server.status = state
                self._json({'success': True})
                return

            if parsed.path == '/generate':
                prompt = get('prompt')
                assistant = getattr(self.server, 'assistant', None)
                if assistant:
                    result = assistant.generate_response(prompt)
                    self._json({'result': result})
                    return
                self._json({'error': 'No assistant active.'})
                return

            if parsed.path == '/reply':
                subject = get('subject')
                body_text = get('body')
                tone = get('tone') or 'professional'
                assistant = getattr(self.server, 'assistant', None)
                if assistant:
                    reply = assistant.create_email_reply(subject, body_text, tone)
                    self._json({'reply': reply})
                    return
                self._json({'error': 'No assistant active.'})
                return

            if parsed.path == '/send_email':
                recipient = get('recipient')
                subject = get('subject')
                body_text = get('body')
                assistant = getattr(self.server, 'assistant', None)
                if assistant:
                    success = assistant.send_email(recipient, subject, body_text)
                    self._json({'success': success})
                    return
                self._json({'error': 'No assistant active.'})
                return

            if parsed.path == '/quote':
                vol = float(get('volume') or 0)
                hours = float(get('hours') or 1)
                material_type = get('material_type') or 'PLA'
                assistant = getattr(self.server, 'assistant', None)
                if assistant:
                    q = assistant.estimate_3d_print_quote(vol, material_type=material_type, print_time_hours=hours)
                    self._json(q)
                    return
                self._json({'error': 'No assistant active.'})
                return

            if parsed.path == '/travel':
                origin = get('origin')
                destination = get('destination')
                assistant = getattr(self.server, 'assistant', None)
                if assistant:
                    res = assistant.estimate_travel_time(origin, destination)
                    self._json({'result': res})
                    return
                self._json({'error': 'No assistant active.'})
                return

            if parsed.path == '/config':
                gemini_key = get('gemini_key')
                maps_key = get('maps_key')
                gmail_email = get('gmail_email')
                gmail_password = get('gmail_password')
                slicer_path = get('slicer_path')
                slicer_template = get('slicer_template')
                default_location = get('default_location')
                
                # Check for masked fields. If masked, keep existing values.
                assistant = getattr(self.server, 'assistant', None)
                if assistant:
                    if gemini_key.startswith("AIzaSy") and gemini_key.endswith("..."):
                        # Masked input, don't overwrite if it hasn't changed.
                        gemini_key = assistant.gemini_api_key or ""
                    elif gemini_key == "********" or (len(gemini_key) > 0 and "..." in gemini_key):
                        gemini_key = assistant.gemini_api_key or ""
                        
                    if maps_key.startswith("AIzaSy") and maps_key.endswith("..."):
                        maps_key = assistant.google_maps_api_key or ""
                    elif maps_key == "********" or (len(maps_key) > 0 and "..." in maps_key):
                        maps_key = assistant.google_maps_api_key or ""
                        
                    if gmail_password == "********":
                        gmail_password = assistant.gmail_app_password or ""

                # Write to .env file in root workspace
                env_content = f"""# Ricky Assistant Configuration
RICKY_GEMINI_API_KEY={gemini_key}
RICKY_GOOGLE_MAPS_API_KEY={maps_key}
RICKY_GMAIL_EMAIL={gmail_email}
RICKY_GMAIL_APP_PASSWORD={gmail_password}
RICKY_SLICER_CLI_PATH={slicer_path}
RICKY_SLICER_COMMAND_TEMPLATE={slicer_template}
RICKY_DEFAULT_LOCATION={default_location}
"""
                try:
                    with open(".env", "w", encoding="utf-8") as f:
                        f.write(env_content)
                    
                    if assistant:
                        # Force assistant to reload config instantly
                        assistant._load_env()
                        assistant.gemini_api_key = os.environ.get("RICKY_GEMINI_API_KEY")
                        assistant.google_maps_api_key = os.environ.get("RICKY_GOOGLE_MAPS_API_KEY")
                        assistant.gmail_app_password = os.environ.get("RICKY_GMAIL_APP_PASSWORD")
                        assistant.gmail_email = os.environ.get("RICKY_GMAIL_EMAIL")
                        assistant.slicer_cli_path = os.environ.get("RICKY_SLICER_CLI_PATH")
                        assistant.slicer_command_template = os.environ.get("RICKY_SLICER_COMMAND_TEMPLATE")
                        assistant.default_location = os.environ.get("RICKY_DEFAULT_LOCATION", "")
                    
                    self._json({"success": True, "message": "Settings saved and loaded."})
                except Exception as e:
                    self._json({"success": False, "message": f"Failed to write file: {e}"})
                return

            if parsed.path == '/upload_model':
                if 'multipart/form-data' in ctype:
                    fs = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={'REQUEST_METHOD':'POST', 'CONTENT_TYPE': ctype})
                    fileitem = fs['model_file'] if 'model_file' in fs else None
                    layer_height = float(fs.getvalue('layer_height', 0.2))
                    infill = int(fs.getvalue('infill', 20))
                    speed = int(fs.getvalue('print_speed', 60))
                    material_type = fs.getvalue('material_type', 'PLA')
                    
                    if fileitem is not None and fileitem.filename:
                        filename = os.path.basename(fileitem.filename)
                        uploads_dir = os.path.join(os.getcwd(), "uploads")
                        os.makedirs(uploads_dir, exist_ok=True)
                        model_path = os.path.join(uploads_dir, filename)
                        
                        # Write stream data
                        with open(model_path, "wb") as f:
                            f.write(fileitem.file.read())
                            
                        output_gcode = os.path.splitext(model_path)[0] + ".gcode"
                        
                        self.server.status = "slicing"
                        assistant = getattr(self.server, 'assistant', None)
                        
                        slicer_runs = True
                        if not assistant or not assistant.slicer_cli_path or not os.path.exists(assistant.slicer_cli_path):
                            slicer_runs = False
                            
                            # Fallback: create mock G-code estimates
                            file_size = os.path.getsize(model_path)
                            volume_cc = max(3.0, min(250.0, file_size / 20480.0))
                            print_time_hours = volume_cc * 0.12 * (0.2 / max(0.05, layer_height)) * (1.0 + (infill - 20) / 100.0)
                            print_time_hours = max(0.3, print_time_hours)
                            
                            hours = int(print_time_hours)
                            minutes = int((print_time_hours - hours) * 60)
                            print_time_str = f"{hours}h {minutes}m"
                            
                            filament_diameter = 1.75
                            filament_radius = filament_diameter / 2.0
                            filament_area_mm2 = math.pi * (filament_radius ** 2)
                            filament_mm = (volume_cc * 1000.0) / filament_area_mm2
                            
                            with open(output_gcode, "w", encoding="utf-8") as gcode_f:
                                gcode_f.write("; Mock G-code generated by Ricky Assistant Slicer Fallback\n")
                                gcode_f.write(f"; estimated print time = {print_time_str}\n")
                                gcode_f.write(f"; filament used = {filament_mm:.2f} mm\n")
                                gcode_f.write("; G1 F1200 E10\n")
                            
                            summary = f"Mock slicing completed. (Slicer binary not found at '{assistant.slicer_cli_path if assistant else 'not set'}')"
                        else:
                            # Run slicer binary
                            summary = assistant.slice_model(
                                model_path,
                                output_gcode,
                                layer_height=layer_height,
                                infill=infill,
                                print_speed=speed
                            )
                        
                        self.server.status = "idle"
                        
                        # Parse results
                        metrics = assistant.extract_gcode_metrics(output_gcode) if assistant else {}
                        
                        # Calculate quote
                        quote_res = None
                        if metrics and not metrics.get("error"):
                            vol = metrics["filament_volume_cc"]
                            hours_est = 1.0
                            pt = metrics.get("print_time", "")
                            if pt:
                                m_h = re.search(r"(\d+)\s*h", pt, re.I)
                                m_m = re.search(r"(\d+)\s*m", pt, re.I)
                                hours_val = float(m_h.group(1)) if m_h else 0.0
                                min_val = float(m_m.group(1)) if m_m else 0.0
                                hours_est = hours_val + (min_val / 60.0)
                                if hours_est == 0.0:
                                    hours_est = 1.0
                            if assistant:
                                quote_res = assistant.estimate_3d_print_quote(vol, material_type=material_type, print_time_hours=hours_est)
                        
                        self._json({
                            "success": True,
                            "summary": summary,
                            "gcode_path": output_gcode,
                            "metrics": metrics,
                            "quote": quote_res,
                            "is_mock": not slicer_runs
                        })
                        return
                self._json({"success": False, "error": "Invalid multipart data or upload error."})
                return

            if parsed.path == '/upload_audio':
                # Maintain compatibility with browser wav recording fallback
                if 'multipart/form-data' in ctype:
                    fs = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={'REQUEST_METHOD':'POST', 'CONTENT_TYPE': ctype})
                    fileitem = fs['audio'] if 'audio' in fs else None
                    if fileitem is not None:
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
                        try:
                            data = fileitem.file.read() if hasattr(fileitem.file, 'read') else fileitem.value
                            tmp.write(data)
                            tmp.close()
                            
                            try:
                                import speech_recognition as sr
                                r = sr.Recognizer()
                                with sr.AudioFile(tmp.name) as source:
                                    audio = r.record(source)
                                try:
                                    result = r.recognize_google(audio, show_all=True)
                                except Exception as exc:
                                    result = {'error': str(exc)}
                                
                                try:
                                    os.remove(tmp.name)
                                except Exception:
                                    pass
                                
                                transcript = ''
                                details = None
                                if isinstance(result, dict):
                                    details = result
                                    if 'alternative' in result:
                                        transcript = result['alternative'][0].get('transcript', '')
                                elif isinstance(result, str):
                                    transcript = result
                                
                                if transcript:
                                    self._json({'transcript': transcript})
                                else:
                                    self._json({'error': 'transcription_failed', 'details': details})
                                return
                            except ImportError:
                                try: os.remove(tmp.name)
                                except: pass
                                self._json({'error': 'speech_recognition_not_installed'})
                                return
                            except Exception as e:
                                try: os.remove(tmp.name)
                                except: pass
                                self._json({'error': str(e)})
                                return
                        except Exception as e:
                            self._json({'error': str(e)})
                            return
                self._json({'error': 'no audio file uploaded'})
                return

            # default
            self._json({'error': 'unknown path'})
        except Exception as exc:
            self._json({'error': str(exc)})

    def _json(self, obj):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode('utf-8'))


class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
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

def start_web_ui(assistant, open_browser=True):
    server = ThreadedServer(('127.0.0.1', 0), Handler)
    server.assistant = assistant
    server.status = 'idle'
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    if open_browser:
        open_in_chrome(f'http://127.0.0.1:{port}/')
    return server, port
