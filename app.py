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
:root { --eo-blue:#2563eb; }
.block-container {padding-top:1.4rem; padding-bottom:2rem; max-width:1500px;}
[data-testid="stSidebar"] {border-right:1px solid rgba(100,116,139,.18)}
.eo-muted {color:#64748b;font-size:.9rem}
.eo-card {border:1px solid rgba(100,116,139,.25); border-radius:18px; padding:20px; min-height:145px; background:linear-gradient(135deg,rgba(59,130,246,.06),rgba(255,255,255,.7));}
.eo-card h3 {margin-top:8px}
div.stButton > button {border-radius:10px;}
</style>""", unsafe_allow_html=True)

if "page" not in st.session_state: st.session_state.page = "home"
if "user" not in st.session_state: st.session_state.user = None
if "event_data" not in st.session_state:
    st.session_state.event_data = {"name":"봄맞이 문화축제", "purpose":"지역 주민 참여와 문화 체험", "budget":10000000, "visitors":1200, "venue":"야외 축제장", "duration_days":1, "event_date":date.today()+timedelta(days=30), "start_time":time(10,0), "end_time":time(18,0), "mood":"활기찬", "age":"전 연령", "inside":"실외", "ticket":"무료", "ticket_price":0, "facilities":["공연장","푸드존","체험 부스","휴게 공간","응급의료센터","안내센터"], "extra":"입구에서 안내센터가 잘 보이도록 배치"}
if "selected_zone" not in st.session_state: st.session_state.selected_zone = "공연장"
if "overrides" not in st.session_state: st.session_state.overrides = {}

# ---------- Layout drawing ----------
FACILITY_COLORS = {"공연장":"#dbeafe", "푸드존":"#ffedd5", "체험 부스":"#f3e8ff", "휴게 공간":"#dcfce7", "응급의료센터":"#fee2e2", "안내센터":"#fef9c3", "입구":"#e2e8f0", "출구":"#cbd5e1", "화장실":"#e0f2fe", "굿즈 판매":"#fce7f3"}
BASE_POS = {"공연장":(0.34,0.72), "푸드존":(0.76,0.65), "체험 부스":(0.23,0.43), "휴게 공간":(0.69,0.34), "응급의료센터":(0.84,0.22), "안내센터":(0.13,0.20), "입구":(0.49,0.06), "출구":(0.91,0.06), "화장실":(0.08,0.58), "굿즈 판매":(0.53,0.43)}
ALT_POS = {"전시장형": {"공연장":(0.50,0.78),"푸드존":(0.80,0.22),"체험 부스":(0.25,0.55),"휴게 공간":(0.25,0.25),"응급의료센터":(0.86,0.50),"안내센터":(0.10,0.10)}, "컨벤션·강연장형":{"공연장":(0.50,0.78),"푸드존":(0.82,0.20),"체험 부스":(0.25,0.52),"휴게 공간":(0.75,0.50),"응급의료센터":(0.10,0.24),"안내센터":(0.12,0.70)}, "공원·광장형":{"공연장":(0.50,0.78),"푸드존":(0.80,0.55),"체험 부스":(0.25,0.50),"휴게 공간":(0.70,0.28),"응급의료센터":(0.12,0.23),"안내센터":(0.12,0.70)}}
def positions(data):
    model = data.get("venue","야외 축제장")
    base = dict(BASE_POS)
    model_key = "전시장형" if "전시" in model else "컨벤션·강연장형" if ("컨벤션" in model or "강연" in model) else "공원·광장형" if ("공원" in model or "광장" in model) else None
    if model_key: base.update(ALT_POS[model_key])
    base.update(st.session_state.get("overrides",{}))
    return base

def make_layout_image(data, selected=None, path=None):
