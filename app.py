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
h1,h2,h3 {letter-spacing:-.025em}
</style>
""", unsafe_allow_html=True)

# -------------------- Session state --------------------
DEFAULT_EVENT = {
    "name":"봄맞이 문화축제", "purpose":"지역 주민 참여와 문화 체험",
    "budget":10000000, "visitors":1200, "venue":"야외 축제장",
    "duration_days":1, "event_date":date.today()+timedelta(days=30),
    "start_time":time(10,0), "end_time":time(18,0), "mood":"활기찬",
    "age":"전 연령", "inside":"실외", "ticket":"무료", "ticket_price":0,
    "facilities":["공연장","푸드존","체험 부스","휴게 공간","응급의료센터","안내센터","입구","출구"],
    "extra":"입구에서 안내센터가 잘 보이도록 배치"
}
if "page" not in st.session_state: st.session_state.page = "home"
if "user" not in st.session_state: st.session_state.user = None
if "event_data" not in st.session_state: st.session_state.event_data = DEFAULT_EVENT.copy()
if "selected_zone" not in st.session_state: st.session_state.selected_zone = "공연장"
if "overrides" not in st.session_state: st.session_state.overrides = {}
if "crowd_running" not in st.session_state: st.session_state.crowd_running = False

FACILITY_COLORS = {
    "공연장":"#bfdbfe", "푸드존":"#fed7aa", "체험 부스":"#e9d5ff",
    "휴게 공간":"#bbf7d0", "응급의료센터":"#fecaca", "안내센터":"#fef08a",
    "입구":"#cbd5e1", "출구":"#94a3b8", "화장실":"#bae6fd", "굿즈 판매":"#fbcfe8"
}
BASE_POS = {
    "공연장":(0.34,0.72), "푸드존":(0.76,0.65), "체험 부스":(0.23,0.43),
    "휴게 공간":(0.69,0.34), "응급의료센터":(0.84,0.22), "안내센터":(0.13,0.20),
    "입구":(0.49,0.06), "출구":(0.91,0.06), "화장실":(0.08,0.58), "굿즈 판매":(0.53,0.43)
}
ALT_POS = {
    "전시장형":{"공연장":(0.50,0.78),"푸드존":(0.80,0.22),"체험 부스":(0.25,0.55),
                "휴게 공간":(0.25,0.25),"응급의료센터":(0.86,0.50),"안내센터":(0.10,0.10)},
    "컨벤션·강연장형":{"공연장":(0.50,0.78),"푸드존":(0.82,0.20),"체험 부스":(0.25,0.52),
                "휴게 공간":(0.75,0.50),"응급의료센터":(0.10,0.24),"안내센터":(0.12,0.70)},
    "공원·광장형":{"공연장":(0.50,0.78),"푸드존":(0.80,0.55),"체험 부스":(0.25,0.50),
                "휴게 공간":(0.70,0.28),"응급의료센터":(0.12,0.23),"안내센터":(0.12,0.70)}
}

def positions(data):
    model = data.get("venue", "야외 축제장")
    base = dict(BASE_POS)
    model_key = ("전시장형" if "전시" in model else
                 "컨벤션·강연장형" if ("컨벤션" in model or "강연" in model) else
                 "공원·광장형" if ("공원" in model or "광장" in model) else None)
    if model_key:
        base.update(ALT_POS[model_key])
    base.update(st.session_state.get("overrides", {}))
    return base

def make_layout_image(data, selected=None, path=None):
    """행사장 배치도를 생성한다. path가 있으면 파일로 저장하고, 없으면 PNG bytes를 반환한다."""
    fig, ax = plt.subplots(figsize=(10, 6.4), dpi=130)
    fig.patch.set_facecolor("#f8fafc")
    ax.set_facecolor("#f8fafc")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    # Venue boundary and soft grid
    ax.add_patch(Rectangle((0.035, 0.04), .93, .91, facecolor="#ffffff",
                           edgecolor="#cbd5e1", linewidth=2, zorder=0))
    for x in [i/20 for i in range(2, 20, 2)]:
        ax.plot([x, x], [.06, .93], color="#f1f5f9", lw=.6, zorder=0)
    for y in [i/10 for i in range(1, 10)]:
        ax.plot([.04, .96], [y, y], color="#f1f5f9", lw=.6, zorder=0)
    # Main walking routes
    ax.plot([.49,.49,.30,.30,.76,.76,.91], [.09,.28,.28,.49,.49,.68,.68],
            color="#cbd5e1", lw=13, solid_capstyle="round", zorder=1)
    ax.plot([.49,.49,.30,.30,.76,.76,.91], [.09,.28,.28,.49,.49,.68,.68],
            color="#f8fafc", lw=8, solid_capstyle="round", zorder=2)
    selected_names = set(data.get("facilities", []))
    selected_names.update(["입구","출구"])
    pos = positions(data)
    for name in selected_names:
        x, y = pos.get(name, (random.uniform(.2,.8), random.uniform(.2,.8)))
        color = FACILITY_COLORS.get(name, "#e2e8f0")
        is_selected = name == selected
        w, h = (.19,.13) if name == "공연장" else (.15,.105)
        if name in ("입구","출구"):
            w,h = .105,.065
        # raised-looking block with shadow
        ax.add_patch(Rectangle((x-w/2+.012,y-h/2-.014), w,h,
                               facecolor="#cbd5e1", edgecolor="none", zorder=3))
        ax.add_patch(Rectangle((x-w/2,y-h/2), w,h, facecolor=color,
                               edgecolor="#2563eb" if is_selected else "#64748b",
                               linewidth=2.5 if is_selected else 1.0, zorder=4))
        ax.add_patch(Rectangle((x-w/2,y+h/2-.014), w,.014,
                               facecolor="#ffffff", edgecolor="none", alpha=.6, zorder=5))
        ax.text(x, y, name, ha="center", va="center", fontsize=8 if name not in ("공연장","체험 부스") else 9,
                fontweight="bold" if is_selected else "normal", color="#0f172a", zorder=6)
    ax.text(.05,.965, "EVENT ON · 행사장 디지털 트윈 배치도", fontsize=11,
            color="#334155", fontweight="bold", va="bottom")
    ax.text(.95,.965, f"예상 방문객 {int(data.get('visitors',0)):,}명", fontsize=9,
            color="#64748b", ha="right", va="bottom")
    fig.tight_layout(pad=.5)
    if path:
        fig.savefig(path, format="png", bbox_inches="tight")
        plt.close(fig)
        return path
    output = io.BytesIO()
    fig.savefig(output, format="png", bbox_inches="tight")
    plt.close(fig)
    output.seek(0)
    return output.getvalue()

def estimate_crowd(data):
    visitors = max(0, int(data.get("visitors", 0)))
    capacity = max(1, visitors * 0.22)
    zones = ["공연장","푸드존","체험 부스","휴게 공간","안내센터"]
    weights = {"공연장":.34,"푸드존":.24,"체험 부스":.20,"휴게 공간":.12,"안내센터":.10}
    result = {}
    for z in zones:
        count = int(visitors * weights[z])
        ratio = count / capacity
        level = "높음" if ratio >= 1.1 else "보통" if ratio >= .65 else "낮음"
        result[z] = {"count":count,"level":level,"ratio":ratio}
    return result

def render_crowd_simulation(data):
    """실제 센서 데이터가 아닌 예시 인원 흐름을 애니메이션으로 표현한다."""
    people = []
    random.seed(17)
    for i in range(34):
        lane = i % 4
        x = random.uniform(.12,.88)
        y = random.uniform(.10,.88)
        people.append((x,y,random.choice(["#2563eb","#0f766e","#f97316"]),random.uniform(.006,.012),lane))
    fig, ax = plt.subplots(figsize=(5.5,3.2), dpi=110)
    ax.set_facecolor("#f8fafc"); fig.patch.set_facecolor("#f8fafc")
    ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis("off")
    ax.add_patch(Rectangle((.04,.05),.92,.90,facecolor="white",edgecolor="#cbd5e1",lw=1.5,zorder=0))
    # simple walkways
    ax.plot([.5,.5,.25,.25,.75,.75],[.08,.35,.35,.65,.65,.90],color="#e2e8f0",lw=18,zorder=1)
    for i,(x,y,color,r,lane) in enumerate(people):
        # small person icon: head + body + legs
        x = .08 + ((x + (i%5)*.037) % .84)
        y = .08 + ((y + (i%7)*.029) % .82)
        ax.add_patch(Circle((x,y+r*1.8),r,facecolor=color,edgecolor="white",lw=.3,zorder=3))
        ax.plot([x,x],[y-r,y+r],color=color,lw=1.8,zorder=3)
        ax.plot([x,x-r*.7],[y-r,y-r*1.8],color=color,lw=1.4,zorder=3)
        ax.plot([x,x+r*.7],[y-r,y-r*1.8],color=color,lw=1.4,zorder=3)
    ax.text(.06,.965,"인원 흐름 미리보기 · 예시 시뮬레이션",fontsize=8,color="#334155",va="top")
    fig.tight_layout(pad=.2)
    output=io.BytesIO(); fig.savefig(output,format="png",bbox_inches="tight"); plt.close(fig)
    output.seek(0)
    return output.getvalue()

def create_pdf(data, settings):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=17*mm, leftMargin=17*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="KoreanTitle", parent=styles["Title"], fontName="HYSMyeongJo-Medium",
                              fontSize=21, leading=28, textColor=colors.HexColor("#1d4ed8"), spaceAfter=10))
    styles.add(ParagraphStyle(name="KoreanBody", parent=styles["BodyText"], fontName="HYSMyeongJo-Medium",
                              fontSize=9, leading=14, wordWrap="CJK", spaceAfter=5))
    styles.add(ParagraphStyle(name="KoreanHeading", parent=styles["Heading2"], fontName="HYSMyeongJo-Medium",
                              fontSize=13, leading=18, textColor=colors.HexColor("#1e293b"), spaceBefore=10, spaceAfter=5))
    def p(text, style="KoreanBody"):
        safe = str(text).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        return Paragraph(safe, styles[style])
    story = [p(settings.get("logo_text") or "EVENT ON","KoreanBody"),
             p(f"{data.get('name','이름 없는 행사')} 기획 보고서","KoreanTitle"),
             p(f"작성일: {date.today().isoformat()}   작성자: {settings.get('report_author') or '미입력'}"),
             p("1. 행사 개요","KoreanHeading")]
    overview = [
        ["항목","내용"],
        ["행사 목적",data.get("purpose","미입력")],
        ["일정",f"{data.get('event_date',date.today())} / {data.get('start_time','')}~{data.get('end_time','')}"],
        ["장소",data.get("venue","미입력")],
        ["예상 방문객",f"{int(data.get('visitors',0)):,}명"],
        ["예산",f"{int(data.get('budget',0)):,}원"],
        ["분위기 / 연령",f"{data.get('mood','')} / {data.get('age','')}"],
        ["입장료",f"{data.get('ticket','무료')} {int(data.get('ticket_price',0)):,}원"]
    ]
    table=Table([[p(c) for c in row] for row in overview], colWidths=[34*mm,128*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#dbeafe")),
        ("GRID",(0,0),(-1,-1),.4,colors.HexColor("#cbd5e1")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),6),
        ("RIGHTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5)
    ]))
    story += [table,p("2. 공간 배치","KoreanHeading")]
    layout_bytes=make_layout_image(data, st.session_state.get("selected_zone"))
    story.append(RLImage(io.BytesIO(layout_bytes), width=165*mm, height=105*mm))
    story += [p("3. 혼잡도 참고 분석","KoreanHeading")]
    crowd=estimate_crowd(data)
    crowd_rows=[["공간","예상 인원(단순 추정)","참고 수준"]]
    for zone,info in crowd.items():
        crowd_rows.append([zone,f"{info['count']:,}명",info["level"]])
    ctable=Table([[p(c) for c in row] for row in crowd_rows],colWidths=[50*mm,60*mm,52*mm],repeatRows=1)
    ctable.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e2e8f0")),
        ("GRID",(0,0),(-1,-1),.4,colors.HexColor("#cbd5e1")),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story += [ctable,Spacer(1,5*mm),p("주의: 혼잡도 수치는 입력한 방문객 수를 이용한 단순 예시 추정이며, 실제 센서·현장 데이터에 기반한 측정값이 아닙니다.")]
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def generate_recommendations(data):
    visitors = int(data.get("visitors", 0))
    tips = []
    if visitors >= 2000:
        tips.append("방문객이 많으므로 입구와 출구를 분리하고 주요 통로를 넓게 확보하세요.")
    else:
        tips.append("입구와 출구 주변에 안내 표지와 대기 공간을 확보하세요.")
    if "응급의료센터" not in data.get("facilities", []):
        tips.append("응급 상황에 대비해 응급의료센터 또는 응급 대응 지점을 추가하세요.")
    if "푸드존" in data.get("facilities", []):
        tips.append("푸드존은 공연장 출입구 및 주요 교차 통로와 거리를 두어 대기 줄이 통행을 막지 않도록 하세요.")
    if "휴게 공간" in data.get("facilities", []):
        tips.append("휴게 공간은 소음이 큰 무대에서 떨어진 곳에 배치하고 접근 가능한 통로를 연결하세요.")
    if data.get("inside") == "실내":
        tips.append("실내 행사라면 비상구, 피난 동선, 소방 설비의 위치를 현장 기준에 맞게 확인하세요.")
    if data.get("extra"):
        tips.append("추가 요청 반영: " + str(data["extra"]))
    return tips

# -------------------- Authentication --------------------
def login_page():
    st.title("🎪 Event ON")
    st.caption("행사 기획부터 공간 배치와 보고서까지, 한 화면에서")
    left, right = st.columns([1.1, .9], gap="large")
    with left:
        st.markdown("### 행사 기획을 더 쉽고 명확하게")
        st.write("행사 정보를 입력하고 공간 배치 초안을 확인한 뒤, 보고서를 저장해 보세요.")
        st.image(make_layout_image(st.session_state.event_data), use_container_width=True)
    with right:
        tab_login, tab_signup = st.tabs(["로그인","회원가입"])
        with tab_login:
            with st.form("login_form"):
                username=st.text_input("아이디", key="login_username")
                password=st.text_input("비밀번호", type="password", key="login_password")
                submitted=st.form_submit_button("로그인", use_container_width=True)
            if submitted:
                row=conn.execute("SELECT password_hash FROM users WHERE username=?",(username.strip(),)).fetchone()
                if row and row[0] == hash_pw(password):
                    st.session_state.user=username.strip()
                    st.session_state.page="home"
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호를 확인해 주세요.")
        with tab_signup:
            with st.form("signup_form"):
                display_name=st.text_input("이름")
                username=st.text_input("아이디")
                password=st.text_input("비밀번호",type="password")
                confirm=st.text_input("비밀번호 확인",type="password")
                submitted=st.form_submit_button("가입하기",use_container_width=True)
            if submitted:
                display_name=display_name.strip(); username=username.strip()
                if not display_name or not username or not password:
                    st.error("이름, 아이디, 비밀번호를 모두 입력해 주세요.")
                elif len(username)<3:
                    st.error("아이디는 3자 이상 입력해 주세요.")
                elif len(password)<6:
                    st.error("비밀번호는 6자 이상 입력해 주세요.")
                elif password != confirm:
                    st.error("비밀번호가 서로 다릅니다.")
                elif get_user(username):
                    st.error("이미 사용 중인 아이디입니다.")
                else:
                    conn.execute("INSERT INTO users(username,password_hash,display_name) VALUES(?,?,?)",
                                 (username,hash_pw(password),display_name))
                    conn.commit()
                    st.success("가입이 완료됐어요. 로그인해 주세요.")

def sidebar():
    user=get_user(st.session_state.user)
    settings=get_settings(st.session_state.user)
    with st.sidebar:
        if st.button("🎪 Event ON", use_container_width=True, type="primary"):
            st.session_state.page="home"; st.rerun()
        st.caption(f"{user[1]} 님 · {user[2]}" if user else "행사 기획 대시보드")
        st.divider()
        pages=[("home","🏠 대시보드"),("design","🗺️ 행사 설계"),("report","📄 AI 보고서"),("projects","🗂️ 저장한 행사"),("settings","⚙️ 설정")]
        for key,label in pages:
            if st.button(label, key="nav_"+key, use_container_width=True,
                         type="primary" if st.session_state.page==key else "secondary"):
                st.session_state.page=key; st.rerun()
        st.divider()
        if st.button("로그아웃", use_container_width=True):
            st.session_state.user=None; st.session_state.page="home"; st.rerun()

def home_page():
    user=get_user(st.session_state.user)
    st.title("안녕하세요, " + (user[1] if user else "기획자") + "님 👋")
    st.write("오늘의 행사 기획 현황을 확인하고 새로운 행사를 설계해 보세요.")
    projects=list_projects(st.session_state.user)
    c1,c2,c3=st.columns(3)
    c1.metric("저장한 행사",f"{len(projects)}개")
    c2.metric("현재 예상 방문객",f"{int(st.session_state.event_data.get('visitors',0)):,}명")
    c3.metric("현재 예산",f"{int(st.session_state.event_data.get('budget',0)):,}원")
    st.markdown("### 빠른 시작")
    a,b=st.columns(2)
    with a:
        st.markdown('<div class="eo-card"><h3>🗺️ 행사 설계</h3><p>행사 정보를 입력하고 공간 배치 초안을 확인하세요.</p></div>',unsafe_allow_html=True)
        if st.button("행사 설계 시작 →",use_container_width=True):
            st.session_state.page="design"; st.rerun()
    with b:
        st.markdown('<div class="eo-card"><h3>📄 AI 보고서</h3><p>입력한 정보를 바탕으로 기획 요약과 혼잡도 참고 분석을 확인하세요.</p></div>',unsafe_allow_html=True)
        if st.button("보고서 확인 →",use_container_width=True):
            st.session_state.page="report"; st.rerun()
    st.markdown("### 현재 배치도 미리보기")
    st.image(make_layout_image(st.session_state.event_data,st.session_state.selected_zone),use_container_width=True)
    st.caption("배치도와 혼잡도는 입력값을 바탕으로 만든 기획 초안이며, 현장 측정 결과가 아닙니다.")

def design_page():
    st.title("🗺️ 행사 설계")
    st.caption("행사 정보를 입력하면 공간 배치 초안과 운영 참고 사항을 확인할 수 있어요.")
    data=st.session_state.event_data
    left,right=st.columns([.85,1.15],gap="large")
    with left:
        with st.form("event_form"):
            st.subheader("1. 행사 기본 정보")
            name=st.text_input("행사명",value=data.get("name",""))
            purpose=st.text_area("행사 목적",value=data.get("purpose",""),height=80)
            c1,c2=st.columns(2)
            with c1:
                budget=st.number_input("예산(원)",min_value=0,value=int(data.get("budget",0)),step=100000)
                visitors=st.number_input("예상 방문객 수",min_value=0,value=int(data.get("visitors",0)),step=100)
                venue=st.selectbox("행사 장소 유형",["야외 축제장","공원·광장","전시장","컨벤션·강연장","학교 운동장","실내 행사장"],
                                   index=["야외 축제장","공원·광장","전시장","컨벤션·강연장","학교 운동장","실내 행사장"].index(data.get("venue","야외 축제장")) if data.get("venue","야외 축제장") in ["야외 축제장","공원·광장","전시장","컨벤션·강연장","학교 운동장","실내 행사장"] else 0)
                inside=st.selectbox("실내/실외",["실외","실내"],index=0 if data.get("inside","실외")=="실외" else 1)
            with c2:
                event_date=st.date_input("행사 날짜",value=data.get("event_date",date.today()+timedelta(days=30)))
                duration=st.number_input("행사 기간(일)",min_value=1,max_value=90,value=int(data.get("duration_days",1)))
                start=st.time_input("시작 시간",value=data.get("start_time",time(10,0)))
                end=st.time_input("종료 시간",value=data.get("end_time",time(18,0)))
                mood=st.selectbox("원하는 분위기",["활기찬","차분한","고급스러운","가족 친화적","미래적인","자연 친화적"],
                                  index=["활기찬","차분한","고급스러운","가족 친화적","미래적인","자연 친화적"].index(data.get("mood","활기찬")) if data.get("mood","활기찬") in ["활기찬","차분한","고급스러운","가족 친화적","미래적인","자연 친화적"] else 0)
                age=st.selectbox("예상 연령",["전 연령","유아·어린이","청소년","청년","성인","가족 단위"],
                                 index=["전 연령","유아·어린이","청소년","청년","성인","가족 단위"].index(data.get("age","전 연령")) if data.get("age","전 연령") in ["전 연령","유아·어린이","청소년","청년","성인","가족 단위"] else 0)
            ticket=st.selectbox("입장료 유형",["무료","유료"],index=0 if data.get("ticket","무료")=="무료" else 1)
            ticket_price=st.number_input("1인 입장료(원)",min_value=0,value=int(data.get("ticket_price",0)),step=1000,disabled=ticket=="무료")
            facility_options=list(FACILITY_COLORS.keys())
            facilities=st.multiselect("배치할 시설",facility_options,default=[x for x in data.get("facilities",[]) if x in facility_options])
            extra=st.text_area("추가 요청 사항",value=data.get("extra",""),placeholder="예: 유모차 이동 경로 확보, 입구 근처 안내센터")
            submitted=st.form_submit_button("배치도 생성 및 저장",type="primary",use_container_width=True)
        if submitted:
            st.session_state.event_data={"name":name.strip() or "이름 없는 행사","purpose":purpose,
                "budget":int(budget),"visitors":int(visitors),"venue":venue,"duration_days":int(duration),
                "event_date":event_date,"start_time":start,"end_time":end,"mood":mood,"age":age,
                "inside":inside,"ticket":ticket,"ticket_price":int(ticket_price),
                "facilities":facilities,"extra":extra}
            st.session_state.overrides={}
            save_project(st.session_state.user,st.session_state.event_data)
            st.success("행사 정보가 저장됐어요!")
            st.rerun()
    data=st.session_state.event_data
    with right:
        st.subheader("2. 행사장 디지털 트윈 배치도")
        b1,b2=st.columns([1,1])
        with b1:
            st.markdown("**혼잡도 미리보기**")
            if st.button("👥 인원 흐름 보기",use_container_width=True):
                st.session_state.crowd_running=not st.session_state.crowd_running
        with b2:
            st.markdown("**시설 선택**")
            chosen=st.selectbox("수정할 시설",data.get("facilities",[]) or ["공연장"],
                                index=(data.get("facilities",[]) or ["공연장"]).index(st.session_state.selected_zone) if st.session_state.selected_zone in (data.get("facilities",[]) or ["공연장"]) else 0,
                                label_visibility="collapsed")
            st.session_state.selected_zone=chosen
        st.image(make_layout_image(data,st.session_state.selected_zone),use_container_width=True)
        if st.session_state.crowd_running:
            st.image(render_crowd_simulation(data),use_container_width=True)
            st.caption("움직임을 표현한 예시 시뮬레이션입니다. 실제 방문객 위치를 추적하지 않습니다.")
        st.markdown("**선택 시설 위치 조정**")
        pos=positions(data).get(st.session_state.selected_zone,(.5,.5))
        colx,coly=st.columns(2)
        with colx: new_x=st.slider("좌우 위치",0.08,0.92,float(pos[0]),0.01,key="slider_x")
        with coly: new_y=st.slider("상하 위치",0.08,0.90,float(pos[1]),0.01,key="slider_y")
        if st.button("선택 시설 위치 적용",use_container_width=True):
            st.session_state.overrides[st.session_state.selected_zone]=(new_x,new_y)
            st.rerun()
        st.markdown("**배치 추천**")
        for tip in generate_recommendations(data):
            st.write("• "+tip)
        crowd=estimate_crowd(data)
        st.markdown("**시설별 혼잡도 참고치**")
        for zone,info in crowd.items():
            st.write(f"- {zone}: 약 {info['count']:,}명 · 참고 수준 **{info['level']}**")

def report_page():
    st.title("📄 AI 행사 기획 보고서")
    data=st.session_state.event_data
    settings=get_settings(st.session_state.user)
    st.write("현재 행사 정보를 바탕으로 작성한 기획 초안입니다. 실제 현장 데이터 분석 결과는 아닙니다.")
    st.markdown("### 행사 개요")
    c1,c2,c3=st.columns(3)
    c1.metric("예상 방문객",f"{int(data.get('visitors',0)):,}명")
    c2.metric("예산",f"{int(data.get('budget',0)):,}원")
    c3.metric("시설 수",f"{len(data.get('facilities',[]))}개")
    with st.container(border=True):
        st.subheader(data.get("name","이름 없는 행사"))
        st.write("**목적:** "+(data.get("purpose") or "미입력"))
        st.write(f"**일정:** {data.get('event_date')} · {data.get('start_time')}~{data.get('end_time')} · {data.get('duration_days',1)}일")
        st.write(f"**장소:** {data.get('venue')} ({data.get('inside')})")
        st.write(f"**분위기/대상:** {data.get('mood')} · {data.get('age')}")
    st.markdown("### 공간 배치도")
    st.image(make_layout_image(data,st.session_state.selected_zone),use_container_width=True)
    st.markdown("### 운영 권장 사항")
    for tip in generate_recommendations(data):
        st.write("• "+tip)
    st.markdown("### 혼잡도 참고 분석")
    crowd=estimate_crowd(data)
    st.bar_chart({z:info["count"] for z,info in crowd.items()})
    for zone,info in crowd.items():
        st.write(f"**{zone}** · 추정 {info['count']:,}명 · 혼잡 참고 수준: {info['level']}")
    st.caption("추정치는 방문객 수와 고정 비율을 사용한 데모 값입니다. 실제 인파 측정값이 아닙니다.")
    if st.button("현재 행사 저장",type="primary"):
        save_project(st.session_state.user,data); st.success("저장했습니다.")
    pdf_bytes=create_pdf(data,settings)
    st.download_button("📥 PDF 보고서 다운로드",data=pdf_bytes,file_name="Event_ON_기획보고서.pdf",mime="application/pdf",use_container_width=True)

def projects_page():
    st.title("🗂️ 저장한 행사")
    projects=list_projects(st.session_state.user)
    if not projects:
        st.info("아직 저장한 행사가 없습니다. 행사 설계에서 먼저 저장해 주세요.")
        return
    for project_id,title,updated,raw in projects:
        with st.container(border=True):
            c1,c2,c3=st.columns([2,1,1])
            c1.markdown("**"+title+"**")
            c2.caption(updated)
            if c3.button("불러오기",key=f"load_{project_id}"):
                try:
                    st.session_state.event_data=decode_project_data(raw)
                    st.session_state.overrides={}
                    st.session_state.page="design"
                    st.rerun()
                except Exception as exc:
                    st.error(f"행사 정보를 불러오지 못했습니다: {exc}")

def settings_page():
    st.title("⚙️ 설정")
    user=get_user(st.session_state.user)
    settings=get_settings(st.session_state.user)
    tab_profile,tab_display,tab_report=st.tabs(["프로필","화면","보고서"])
    with tab_profile:
        with st.form("profile_settings"):
            display_name=st.text_input("이름",value=user[1] if user else "")
            department=st.text_input("부서/팀",value=user[3] if user else "")
            company=st.text_input("소속",value=user[4] if user else "")
            if st.form_submit_button("프로필 저장"):
                conn.execute("UPDATE users SET display_name=?,department=?,company=? WHERE username=?",
                             (display_name.strip() or "사용자",department.strip(),company.strip(),st.session_state.user))
                conn.commit()
                settings["company"]=company.strip(); save_settings(st.session_state.user,settings)
                st.success("프로필을 저장했어요."); st.rerun()
        st.caption("아이디는 로그인 식별자로 사용되며 여기서 변경하지 않습니다.")
    with tab_display:
        with st.form("display_settings"):
            theme=st.selectbox("화면 테마",["밝은 화면","기본"],index=0 if settings.get("theme")=="밝은 화면" else 1)
            font=st.selectbox("글자 크기",["작게","보통","크게"],index=["작게","보통","크게"].index(settings.get("font","보통")))
            if st.form_submit_button("화면 설정 저장"):
                settings.update({"theme":theme,"font":font}); save_settings(st.session_state.user,settings)
                st.success("화면 설정을 저장했어요.")
    with tab_report:
        with st.form("report_settings"):
            report_style=st.selectbox("보고서 문체",["업무용 간결체","설명형","요약 중심"],index=["업무용 간결체","설명형","요약 중심"].index(settings.get("report_style","업무용 간결체")))
            detail=st.selectbox("보고서 상세도",["간단 분석","상세 분석"],index=0 if settings.get("detail")=="간단 분석" else 1)
            logo_text=st.text_input("보고서 로고 문구",value=settings.get("logo_text","Event ON"))
            report_author=st.text_input("보고서 작성자",value=settings.get("report_author",""))
            if st.form_submit_button("보고서 설정 저장"):
                settings.update({"report_style":report_style,"detail":detail,"logo_text":logo_text,"report_author":report_author})
                save_settings(st.session_state.user,settings); st.success("보고서 설정을 저장했어요.")

# -------------------- App router --------------------
if not st.session_state.user:
    login_page()
else:
    sidebar()
    page=st.session_state.page
    if page=="home": home_page()
    elif page=="design": design_page()
    elif page=="report": report_page()
    elif page=="projects": projects_page()
    elif page=="settings": settings_page()
    else:
        st.session_state.page="home"; st.rerun()
