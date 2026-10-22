import streamlit as st
import sqlite3, hashlib, os, io, json, random, math
from datetime import date, time, datetime, timedelta
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import streamlit.components.v1 as components

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "event_on.db"

st.set_page_config(page_title="Event ON", page_icon="🎪", layout="wide", initial_sidebar_state="expanded")

# ---------- Persistence ----------
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, display_name TEXT NOT NULL, role TEXT DEFAULT '사용자', department TEXT DEFAULT '', company TEXT DEFAULT '')")
    conn.execute("CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, title TEXT NOT NULL, data TEXT NOT NULL, updated_at TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS settings (username TEXT PRIMARY KEY, data TEXT NOT NULL)")
    conn.commit()
    return conn

conn = db()
try:
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
except Exception:
    pass
def hash_pw(pw): return hashlib.sha256(pw.encode('utf-8')).hexdigest()
def get_user(username):
    return conn.execute("SELECT username, display_name, role, department, company FROM users WHERE username=?", (username,)).fetchone()
def get_settings(username):
    row = conn.execute("SELECT data FROM settings WHERE username=?", (username,)).fetchone()
    defaults = {"theme":"밝은 화면", "font":"보통", "report_style":"업무용 간결체", "detail":"상세 분석", "company":"", "logo_text":"", "report_author":""}
    if row:
        try: defaults.update(json.loads(row[0]))
        except Exception: pass
    return defaults
def save_settings(username, settings):
    conn.execute("INSERT INTO settings(username,data) VALUES(?,?) ON CONFLICT(username) DO UPDATE SET data=excluded.data", (username, json.dumps(settings, ensure_ascii=False)))
    conn.commit()
def save_project(username, data):
    title = data.get("name") or "이름 없는 행사"
    conn.execute("INSERT INTO projects(username,title,data,updated_at) VALUES(?,?,?,?)", (username,title,json.dumps(data,ensure_ascii=False,default=str),datetime.now().strftime('%Y-%m-%d %H:%M')))
    conn.commit()
def list_projects(username):
    return conn.execute("SELECT id,title,updated_at,data FROM projects WHERE username=? ORDER BY id DESC", (username,)).fetchall()

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

# ---------- Styling ----------
st.markdown("""<style>
:root { --eo-blue:#3157e8; --eo-ink:#172033; --eo-muted:#68748a; }
.block-container {padding-top:1.2rem; padding-bottom:3rem; max-width:1440px;}
[data-testid="stAppViewContainer"] {background:#f7f9fc;}
[data-testid="stSidebar"] {background:#fff;border-right:1px solid #e7ebf2;}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {color:#536078;}
.eo-muted {color:#68748a;font-size:.9rem}
.eo-card {border:1px solid #e6eaf2; border-radius:20px; padding:24px; min-height:175px; background:#fff; box-shadow:0 5px 20px rgba(27,45,94,.035);}
.eo-card h3 {margin-top:10px;color:#172033;font-size:1.18rem;}
.eo-card p {color:#68748a;line-height:1.65;}
.eo-hero {background:linear-gradient(115deg,#172b69 0%,#3157e8 58%,#7a8df5 100%);border-radius:26px;padding:36px 38px;color:white;margin:4px 0 24px 0;}
.eo-hero h1 {color:white;font-size:2.25rem;line-height:1.25;margin:0 0 12px 0;letter-spacing:-.04em;}
.eo-hero p {color:#e5eaff;font-size:1rem;line-height:1.7;margin-bottom:0;}
.eo-eyebrow {font-size:.75rem;font-weight:800;letter-spacing:.14em;color:#dce4ff;margin-bottom:14px;}
.eo-section {font-size:1.25rem;font-weight:750;color:#172033;margin:26px 0 6px 0;}
.eo-sub {font-size:.9rem;color:#778198;margin-bottom:18px;}
.eo-stat {background:#fff;border:1px solid #e6eaf2;border-radius:16px;padding:18px 20px;}
.eo-stat-label {font-size:.82rem;color:#778198;margin-bottom:8px;}
.eo-stat-value {font-size:1.5rem;font-weight:800;color:#172033;}
div.stButton > button {border-radius:11px;min-height:2.7rem;font-weight:650;border:1px solid #dce3ef;}
div.stButton > button[kind="primary"] {background:#3157e8;border-color:#3157e8;}
[data-testid="stForm"] {background:#fff;border:1px solid #e6eaf2;border-radius:16px;padding:20px;}
[data-testid="stExpander"] {border-color:#e3e8f1;border-radius:14px;}
h1,h2,h3 {letter-spacing:-.025em;}
</style>""", unsafe_allow_html=True)

if "page" not in st.session_state: st.session_state.page = "home"
if "user" not in st.session_state: st.session_state.user = None
if "event_data" not in st.session_state:
    st.session_state.event_data = {"name":"봄맞이 문화축제", "purpose":"지역 주민 참여와 문화 체험", "budget":10000000, "visitors":1200, "venue":"야외 축제장", "duration_days":1, "event_date":date.today()+timedelta(days=30), "start_time":time(10,0), "end_time":time(18,0), "mood":"활기찬", "age":"전 연령", "inside":"실외", "ticket":"무료", "ticket_price":0, "facilities":["공연장","푸드존","체험 부스","휴게 공간","응급의료센터","안내센터"], "extra":"입구에서 안내센터가 잘 보이도록 배치"}
