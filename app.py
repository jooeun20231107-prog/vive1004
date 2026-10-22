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
.block-container {padding-top:1.6rem; padding-bottom:2rem; max-width:1500px; overflow-wrap:anywhere;}
[data-testid="stSidebar"] {border-right:1px solid rgba(100,116,139,.18)}
.eo-muted {color:#64748b;font-size:.9rem}
.eo-card {border:1px solid rgba(100,116,139,.25); border-radius:18px; padding:22px; min-height:205px; height:100%; background:linear-gradient(135deg,rgba(59,130,246,.07),rgba(255,255,255,.85)); box-sizing:border-box; display:flex; flex-direction:column;}
.eo-card h3 {margin-top:8px; margin-bottom:10px; line-height:1.35; min-height:2.7em;}
.eo-card p {line-height:1.6; margin-bottom:0;}
.eo-home-title {font-size:clamp(1.55rem, 3vw, 2.25rem); font-weight:750; line-height:1.3; letter-spacing:-.035em; overflow-wrap:anywhere; word-break:keep-all; margin:0 0 .45rem 0;}
.eo-home-subtitle {font-size:1rem; line-height:1.7; color:#64748b; margin-bottom:1.25rem;}
@media (max-width: 700px) { .eo-card {min-height:0;} .eo-card h3 {min-height:0;} }
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
    """행사장 모형의 기본 위치에 저장된 배치 좌표를 덮어쓴다."""
    model = data.get("venue","야외 축제장")
    base = dict(BASE_POS)
    model_key = "전시장형" if "전시" in model else "컨벤션·강연장형" if ("컨벤션" in model or "강연" in model) else "공원·광장형" if ("공원" in model or "광장" in model) else None
    if model_key: base.update(ALT_POS[model_key])
    saved = data.get("layout_positions", {}) or {}
    base.update(saved)
    # 이전 프로젝트 호환: 아직 저장 좌표가 없는 경우에만 세션 값을 사용한다.
    if not saved:
        base.update(st.session_state.get("overrides",{}))
    return base

def make_layout_image(data, selected=None, path=None):
    """행사장 형태를 반영한 2D 배치도. 대시보드와 PDF가 같은 저장 좌표를 사용한다."""
    try:
        from matplotlib import font_manager
        available = {f.name for f in font_manager.fontManager.ttflist}
        for f in ("NanumGothic", "NanumSquare", "Noto Sans CJK KR"):
            if f in available:
                plt.rcParams["font.family"] = f
                break
        plt.rcParams["axes.unicode_minus"] = False
    except Exception:
        pass

    fig, ax = plt.subplots(figsize=(12, 7.4), dpi=160)
    fig.patch.set_facecolor("#f8fafc")
    ax.set_facecolor("#f8fafc")
    shape_name = data.get("venue_shape", "직사각형 (기본)")
    # normalized canvas: x 0..100, y 0..60; shape geometry drives both boundary and usable area.
    if shape_name == "정사각형":
        outline = [(20, 2), (80, 2), (80, 58), (20, 58)]
    elif shape_name == "원형 광장":
        outline = [(50 + 29*math.cos(2*math.pi*i/100), 30 + 27*math.sin(2*math.pi*i/100)) for i in range(100)]
    elif shape_name == "돔형 (지붕 있음)":
        outline = [(50 + 29*math.cos(2*math.pi*i/100), 30 + 27*math.sin(2*math.pi*i/100)) for i in range(100)]
    elif shape_name == "타원형 경기장":
        outline = [(50 + 43*math.cos(2*math.pi*i/100), 30 + 26*math.sin(2*math.pi*i/100)) for i in range(100)]
    elif shape_name == "L자형":
        outline = [(5, 2), (57, 2), (57, 25), (95, 25), (95, 58), (5, 58)]
    else:
        outline = [(5, 2), (95, 2), (95, 58), (5, 58)]
    from matplotlib.patches import Polygon, Circle
    floor = Polygon(outline, closed=True, facecolor="#edf4fb", edgecolor="#64748b", linewidth=2.2, zorder=1)
    ax.add_patch(floor)
    # Light grid clipped to venue boundary
    for x in range(10, 100, 5):
        ln=ax.plot([x,x],[0,60],color="#dbe5f0",lw=.55,zorder=1)[0]; ln.set_clip_path(floor)
    for y in range(5, 60, 5):
        ln=ax.plot([0,100],[y,y],color="#dbe5f0",lw=.55,zorder=1)[0]; ln.set_clip_path(floor)
    # Primary and cross circulation corridors
    path_lines = [([8,92],[30,30]), ([50,50],[5,55])]
    for xs,ys in path_lines:
        ln=ax.plot(xs,ys,color="#c3d9ee",lw=7,solid_capstyle="round",zorder=2)[0]; ln.set_clip_path(floor)
        ln=ax.plot(xs,ys,color="#ffffff",lw=1.8,ls=(0,(3,4)),zorder=3)[0]; ln.set_clip_path(floor)
    # Optional secondary paths to each facility, linked to the central walkway.
    pos=positions(data)
    facilities=list(data.get("facilities", []))
    default_colors={**FACILITY_COLORS,"응급의료센터":"#fecaca"}
    for i,name in enumerate(facilities):
        nx,ny=pos.get(name,(.15+(i%4)*.2,.25+(i//4)*.25))
        x=min(91,max(9,float(nx)*90+5)); y=min(54,max(7,float(ny)*50+5))
        # L-shaped connector is a visual guide, not a verified pedestrian route.
        ax.plot([x,x,50],[y,30,30],color="#94a3b8",lw=.8,alpha=.7,ls="--",zorder=3)
        w,h=(13,8.2) if name=="공연장" else ((10.5,7.2) if name in ("체험 부스","푸드존") else (9,6.4))
        col=default_colors.get(name,"#dbeafe")
        patch=Polygon([(x-w/2,y-h/2),(x+w/2,y-h/2),(x+w/2,y+h/2),(x-w/2,y+h/2)],closed=True,
                      facecolor=("#93c5fd" if selected==name else col),edgecolor=("#1d4ed8" if selected==name else "#64748b"),
                      linewidth=2.2 if selected==name else 1.0,zorder=5)
        ax.add_patch(patch)
        ax.text(x,y,name,ha="center",va="center",fontsize=8.2,fontweight="bold",color="#172b45",zorder=6,wrap=True)
        if selected==name:
            ax.add_patch(Circle((x+w/2,y+h/2),1.25,facecolor="#2563eb",edgecolor="white",lw=1,zorder=7))
    # Entrance and exit positions are displayed on the lower boundary.
    ax.scatter([38,62],[3.5,3.5],s=95,c=["#16a34a","#ea580c"],edgecolors="white",linewidths=1.5,zorder=8)
    ax.text(38,6.5,"입구",ha="center",va="bottom",fontsize=8,fontweight="bold",color="#15803d",zorder=8)
    ax.text(62,6.5,"출구",ha="center",va="bottom",fontsize=8,fontweight="bold",color="#c2410c",zorder=8)
    if shape_name == "돔형 (지붕 있음)":
        ax.text(50,53,"돔 지붕 범위",ha="center",va="center",fontsize=9,color="#64748b",alpha=.9,zorder=4)
    ax.set_title(f"{data.get('name','행사장')} | {data.get('venue','행사장')} · {shape_name}",fontsize=15,fontweight="bold",color="#14243a",pad=16)
    ax.text(.01,-.04,"개념 설계도 · 저장된 시설 좌표 반영 · 실제 치수/비상 동선은 현장 검토 필요",transform=ax.transAxes,fontsize=8,color="#64748b")
    ax.set_xlim(0,100); ax.set_ylim(0,60); ax.set_aspect("equal"); ax.axis("off")
    plt.tight_layout(pad=1.2)
    if path:
        fig.savefig(path,bbox_inches="tight",facecolor=fig.get_facecolor()); plt.close(fig); return path
    buf=io.BytesIO(); fig.savefig(buf,format="png",bbox_inches="tight",facecolor=fig.get_facecolor()); plt.close(fig); buf.seek(0); return buf

def ai_explanation(zone, data):
    visitors=int(data.get('visitors',0)); fac=data.get('facilities',[])
    reasons={
      "공연장":"공연장은 행사장의 주요 목적 시설이므로 시야가 트이는 중심 또는 안쪽에 배치해 관객이 무대를 찾기 쉽게 하고, 관람 대기열이 입구를 막지 않도록 동선과 분리하는 것이 좋습니다.",
      "푸드존":"푸드존은 체류 시간이 길고 대기열이 생기기 쉬워 주 통행로에서 한 걸음 떨어진 가장자리 쪽에 두면 줄이 다른 부스의 이동을 방해할 가능성을 줄일 수 있습니다.",
      "체험 부스":"체험 부스는 여러 곳을 순서대로 둘러볼 수 있도록 통행로와 가까운 구역에 배치하면 접근성이 좋아집니다. 부스 사이에는 대기와 회전 공간을 확보하는 것이 중요합니다.",
      "휴게 공간":"휴게 공간은 활동량이 많은 구역과 가까우면서도 주 동선에서 약간 벗어난 곳에 두면 쉬려는 방문객이 흐름을 막지 않고 이용할 수 있습니다.",
      "응급의료센터":"응급의료센터는 행사장 어느 구역에서도 접근하기 쉽고 구조 인력이 진입할 수 있는 통로와 연결되는 위치가 적합합니다. 실제 운영 전에는 현장 안전 담당자가 접근로와 기준을 확인해야 합니다.",
      "안내센터":"안내센터는 입구에서 쉽게 보이는 위치에 배치하면 방문객이 행사장에 들어온 직후 정보를 얻고 목적지를 찾기 쉽습니다.",
      "굿즈 판매":"굿즈 판매는 관람객이 자연스럽게 들를 수 있는 동선 주변에 두되, 결제 대기열이 주요 통행로를 막지 않도록 별도 대기 공간을 확보하는 것이 좋습니다.",
      "화장실":"화장실은 여러 구역에서 찾기 쉬운 위치에 두고 안내 표지를 배치하는 것이 좋습니다. 실제 급배수와 접근성 조건은 현장 확인이 필요합니다."
    }
    base=reasons.get(zone, f'{zone}은(는) 방문객이 쉽게 찾고 안전하게 이용할 수 있도록 주요 동선과 연결하되 통행 흐름을 방해하지 않는 위치가 적합합니다.')
    return f"**AI 배치 분석 — {zone}**\n\n{base}\n\n**행사 조건 반영**\n- 예상 방문객: {visitors:,}명\n- 행사 분위기: {data.get('mood','미지정')}\n- 예상 연령대: {data.get('age','미지정')}\n- 검토 포인트: 접근성, 대기열, 시설 간 동선, 비상 접근로\n\n이 내용은 입력된 행사 조건을 바탕으로 한 설계 제안이며, 최종 배치는 실제 장소 치수와 안전 기준을 확인한 뒤 확정해야 합니다."

# ---------- AI demand forecast + meaningful crowd simulation ----------
def forecast_visitors(data):
    """규칙 기반 수요 추정. 학습된 ML 모델이 아닌 초기 추정치임을 명시한다."""
    facilities = list(data.get("facilities", [])) or ["공연장", "푸드존", "체험 부스"]
    visitors = max(1, int(data.get("visitors", 1000)))
    mood, age = data.get("mood", "활기찬"), data.get("age", "전 연령")
    weights = {}
    for name in facilities:
        w = {"공연장": 1.6 if mood in ("활기찬", "감성적인") else 1.25,
             "체험 부스": 1.55 if age in ("어린이", "청소년", "전 연령") else 1.15,
             "푸드존": 1.35, "휴게 공간": 0.8 if mood == "활기찬" else 1.15,
             "굿즈 판매": 1.1, "안내센터": .45, "화장실": .65, "응급의료센터": .08}.get(name, 1.0)
        if age == "고령층" and name == "휴게 공간": w *= 1.35
        if age == "어린이" and name == "체험 부스": w *= 1.2
        weights[name] = w
    total = sum(weights.values()) or 1
    rows = [{"name": n, "share": weights[n]/total, "visits": round(visitors*weights[n]/total)} for n in facilities]
    duration = max(1, int(data.get("duration_days", 1)))
    start, end = data.get("start_time", time(10, 0)), data.get("end_time", time(18, 0))
    sh = start.hour if hasattr(start, "hour") else 10
    eh = end.hour if hasattr(end, "hour") else 18
    return {"rows": rows, "visitors": visitors, "peak_occupancy": round(visitors*(.28 if duration == 1 else .18)),
            "peak_hour": min(max(sh+1, 12), max(sh+1, eh-1)),
            "assumption": "시설별 선호도 가중치와 행사 조건을 사용한 규칙 기반 추정이며 실제 행사 기록으로 학습한 모델은 아닙니다."}

def crowd_widget(data):
    pos = positions(data)
    palette = {"공연장":"#8b5cf6", "푸드존":"#f59e0b", "체험 부스":"#3b82f6", "휴게 공간":"#10b981", "응급의료센터":"#ef4444", "안내센터":"#0ea5e9", "화장실":"#06b6d4", "굿즈 판매":"#ec4899"}
    zones=[]
    for i,name in enumerate(data.get("facilities", []) or ["공연장", "푸드존", "체험 부스"]):
        nx,ny=pos.get(name,(.15+(i%4)*.2,.25+(i//4)*.25))
        zones.append({"name":name,"x":round(80+nx*820),"y":round(45+(1-ny)*430),"w":105 if name in ("공연장","체험 부스") else 85,"h":58,"color":palette.get(name,"#64748b")})
    payload={"zones":zones,"visitors":int(data.get("visitors",1000)),"forecast":forecast_visitors(data),"shape":data.get("venue_shape","직사각형 (기본)"),"venue":data.get("venue","야외 축제장")}
    html = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script><style>
    *{box-sizing:border-box}body{margin:0;background:#f8fafc;color:#0f172a;font-family:Arial,'Malgun Gothic',sans-serif}.bar{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:8px}.bar button{border:1px solid #cbd5e1;border-radius:9px;padding:8px 12px;background:#fff;color:#334155;font-weight:700;cursor:pointer}.bar button.on{background:#2563eb;color:#fff}.card{border:1px solid #dbe3ef;border-radius:13px;background:#fff;padding:11px}.head{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:8px;font-size:13px;font-weight:800}.badge{background:#eff6ff;color:#1d4ed8;border-radius:20px;padding:4px 9px;font-size:11px}.vp{position:relative;height:360px;border-radius:10px;overflow:hidden;background:linear-gradient(#dbeafe,#f8fafc)}#scene,#map{position:absolute;inset:0;width:100%;height:100%}#map{display:none}.hint{position:absolute;right:8px;top:8px;background:#0f172acc;color:#fff;border-radius:7px;padding:5px 8px;font-size:10px}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:9px}.stat{background:#f8fafc;border:1px solid #e2e8f0;border-radius:9px;padding:9px;font-size:11px;color:#64748b}.stat b{display:block;color:#0f172a;font-size:16px;margin-top:3px}.note{font-size:10px;color:#64748b;line-height:1.5;margin-top:8px}@media(max-width:600px){.vp{height:290px}.stats{grid-template-columns:1fr 1fr}}</style></head><body>
    <div class="bar"><button id="v3" class="on" onclick="view3(true)">🧊 3D 입체 설계도</button><button id="v2" onclick="view3(false)">🗺️ 2D 평면도</button><button id="play" onclick="running=!running;this.textContent=running?'⏸ 이동 시뮬레이션 정지':'▶ 이동 시뮬레이션 시작'">⏸ 이동 시뮬레이션 정지</button><button onclick="reset()">↻ 다시 시작</button></div>
    <div class="card"><div class="head"><span>🎪 방문객 목적 기반 이동 시뮬레이션</span><span class="badge" id="crowd"></span></div><div class="vp"><div id="scene"></div><canvas id="map"></canvas><div class="hint" id="hint">드래그: 3D 회전 · 휠: 확대/축소</div></div><div class="stats"><div class="stat">예상 총 방문객<b id="total"></b></div><div class="stat">예상 피크 체류 인원<b id="peak"></b></div><div class="stat">예상 혼잡 시간대<b id="hour"></b></div></div><div class="note" id="note"></div></div>
    <script>
    const D=__DATA__,el=document.getElementById('scene'),map=document.getElementById('map'),ctx=map.getContext('2d');let is3=true,running=true,renderer,scene,camera,agents=[],meshes=[],yaw=.55,pitch=.72,zoom=1,drag=false,lx=0,ly=0;const W=1000,H=550;
    total.textContent=D.visitors.toLocaleString()+'명';peak.textContent=D.forecast.peak_occupancy.toLocaleString()+'명';hour.textContent=D.forecast.peak_hour+':00 전후';note.textContent='예측: '+D.forecast.assumption+' 화면 속 사람은 전체 방문객을 축소한 시뮬레이션 인원입니다.';
    function choose(){let zs=D.zones.filter(z=>!['응급의료센터','안내센터','화장실'].includes(z.name));if(!zs.length)zs=D.zones;let ws=zs.map(z=>Math.max(.05,(D.forecast.rows.find(r=>r.name===z.name)||{share:.1}).share));let n=Math.random()*ws.reduce((a,b)=>a+b,0);for(let i=0;i<zs.length;i++){n-=ws[i];if(n<=0)return zs[i]}return zs[0]}
    function go(a,z){let t={x:z.x+z.w/2,y:z.y+z.h/2};a.dest=z;a.path=[{x:500,y:530},{x:500,y:Math.min(500,Math.max(80,t.y))},t];a.pi=0;a.tx=a.path[0].x;a.ty=a.path[0].y}
    function spawn(a){a.x=490+Math.random()*20;a.y=520+Math.random()*10;a.visits=0;a.dwell=0;a.speed=.5+Math.random()*.5;a.leaving=false;go(a,choose())}
    function reset(){agents=[];for(let i=0;i<Math.min(90,Math.max(28,Math.round(D.visitors/18)));i++){let a={};spawn(a);agents.push(a)}if(scene)buildPeople()}
    function step(){if(!running)return;agents.forEach(a=>{if(a.dwell>0){a.dwell--;return}let dx=a.tx-a.x,dy=a.ty-a.y,d=Math.hypot(dx,dy);if(d<5){if(a.pi<a.path.length-1){a.pi++;a.tx=a.path[a.pi].x;a.ty=a.path[a.pi].y}else if(a.leaving){spawn(a)}else{a.visits++;a.dwell=(a.dest.name==='푸드존'?85:a.dest.name==='공연장'?95:a.dest.name==='체험 부스'?75:40)+Math.random()*35;if(a.visits>=2&&Math.random()<.38){a.leaving=true;a.path=[{x:a.x,y:a.y},{x:950,y:530}];a.pi=0;a.tx=950;a.ty=530}else go(a,choose())}}else{a.x+=dx/d*a.speed;a.y+=dy/d*a.speed}})}
    function boundaryPoints(){const s=D.shape||'직사각형 (기본)';if(s==='정사각형')return [[200,20],[800,20],[800,530],[200,530]];if(s==='원형 광장'||s==='돔형 (지붕 있음)')return Array.from({length:100},(_,i)=>[500+290*Math.cos(i*Math.PI*2/100),275+250*Math.sin(i*Math.PI*2/100)]);if(s==='타원형 경기장')return Array.from({length:100},(_,i)=>[500+430*Math.cos(i*Math.PI*2/100),275+245*Math.sin(i*Math.PI*2/100)]);if(s==='L자형')return [[50,530],[570,530],[570,300],[950,300],[950,20],[50,20]];return [[50,20],[950,20],[950,530],[50,530]]}
    function draw2(){let r=map.getBoundingClientRect();if(!r.width)return;let dpr=devicePixelRatio||1;if(map.width!==Math.round(r.width*dpr)||map.height!==Math.round(r.height*dpr)){map.width=r.width*dpr;map.height=r.height*dpr}ctx.setTransform(dpr,0,0,dpr,0,0);let sx=r.width/W,sy=r.height/H;ctx.fillStyle='#f8fafc';ctx.fillRect(0,0,r.width,r.height);const bp=boundaryPoints().map(p=>[p[0]*sx,p[1]*sy]);ctx.beginPath();bp.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.closePath();ctx.fillStyle='#edf4fb';ctx.fill();ctx.save();ctx.clip();ctx.strokeStyle='#d6e2ef';ctx.lineWidth=1;for(let x=0;x<W;x+=50){ctx.beginPath();ctx.moveTo(x*sx,0);ctx.lineTo(x*sx,r.height);ctx.stroke()}for(let y=0;y<H;y+=50){ctx.beginPath();ctx.moveTo(0,y*sy);ctx.lineTo(r.width,y*sy);ctx.stroke()}ctx.lineCap='round';ctx.strokeStyle='#c3d9ee';ctx.lineWidth=15;ctx.beginPath();ctx.moveTo(500*sx,520*sy);ctx.lineTo(500*sx,35*sy);ctx.moveTo(70*sx,280*sy);ctx.lineTo(930*sx,280*sy);ctx.stroke();ctx.strokeStyle='#fff';ctx.lineWidth=4;ctx.stroke();ctx.setLineDash([7,7]);ctx.strokeStyle='#94a3b8';ctx.lineWidth=1.3;D.zones.forEach(z=>{let cx=(z.x+z.w/2)*sx,cy=(z.y+z.h/2)*sy;ctx.beginPath();ctx.moveTo(cx,cy);ctx.lineTo(cx,280*sy);ctx.lineTo(500*sx,280*sy);ctx.stroke()});ctx.setLineDash([]);D.zones.forEach(z=>{let x=z.x*sx,y=z.y*sy,w=z.w*sx,h=z.h*sy;ctx.fillStyle=z.color;ctx.fillRect(x,y,w,h);ctx.strokeStyle='#fff';ctx.lineWidth=2;ctx.strokeRect(x,y,w,h);ctx.fillStyle='#172b45';ctx.font='bold 11px Arial';ctx.textAlign='center';ctx.fillText(z.name,x+w/2,y+h/2+4,w-4)});ctx.restore();ctx.beginPath();bp.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.closePath();ctx.strokeStyle='#64748b';ctx.lineWidth=2.5;ctx.stroke();[[380,520,'입구','#16a34a'],[620,520,'출구','#ea580c']].forEach(g=>{ctx.fillStyle=g[3];ctx.beginPath();ctx.arc(g[0]*sx,g[1]*sy,7,0,Math.PI*2);ctx.fill();ctx.fillStyle='#0f172a';ctx.font='bold 11px Arial';ctx.fillText(g[2],g[0]*sx,g[1]*sy-11)});agents.forEach(a=>{ctx.fillStyle='#2563eb';ctx.beginPath();ctx.arc(a.x*sx,a.y*sy,3.5,0,Math.PI*2);ctx.fill()})}
    function box(w,h,d,c,x,y,z){let m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),new THREE.MeshStandardMaterial({color:c,roughness:.8}));m.position.set(x,y,z);scene.add(m);return m}
    function buildPeople(){meshes.forEach(m=>scene.remove(m));meshes=[];agents.forEach(()=>{let m=new THREE.Mesh(new THREE.SphereGeometry(4,8,8),new THREE.MeshStandardMaterial({color:'#2563eb'}));scene.add(m);meshes.push(m)})}
    function build3(){scene.clear();scene.add(new THREE.HemisphereLight(0xffffff,0x94a3b8,2));let l=new THREE.DirectionalLight(0xffffff,1.1);l.position.set(-100,180,100);scene.add(l);const s=D.shape||'직사각형 (기본)';let pts;if(s==='정사각형')pts=[[200,20],[800,20],[800,530],[200,530]];else if(s==='원형 광장'||s==='돔형 (지붕 있음)')pts=Array.from({length:80},(_,i)=>[500+290*Math.cos(i*Math.PI*2/80),275+250*Math.sin(i*Math.PI*2/80)]);else if(s==='타원형 경기장')pts=Array.from({length:80},(_,i)=>[500+430*Math.cos(i*Math.PI*2/80),275+245*Math.sin(i*Math.PI*2/80)]);else if(s==='L자형')pts=[[50,530],[570,530],[570,300],[950,300],[950,20],[50,20]];else pts=[[50,20],[950,20],[950,530],[50,530]];const sh=new THREE.Shape();pts.forEach((p,i)=>{const x=p[0]-500,z=p[1]-275;if(i===0)sh.moveTo(x,z);else sh.lineTo(x,z)});sh.closePath();const floor=new THREE.Mesh(new THREE.ShapeGeometry(sh),new THREE.MeshStandardMaterial({color:'#dbe5ef',side:THREE.DoubleSide,roughness:.9}));floor.rotation.x=-Math.PI/2;floor.position.y=-2;scene.add(floor);const edgePts=pts.map(p=>new THREE.Vector3(p[0]-500,0,p[1]-275));edgePts.push(edgePts[0]);const edge=new THREE.Line(new THREE.BufferGeometry().setFromPoints(edgePts),new THREE.LineBasicMaterial({color:'#64748b'}));scene.add(edge);box(18,1,450,'#c3d9ee',0,0,0);box(800,1,18,'#c3d9ee',0,0,0);D.zones.forEach(z=>{let x=z.x-500+z.w/2,zz=z.y-275+z.h/2;box(z.w,4,z.h,z.color,x,1,zz);box(z.w*.85,12,z.h*.8,z.color,x,8,zz)});box(22,10,22,'#16a34a',-120,5,245);box(22,10,22,'#ea580c',120,5,245);if(s==='돔형 (지붕 있음)'){const roof=new THREE.Mesh(new THREE.SphereGeometry(260,32,12,0,Math.PI*2,0,Math.PI/2),new THREE.MeshBasicMaterial({color:'#94a3b8',wireframe:true,transparent:true,opacity:.35,side:THREE.DoubleSide}));roof.scale.set(1.1,.55,.95);roof.position.set(0,80,0);scene.add(roof)}buildPeople()}
    function init3(){try{renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});el.innerHTML='';el.appendChild(renderer.domElement);renderer.setPixelRatio(Math.min(2,devicePixelRatio||1));scene=new THREE.Scene();scene.background=new THREE.Color('#eaf3fc');camera=new THREE.PerspectiveCamera(42,1,.1,3000);build3();let c=renderer.domElement;c.onpointerdown=e=>{drag=true;lx=e.clientX;ly=e.clientY;c.setPointerCapture(e.pointerId)};c.onpointerup=()=>drag=false;c.onpointermove=e=>{if(drag){yaw-=(e.clientX-lx)*.008;pitch=Math.max(.25,Math.min(1.25,pitch+(e.clientY-ly)*.006));lx=e.clientX;ly=e.clientY}};c.onwheel=e=>{e.preventDefault();zoom=Math.max(.65,Math.min(1.8,zoom*(e.deltaY<0?1.08:.92)))};return true}catch(e){return false}}
    function draw3(){if(!renderer)return;let w=el.clientWidth,h=el.clientHeight;if(!w||!h)return;renderer.setSize(w,h,false);camera.aspect=w/h;camera.position.set(Math.sin(yaw)*900/zoom,620/zoom,Math.cos(yaw)*900/zoom);camera.lookAt(0,0,0);camera.updateProjectionMatrix();agents.forEach((a,i)=>{if(meshes[i])meshes[i].position.set(a.x-500,3,a.y-275)});renderer.render(scene,camera)}
    function view3(v){is3=v;v3.classList.toggle('on',v);v2.classList.toggle('on',!v);el.style.display=v?'block':'none';map.style.display=v?'none':'block';hint.style.display=v?'block':'none';if(!v)draw2()}function loop(){step();if(is3)draw3();else draw2();crowd.textContent='목적지 기반 이동 · '+agents.length+'명 표시';requestAnimationFrame(loop)}
    reset();if(!init3())view3(false);else{build3();view3(true)}window.addEventListener('resize',()=>{if(renderer)renderer.setSize(el.clientWidth,el.clientHeight);draw2()});requestAnimationFrame(loop);
    </script></body></html>'''
    html = html.replace("__DATA__", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"))
    components.html(html, height=475, scrolling=False)

# ---------- Auth ----------
def auth_screen():
    st.markdown("# Event ON")
    st.caption("AI 행사 설계 및 보고 플랫폼")
    a,b=st.columns(2, gap="large")
    with a:
        st.subheader("로그인")
        st.caption("아이디와 비밀번호를 입력해 주세요.")
        with st.form("login_form"):
            un=st.text_input("아이디", key="login_user")
            pw=st.text_input("비밀번호",type="password",key="login_pw")
            ok=st.form_submit_button("로그인",use_container_width=True)
        if ok:
            row=conn.execute("SELECT password_hash FROM users WHERE username=?",(un.strip(),)).fetchone()
            if row and row[0]==hash_pw(pw): st.session_state.user=un.strip(); st.session_state.page="home"; st.rerun()
            else: st.error("아이디 또는 비밀번호를 확인해 주세요.")
    with b:
        st.subheader("회원가입")
        st.caption("필수 정보를 입력해 새 계정을 만들어 주세요.")
        with st.form("signup_form"):
            name=st.text_input("이름", placeholder="홍길동")
            newun=st.text_input("아이디", placeholder="영문·숫자 조합")
            newpw=st.text_input("비밀번호",type="password",placeholder="4자 이상")
            ok2=st.form_submit_button("간편 회원가입",use_container_width=True)
        if ok2:
            if not name.strip() or not newun.strip() or len(newpw)<4: st.error("이름과 아이디를 입력하고 비밀번호는 4자 이상으로 설정해 주세요.")
            elif conn.execute("SELECT 1 FROM users WHERE username=?",(newun.strip(),)).fetchone(): st.error("이미 사용 중인 아이디입니다.")
            else:
                conn.execute("INSERT INTO users(username,password_hash,display_name,role,department,company) VALUES(?,?,?,?,?,?)",(newun.strip(),hash_pw(newpw),name.strip(),"사용자","", "")); conn.commit()
                st.success("가입이 완료됐어요! 직급과 회사 정보는 설정에서 나중에 입력할 수 있어요.")
    st.info("데모 버전은 SQLite에 계정과 프로젝트를 저장합니다. Streamlit Cloud에서는 재배포 시 로컬 파일이 초기화될 수 있으므로 장기 운영 시 외부 데이터베이스를 연결하세요.")

# ---------- Sidebar ----------
if not st.session_state.user:
    auth_screen(); st.stop()
user=get_user(st.session_state.user)
if not user:
    st.session_state.user=None; st.rerun()
username, display_name, role, department, company = user
settings=get_settings(username)
if settings.get("theme")=="어두운 화면":
    st.markdown("<style>.stApp{background:#111827;color:#f8fafc}.eo-card{background:#1f2937}</style>",unsafe_allow_html=True)
with st.sidebar:
    if st.button("🎪 Event ON",use_container_width=True): st.session_state.page="home"; st.rerun()
    st.caption("AI EVENT DESIGN PLATFORM")
    st.divider()
    if st.button("🏠  홈",use_container_width=True): st.session_state.page="home"; st.rerun()
    if st.button("🧩  대시보드",use_container_width=True): st.session_state.page="dashboard"; st.rerun()
    if st.button("📄  AI 보고서",use_container_width=True): st.session_state.page="report"; st.rerun()
    st.write("")
    st.write("")
    if st.button("⚙️  설정",use_container_width=True): st.session_state.page="settings"; st.rerun()
    st.markdown(f"**👤 {display_name} ({role})님**")
    if department: st.caption(department)
    if st.button("로그아웃",use_container_width=True): st.session_state.user=None; st.session_state.page="home"; st.rerun()

# ---------- Home ----------
if st.session_state.page=="home":
    st.markdown('<div class="eo-home-title">행사 기획을 더 똑똑하게, Event ON</div>',unsafe_allow_html=True)
    st.markdown('<div class="eo-home-subtitle">행사 정보를 입력하고, 공간을 설계하고, 보고서까지 한 번에 준비하세요.</div>',unsafe_allow_html=True)
    c1,c2=st.columns(2,gap="large")
    with c1:
        st.markdown('<div class="eo-card"><div style="font-size:34px">🧩</div><h3>행사 설계 대시보드</h3><p>기본정보를 입력하고 행사장 배치와 방문객 이동을 시뮬레이션하세요.</p></div>',unsafe_allow_html=True)
        if st.button("대시보드 들어가기 →",key="go_dash",use_container_width=True): st.session_state.page="dashboard"; st.rerun()
    with c2:
        st.markdown('<div class="eo-card"><div style="font-size:34px">📄</div><h3>AI 보고서</h3><p>최종 배치도와 분석 결과가 포함된 업무용 보고서를 생성하고 PDF로 저장하세요.</p></div>',unsafe_allow_html=True)
        if st.button("AI 보고서 열기 →",key="go_report",use_container_width=True): st.session_state.page="report"; st.rerun()
    st.write("")
    st.subheader("최근 저장한 행사")
    projects=list_projects(username)
    if projects:
        for pid,title,updated,data_json in projects[:3]:
            with st.container(border=True):
                cc1,cc2=st.columns([4,1]); cc1.markdown(f"**{title}**  \n<small>{updated}</small>",unsafe_allow_html=True)
                if cc2.button("불러오기",key=f"loadhome{pid}"):
                    st.session_state.event_data=decode_project_data(data_json); st.session_state.page="dashboard"; st.rerun()
    else: st.caption("아직 저장된 행사가 없어요. 대시보드에서 첫 행사를 설계해 보세요.")

# ---------- Dashboard ----------
elif st.session_state.page=="dashboard":
    st.title("행사 설계 대시보드")
    st.caption("기본정보를 입력하면 행사장 배치도와 AI 분석이 업데이트됩니다.")
    data=st.session_state.event_data
    with st.expander("✏️ 행사 기본정보 입력 / 수정",expanded=not st.session_state.get("data_confirmed",False)):
        with st.form("event_form"):
            c1,c2=st.columns(2)
            with c1:
                name=st.text_input("행사명",data.get("name","")); purpose=st.text_area("행사 목적",data.get("purpose",""),height=75)
                budget=st.number_input("예산 (원)",min_value=0,value=int(data.get("budget",0)),step=100000)
                visitors=st.number_input("예상 방문객 수 (명)",min_value=1,value=int(data.get("visitors",1000)),step=50)
                venue=st.selectbox("행사장 모형 선택",["야외 축제장","실내 전시장형","컨벤션·강연장형","공원·광장형","실내 공연장형"],index=["야외 축제장","실내 전시장형","컨벤션·강연장형","공원·광장형","실내 공연장형"].index(data.get("venue","야외 축제장")) if data.get("venue") in ["야외 축제장","실내 전시장형","컨벤션·강연장형","공원·광장형","실내 공연장형"] else 0)
                shape_options=["직사각형 (기본)","정사각형","원형 광장","돔형 (지붕 있음)","타원형 경기장","L자형"]
                venue_shape=st.selectbox("행사장 형태",shape_options,index=shape_options.index(data.get("venue_shape","직사각형 (기본)")) if data.get("venue_shape","직사각형 (기본)") in shape_options else 0,help="선택한 형태가 디지털 트윈 바닥 모양에 반영됩니다.")
                event_date=st.date_input("행사 날짜",value=data.get("event_date",date.today()+timedelta(days=30)))
                duration=st.number_input("진행 일수",min_value=1,max_value=365,value=int(data.get("duration_days",1)))
            with c2:
                start=st.time_input("하루 운영 시작",value=data.get("start_time",time(10,0))); end=st.time_input("하루 운영 종료",value=data.get("end_time",time(18,0)))
                mood=st.selectbox("원하는 분위기",["활기찬","감성적인","전문적인","가족 친화적인","차분한","미래지향적인"],index=["활기찬","감성적인","전문적인","가족 친화적인","차분한","미래지향적인"].index(data.get("mood","활기찬")) if data.get("mood") in ["활기찬","감성적인","전문적인","가족 친화적인","차분한","미래지향적인"] else 0)
                age=st.selectbox("예상 연령대",["어린이","청소년","성인","고령층","전 연령"],index=["어린이","청소년","성인","고령층","전 연령"].index(data.get("age","전 연령")) if data.get("age") in ["어린이","청소년","성인","고령층","전 연령"] else 4)
                inside=st.selectbox("실내·실외 여부",["실내","실외","실내·실외 혼합"],index=["실내","실외","실내·실외 혼합"].index(data.get("inside","실외")) if data.get("inside") in ["실내","실외","실내·실외 혼합"] else 1)
                ticket=st.selectbox("입장료",["무료","유료"],index=0 if data.get("ticket","무료")=="무료" else 1)
                ticket_price=st.number_input("유료 입장료 (원)",min_value=0,value=int(data.get("ticket_price",0)),step=1000,disabled=ticket=="무료")
            facility_opts=["공연장","푸드존","체험 부스","휴게 공간","응급의료센터","안내센터","화장실","굿즈 판매"]
            facilities=st.multiselect("필요한 부스 및 시설 (복수 선택)",facility_opts,default=[x for x in data.get("facilities",facility_opts[:6]) if x in facility_opts])
            extra=st.text_area("추가 요청 사항",data.get("extra",""),placeholder="예: 입구에서 안내센터가 잘 보이게, 응급의료센터 진입로 확보")
            submitted=st.form_submit_button("정보 저장하고 배치도 업데이트",use_container_width=True)
        if submitted:
            if end<=start: st.error("운영 종료 시간은 시작 시간보다 늦어야 합니다.")
            elif not facilities: st.error("부스 또는 시설을 하나 이상 선택해 주세요.")
            else:
                previous=st.session_state.event_data
                # 시설 목록 변경 시 기존 좌표는 유지하고, 새 시설에는 기본 위치를 사용한다.
                saved_positions=dict(previous.get("layout_positions", {}) or {})
                st.session_state.event_data={"name":name,"purpose":purpose,"budget":budget,"visitors":visitors,"venue":venue,"venue_shape":venue_shape,"event_date":event_date,"duration_days":duration,"start_time":start,"end_time":end,"mood":mood,"age":age,"inside":inside,"ticket":ticket,"ticket_price":ticket_price if ticket=="유료" else 0,"facilities":facilities,"extra":extra,"layout_positions":saved_positions}
                st.session_state.overrides={}; st.session_state.data_confirmed=True; st.success("행사 정보와 디지털 트윈 배치 설정이 업데이트됐어요."); st.rerun()
    data=st.session_state.event_data
    left,right=st.columns([1.55,1],gap="large")
    with left:
        st.markdown("#### AI 방문 수요 예측 · 디지털 트윈")
        crowd_widget(data)
        forecast = forecast_visitors(data)
        st.markdown("#### 시설별 예상 방문 수요")
        st.caption("시설 선호도·연령대·행사 분위기를 반영한 초기 추정치입니다. 실제 행사 기록으로 학습한 예측값은 아닙니다.")
        for row in sorted(forecast["rows"], key=lambda r: r["visits"], reverse=True):
            st.write(f"**{row['name']}** · 약 {row['visits']:,}회 방문 수요 · {row['share']*100:.0f}%")
            st.progress(min(1.0, row["share"]))
        st.markdown("#### 행사장 배치도 미리보기")
        st.image(make_layout_image(data,st.session_state.selected_zone),use_container_width=True)
        st.caption("디지털 트윈의 3D/2D 이동 경로는 시설 위치와 수요 가중치를 바탕으로 한 시뮬레이션입니다. 실제 공간 치수·통로 폭·방문객 이동 기록을 연결하면 예측을 검증하고 개선할 수 있습니다.")
    with right:
        st.markdown("#### AI 배치 분석")
        facilities=data.get("facilities",[])
        if not facilities: facilities=["공연장","푸드존","체험 부스"]
        if st.session_state.selected_zone not in facilities: st.session_state.selected_zone=facilities[0]
        zone=st.selectbox("분석할 부스 이름",facilities,index=facilities.index(st.session_state.selected_zone),key="zone_select")
        st.session_state.selected_zone=zone
        st.markdown(ai_explanation(zone,data))
        st.divider()
        st.markdown("#### AI 배치 수정")
        st.caption("시설을 선택한 뒤 가로·세로 좌표를 직접 조정하세요. 저장하면 2D 배치도, 3D 디지털 트윈, PDF 보고서에 같은 위치가 반영됩니다.")
        move_zone=st.selectbox("이동할 시설",facilities,key="move_zone")
        current_positions=positions(data)
        old_x,old_y=current_positions.get(move_zone,(.5,.5))
        sx,sy=st.columns(2)
        with sx:
            move_x=st.slider("가로 위치",min_value=5,max_value=95,value=int(max(5,min(95,old_x*100))),step=1,format="%d%%",key=f"move_x_{move_zone}")
        with sy:
            move_y=st.slider("세로 위치",min_value=8,max_value=92,value=int(max(8,min(92,old_y*100))),step=1,format="%d%%",key=f"move_y_{move_zone}")
        st.caption("좌표는 행사장 내부의 상대 위치(%)입니다. L자형·원형 등 가장자리 근처에서는 시설이 경계에 가까워질 수 있으니 배치도를 확인하세요.")
        if st.button("📍 좌표 적용 및 배치 저장",use_container_width=True):
            current=dict(st.session_state.event_data)
            saved=dict(current.get("layout_positions", {}) or {})
            saved[move_zone]=(move_x/100,move_y/100)
            current["layout_positions"]=saved
            st.session_state.event_data=current
            st.session_state.overrides={}
            save_project(username,current)
            st.success(f"{move_zone} 좌표를 적용하고 현재 프로젝트에 저장했어요.")
            st.rerun()
        if st.button("AI 추천 배치로 초기화",use_container_width=True):
            current=dict(st.session_state.event_data); current["layout_positions"]={}
            st.session_state.event_data=current; st.session_state.overrides={}
            save_project(username,current); st.success("추천 배치를 초기화하고 저장했어요."); st.rerun()
        st.divider()
        if st.button("💾 행사 프로젝트 저장",use_container_width=True): save_project(username,st.session_state.event_data); st.success("현재 행사 정보가 저장됐어요.")
        if st.button("📄 이 설계로 보고서 만들기",use_container_width=True): st.session_state.page="report"; st.rerun()

# ---------- Report ----------
elif st.session_state.page=="report":
    st.title("AI 행사 설계 보고서")
    st.caption("대시보드의 행사 정보와 현재 배치도를 바탕으로 업무용 보고서를 생성합니다.")
    data=st.session_state.event_data
    settings=get_settings(username)
    st.subheader("보고서 미리보기")
    st.markdown(f"### {data.get('name','행사')} 설계 및 운영 계획 보고서")
    st.caption(f"작성자: {settings.get('report_author') or display_name} · 작성일: {date.today().isoformat()} · 회사: {settings.get('company') or company or '미입력'}")
    st.markdown("**1. 행사 개요**")
    st.write(f"행사 목적: {data.get('purpose') or '미입력'}")
    st.write(f"일정: {data.get('event_date',date.today())} / {data.get('duration_days',1)}일 / {data.get('start_time')}–{data.get('end_time')}")
    st.write(f"장소 유형: {data.get('venue')} ({data.get('inside')}) · 예상 방문객: {int(data.get('visitors',0)):,}명 · 예산: {int(data.get('budget',0)):,}원")
    ticket_display = "무료" if data.get("ticket") == "무료" else "유료 {:,}원".format(int(data.get("ticket_price", 0)))
    st.write(f"입장료: {ticket_display} · 분위기: {data.get('mood')} · 대상: {data.get('age')}")
    st.markdown("**2. 행사장 배치도**")
    layout_img=make_layout_image(data)
    st.image(layout_img,use_container_width=True)
    st.markdown("**3. 주요 시설 배치 근거**")
    for f in data.get("facilities",[]):
        with st.expander(f): st.write(ai_explanation(f,data))
    st.markdown("**4. 동선 및 혼잡도 분석**")
    st.write(f"예상 방문객 {int(data.get('visitors',0)):,}명을 기준으로 입구와 주요 시설 간 이동 동선을 검토했습니다. 방문객이 집중될 수 있는 공연장과 푸드존 주변은 대기 공간을 별도로 확보하고, 응급의료센터로 이어지는 접근 통로를 막지 않도록 운영 계획을 마련해야 합니다.")
    st.caption("혼잡도 화면은 현재 시뮬레이션 예시이며, 실제 센서 데이터에 기반한 실측값은 아닙니다.")
    st.markdown("**5. 예산 및 운영 계획**")
    st.write(f"총 계획 예산은 {int(data.get('budget',0)):,}원입니다. 시설 설치, 안전관리, 안내 인력, 전기·통신, 청소 및 폐기물 처리 항목별로 세부 견적을 확인한 뒤 예산을 확정해야 합니다.")
    st.markdown("**6. 종합 의견 및 제안**")
    st.write(f"본 배치안은 '{data.get('mood')}' 분위기와 '{data.get('age')}' 연령대를 고려한 초기 제안입니다. 실제 행사장 치수, 피난 경로, 소방·전기 설비, 접근성 및 현장 운영 조건을 검토한 후 최종 확정하는 것을 권고합니다. 추가 요청 사항: {data.get('extra') or '없음'}")
    if st.button("PDF 보고서 생성",type="primary",use_container_width=True):
        try:
            pdf_buf=io.BytesIO(); doc=SimpleDocTemplate(pdf_buf,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=17*mm,bottomMargin=17*mm)
            styles=getSampleStyleSheet(); styles.add(ParagraphStyle(name='KTitle',parent=styles['Title'],fontName='HYSMyeongJo-Medium',fontSize=18,leading=23,textColor=colors.HexColor('#1d4ed8'),spaceAfter=8)); styles.add(ParagraphStyle(name='KBody',parent=styles['BodyText'],fontName='HYSMyeongJo-Medium',fontSize=9.5,leading=14,spaceAfter=5)); styles.add(ParagraphStyle(name='KHead',parent=styles['Heading2'],fontName='HYSMyeongJo-Medium',fontSize=12,leading=16,textColor=colors.HexColor('#1e40af'),spaceBefore=10,spaceAfter=5))
            story=[Paragraph((settings.get('company') or company or 'Event ON')+" · 행사 기획 보고서",styles['KBody']),Paragraph((data.get('name') or '행사')+' 설계 및 운영 계획 보고서',styles['KTitle']),Paragraph(f"작성자: {settings.get('report_author') or display_name}　|　작성일: {date.today().isoformat()}",styles['KBody']),Spacer(1,4*mm)]
            story.append(Paragraph('1. 행사 개요',styles['KHead']))
            overview=[["항목","내용"],["행사 목적",data.get('purpose') or '미입력'],["일정",f"{data.get('event_date')} / {data.get('duration_days')}일 / {data.get('start_time')}–{data.get('end_time')}"],["장소",f"{data.get('venue')} ({data.get('inside')})"],["예상 방문객",f"{int(data.get('visitors',0)):,}명"],["예산",f"{int(data.get('budget',0)):,}원"],["입장료",'무료' if data.get('ticket')=='무료' else f"유료 {int(data.get('ticket_price',0)):,}원"],["분위기·대상",f"{data.get('mood')} / {data.get('age')}"]]
            tbl=Table(overview,colWidths=[32*mm,145*mm],repeatRows=1); tbl.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dbeafe')),('TEXTCOLOR',(0,0),(-1,0),colors.HexColor('#1e3a8a')),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#cbd5e1')),('VALIGN',(0,0),(-1,-1),'TOP'),('FONTSIZE',(0,0),(-1,-1),8.5),('FONTNAME',(0,0),(-1,-1),'HYSMyeongJo-Medium'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)])); story += [tbl,Paragraph('2. 행사장 배치도',styles['KHead'])]
            img_path=APP_DIR/'report_layout.png'; make_layout_image(data,path=img_path); story.append(RLImage(str(img_path),width=174*mm,height=104*mm))
            story.append(Paragraph('3. 주요 시설 배치 근거',styles['KHead']))
            for f in data.get('facilities',[]): story.append(Paragraph(f'<b>{f}</b> — '+ai_explanation(f,data).replace('**','').replace('\n',' '),styles['KBody']))
            story.append(Paragraph('4. 동선 및 혼잡도 분석',styles['KHead'])); story.append(Paragraph(f"예상 방문객 {int(data.get('visitors',0)):,}명을 기준으로 입구와 주요 시설 간 이동 동선을 검토했습니다. 공연장과 푸드존 주변은 대기 공간을 별도로 확보하고 응급의료센터 접근 통로를 막지 않도록 운영해야 합니다. 혼잡도 화면은 시뮬레이션 예시이며 실제 센서 기반 측정값은 아닙니다.",styles['KBody']))
            story.append(Paragraph('5. 예산 및 운영 계획',styles['KHead'])); story.append(Paragraph(f"총 계획 예산은 {int(data.get('budget',0)):,}원입니다. 시설 설치, 안전관리, 안내 인력, 전기·통신, 청소 및 폐기물 처리 항목별 세부 견적을 확인한 후 예산을 확정해야 합니다.",styles['KBody']))
            story.append(Paragraph('6. 종합 의견 및 제안',styles['KHead'])); story.append(Paragraph(f"본 배치안은 {data.get('mood')} 분위기와 {data.get('age')} 연령대를 고려한 초기 제안입니다. 실제 행사장 치수, 피난 경로, 소방·전기 설비, 접근성 및 현장 운영 조건을 확인한 뒤 최종 확정해야 합니다. 추가 요청: {data.get('extra') or '없음'}",styles['KBody']))
            story.append(Spacer(1,5*mm)); story.append(Paragraph('※ 본 보고서는 제공된 입력값을 바탕으로 생성한 기획 초안입니다. 현장 실측 및 안전 전문가의 검토를 대체하지 않습니다.',styles['Italic']))
            doc.build(story); pdf_buf.seek(0); st.download_button("⬇️ PDF 다운로드",data=pdf_buf.getvalue(),file_name="Event_ON_행사설계_보고서.pdf",mime="application/pdf",use_container_width=True)
        except Exception as e: st.error(f"PDF 생성 중 오류가 발생했습니다: {e}")
    if st.button("현재 행사 저장",use_container_width=True): save_project(username,data); st.success("행사 프로젝트가 저장됐어요.")

# ---------- Settings ----------
elif st.session_state.page=="settings":
    st.title("설정")
    st.caption("Event ON 사용 환경과 계정 정보를 관리합니다.")
    tab1,tab2,tab3,tab4,tab5,tab6=st.tabs(["계정 및 프로필","보고서 설정","화면 설정","AI 분석 설정","프로젝트 및 저장 관리","보안 및 계정 관리"])
    with tab1:
        st.subheader("계정 및 프로필")
        with st.form("profile_form"):
            display=st.text_input("이름",value=display_name); newrole=st.text_input("직급",value=role); newdept=st.text_input("소속 부서",value=department); newcompany=st.text_input("회사명",value=company)
            if st.form_submit_button("프로필 저장"):
                conn.execute("UPDATE users SET display_name=?,role=?,department=?,company=? WHERE username=?",(display.strip() or display_name,newrole.strip() or '사용자',newdept.strip(),newcompany.strip(),username)); conn.commit(); st.success("프로필을 저장했어요."); st.rerun()
    with tab2:
        st.subheader("보고서 설정")
        with st.form("report_settings"):
            scompany=st.text_input("보고서에 표시할 회사명",value=settings.get("company",company)); logo=st.text_input("회사 로고 대신 표시할 텍스트",value=settings.get("logo_text",""),help="현재 버전은 로고 이미지 업로드 대신 텍스트 표시를 지원합니다."); author=st.text_input("보고서 작성자",value=settings.get("report_author",display_name)); rstyle=st.selectbox("보고서 문체",["업무용 간결체","상세 분석형"],index=0 if settings.get("report_style")=="업무용 간결체" else 1)
            if st.form_submit_button("보고서 설정 저장"):
                settings.update({"company":scompany,"logo_text":logo,"report_author":author,"report_style":rstyle}); save_settings(username,settings); st.success("보고서 설정을 저장했어요.")
    with tab3:
        st.subheader("화면 설정")
        with st.form("display_settings"):
            theme=st.radio("화면 테마",["밝은 화면","어두운 화면"],horizontal=True,index=0 if settings.get("theme")=="밝은 화면" else 1); font=st.selectbox("글자 크기",["작게","보통","크게"],index=["작게","보통","크게"].index(settings.get("font","보통")) if settings.get("font") in ["작게","보통","크게"] else 1)
            if st.form_submit_button("화면 설정 저장"):
                settings.update({"theme":theme,"font":font}); save_settings(username,settings); st.success("화면 설정을 저장했어요. 새로고침하면 테마가 적용됩니다."); st.rerun()
    with tab4:
        st.subheader("AI 분석 설정")
        with st.form("ai_settings"):
            detail=st.selectbox("분석 상세도",["핵심 요약","상세 분석"],index=0 if settings.get("detail")=="핵심 요약" else 1); report_style=st.selectbox("기본 보고서 문체",["업무용 간결체","상세 분석형"],index=0 if settings.get("report_style")=="업무용 간결체" else 1)
            if st.form_submit_button("AI 설정 저장"):
                settings.update({"detail":detail,"report_style":report_style}); save_settings(username,settings); st.success("AI 분석 설정을 저장했어요.")
        st.info("현재 버전의 AI 설명은 입력값 기반 규칙형 분석입니다. 실제 생성형 AI 연결을 원하면 별도 API 키와 모델 연동이 필요합니다.")
    with tab5:
        st.subheader("프로젝트 및 저장 관리")
        projects=list_projects(username)
        if not projects: st.caption("저장된 프로젝트가 없습니다.")
        for pid,title,updated,data_json in projects:
            with st.container(border=True):
                c1,c2,c3=st.columns([3,1,1]); c1.markdown(f"**{title}**\n\n<small>{updated}</small>",unsafe_allow_html=True)
                if c2.button("불러오기",key=f"loadset{pid}"): st.session_state.event_data=decode_project_data(data_json); st.session_state.page="dashboard"; st.rerun()
                if c3.button("삭제",key=f"delset{pid}"): conn.execute("DELETE FROM projects WHERE id=? AND username=?",(pid,username)); conn.commit(); st.rerun()
    with tab6:
        st.subheader("보안 및 계정 관리")
        with st.form("password_form"):
            oldpw=st.text_input("현재 비밀번호",type="password"); newpw=st.text_input("새 비밀번호 (4자 이상)",type="password"); confirm=st.text_input("새 비밀번호 확인",type="password")
            if st.form_submit_button("비밀번호 변경"):
                current=conn.execute("SELECT password_hash FROM users WHERE username=?",(username,)).fetchone()
                if not current or current[0]!=hash_pw(oldpw): st.error("현재 비밀번호가 올바르지 않습니다.")
                elif len(newpw)<4: st.error("새 비밀번호는 4자 이상이어야 합니다.")
                elif newpw!=confirm: st.error("새 비밀번호가 일치하지 않습니다.")
                else: conn.execute("UPDATE users SET password_hash=? WHERE username=?",(hash_pw(newpw),username)); conn.commit(); st.success("비밀번호를 변경했어요.")
        st.warning("계정 탈퇴는 저장된 프로젝트와 프로필을 삭제합니다.")
        if st.button("계정 탈퇴",type="secondary"):
            st.session_state.confirm_delete=True
        if st.session_state.get("confirm_delete"):
            st.error("정말 탈퇴할까요? 이 작업은 되돌릴 수 없습니다.")
            ca,cb=st.columns(2)
            if ca.button("탈퇴 확정"):
                conn.execute("DELETE FROM users WHERE username=?",(username,)); conn.execute("DELETE FROM projects WHERE username=?",(username,)); conn.execute("DELETE FROM settings WHERE username=?",(username,)); conn.commit(); st.session_state.user=None; st.session_state.confirm_delete=False; st.rerun()
            if cb.button("취소"): st.session_state.confirm_delete=False; st.rerun()

st.divider()
st.caption("Event ON · 행사장 배치도와 혼잡도는 기획용 시뮬레이션입니다. 실제 운영 전 현장 실측 및 안전 검토가 필요합니다.")
