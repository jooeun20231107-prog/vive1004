import streamlit as st
import sqlite3, hashlib, json, random, math, io
from datetime import date, time, datetime, timedelta
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "event_on.db"

st.set_page_config(page_title="Event ON", page_icon="🎪", layout="wide")

# -------------------- Database --------------------
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password_hash TEXT NOT NULL,
        display_name TEXT NOT NULL, role TEXT DEFAULT '사용자',
        department TEXT DEFAULT '', company TEXT DEFAULT '')""")
    conn.execute("""CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL,
        title TEXT NOT NULL, data TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    conn.execute("CREATE TABLE IF NOT EXISTS settings (username TEXT PRIMARY KEY, data TEXT NOT NULL)")
    conn.commit()
    return conn

conn = db()
try:
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
except Exception:
    pass

def hash_pw(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def get_user(username):
    return conn.execute(
        "SELECT username, display_name, role, department, company FROM users WHERE username=?",
        (username,)).fetchone()

def get_settings(username):
    defaults = {"theme":"밝은 화면", "font":"보통", "report_style":"업무용 간결체",
                "detail":"상세 분석", "company":"", "logo_text":"Event ON", "report_author":""}
    row = conn.execute("SELECT data FROM settings WHERE username=?", (username,)).fetchone()
    if row:
        try:
            defaults.update(json.loads(row[0]))
        except (ValueError, TypeError):
            pass
    return defaults

def save_settings(username, settings):
    conn.execute("""INSERT INTO settings(username,data) VALUES(?,?)
        ON CONFLICT(username) DO UPDATE SET data=excluded.data""",
        (username, json.dumps(settings, ensure_ascii=False)))
    conn.commit()

def save_project(username, data):
    title = str(data.get("name") or "이름 없는 행사")
    conn.execute("INSERT INTO projects(username,title,data,updated_at) VALUES(?,?,?,?)",
        (username, title, json.dumps(data, ensure_ascii=False, default=str),
         datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()

def list_projects(username):
    return conn.execute(
        "SELECT id,title,updated_at,data FROM projects WHERE username=? ORDER BY id DESC",
        (username,)).fetchall()

def decode_project_data(raw):
    data = json.loads(raw)
    if isinstance(data.get("event_date"), str):
        try: data["event_date"] = date.fromisoformat(data["event_date"])
        except ValueError: pass
    for key in ("start_time", "end_time"):
        if isinstance(data.get(key), str):
            try: data[key] = time.fromisoformat(data[key])
            except ValueError: pass
    return data

# -------------------- Style --------------------
st.markdown("""
<style>
:root { --eo-blue:#2563eb; }
.block-container {padding-top:1.2rem; padding-bottom:2rem; max-width:1500px;}
[data-testid="stSidebar"] {border-right:1px solid rgba(100,116,139,.18); background:#fbfdff;}
.eo-muted {color:#64748b;font-size:.9rem}
.eo-card {border:1px solid #e2e8f0;border-radius:18px;padding:18px;background:linear-gradient(135deg,#f8fbff,#fff);min-height:120px}
div.stButton > button {border-radius:10px;min-height:2.5rem}
