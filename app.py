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
    fig, ax = plt.subplots(figsize=(10,6), dpi=150)
    fig.patch.set_facecolor('#f8fafc'); ax.set_facecolor('#f8fafc')
    ax.add_patch(Rectangle((0.025,0.04),.95,.91,facecolor='#f1f5f9',edgecolor='#94a3b8',linewidth=2,linestyle='--'))
    ax.text(.5,.92,data.get('name','행사장')+' · 행사장 배치도',ha='center',va='center',fontsize=12,fontweight='bold',color='#0f172a')
    pos=positions(data); facilities=data.get('facilities',[])
    # Draw circulation lanes
    ax.plot([.49,.49,.72,.72],[.09,.48,.48,.78],color='#94a3b8',linewidth=8,alpha=.22,solid_capstyle='round')
    ax.plot([.12,.88],[.48,.48],color='#94a3b8',linewidth=6,alpha=.18,solid_capstyle='round')
    for name in facilities:
        x,y=pos.get(name, (random.uniform(.15,.85),random.uniform(.2,.8)))
        w=.20 if name in ('공연장','체험 부스') else .16; h=.13
        if selected==name: edge='#2563eb'; lw=3
        else: edge='#64748b'; lw=1
        ax.add_patch(Rectangle((x-w/2,y-h/2),w,h,facecolor=FACILITY_COLORS.get(name,'#e2e8f0'),edgecolor=edge,linewidth=lw,zorder=3))
        ax.text(x,y,name,ha='center',va='center',fontsize=8,fontweight='bold',color='#1e293b',zorder=4,wrap=True)
    for name,x,y in [('입구',.49,.07),('출구',.90,.07)]:
        if name not in facilities:
            ax.add_patch(Rectangle((x-.07,y-.035),.14,.07,facecolor=FACILITY_COLORS[name],edgecolor='#64748b'))
            ax.text(x,y,name,ha='center',va='center',fontsize=8)
    ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis('off'); plt.tight_layout(pad=.5)
    if path:
        fig.savefig(path,bbox_inches='tight',facecolor=fig.get_facecolor())
        plt.close(fig); return path
    buf=io.BytesIO(); fig.savefig(buf,format='png',bbox_inches='tight',facecolor=fig.get_facecolor()); plt.close(fig); buf.seek(0); return buf

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

# ---------- Crowd simulation widget ----------
def crowd_widget():
    html = r'''<!DOCTYPE html><html><head><style>body{margin:0;background:#f8fafc;font-family:Arial,sans-serif}.wrap{border:1px solid #dbe3ef;border-radius:12px;overflow:hidden;background:linear-gradient(#f8fafc,#eaf1f8)}canvas{display:block;width:100%;height:205px}.caption{font-size:11px;color:#64748b;padding:4px 10px 8px}</style></head><body><div class="wrap"><canvas id="c" width="700" height="260"></canvas><div class="caption">실시간 애니메이션 시뮬레이션 · 실제 현장 센서 데이터가 아닌 예시 이동 모델</div></div><script>
const c=document.getElementById('c'),ctx=c.getContext('2d');let W=700,H=260;let people=[];for(let i=0;i<68;i++){people.push({x:Math.random()*W,y:Math.random()*H*.82,tx:100+Math.random()*500,ty:35+Math.random()*180,s:.45+Math.random()*.7,phase:Math.random()*6.28})}
function poly(points,fill,stroke){ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.closePath();ctx.fillStyle=fill;ctx.fill();ctx.strokeStyle=stroke;ctx.stroke()}
function draw(t){ctx.clearRect(0,0,W,H);ctx.fillStyle='#f8fafc';ctx.fillRect(0,0,W,H);
// isometric venue platform
poly([[70,60],[360,20],[640,80],[345,130]],'#e2e8f0','#94a3b8');poly([[70,60],[345,130],[345,220],[70,150]],'#cbd5e1','#94a3b8');poly([[345,130],[640,80],[640,170],[345,220]],'#dbeafe','#94a3b8');
// booths
poly([[120,76],[190,66],[220,80],[150,91]],'#bfdbfe','#64748b');poly([[260,54],[318,45],[350,57],[292,67]],'#fed7aa','#64748b');poly([[410,72],[468,64],[500,76],[442,86]],'#e9d5ff','#64748b');poly([[470,117],[520,109],[546,120],[496,129]],'#bbf7d0','#64748b');
ctx.fillStyle='#334155';ctx.font='bold 10px Arial';ctx.fillText('STAGE',145,80);ctx.fillText('FOOD',291,57);ctx.fillText('BOOTH',438,78);ctx.fillText('REST',495,122);
// animate crowd on perspective plane
for(let p of people){p.phase+=.035*p.s;p.x+=Math.sin(p.phase)*.65*p.s+(p.tx-p.x)*.0018;p.y+=Math.cos(p.phase*.8)*.45*p.s+(p.ty-p.y)*.0018;if(Math.abs(p.tx-p.x)<12&&Math.abs(p.ty-p.y)<12){p.tx=75+Math.random()*550;p.ty=60+Math.random()*140}let scale=.55+p.y/450;let col=p.x>250&&p.x<365&&p.y>60&&p.y<160?'#f59e0b':'#2563eb';ctx.strokeStyle=col;ctx.fillStyle=col;ctx.lineWidth=2.2*scale;ctx.beginPath();ctx.arc(p.x,p.y,2.3*scale,0,Math.PI*2);ctx.fill();ctx.beginPath();ctx.moveTo(p.x,p.y+3*scale);ctx.lineTo(p.x,p.y+10*scale);ctx.moveTo(p.x,p.y+5*scale);ctx.lineTo(p.x-3*scale,p.y+8*scale);ctx.moveTo(p.x,p.y+5*scale);ctx.lineTo(p.x+3*scale,p.y+8*scale);ctx.moveTo(p.x,p.y+10*scale);ctx.lineTo(p.x-2*scale,p.y+14*scale);ctx.moveTo(p.x,p.y+10*scale);ctx.lineTo(p.x+2*scale,p.y+14*scale);ctx.stroke();}
ctx.fillStyle='#0f172a';ctx.font='bold 12px Arial';ctx.fillText('행사장 내 방문객 이동 시뮬레이션',16,20);requestAnimationFrame(draw)}requestAnimationFrame(draw);
</script></body></html>'''
    components.html(html, height=270, scrolling=False)

# ---------- Auth ----------
def auth_screen():
    st.markdown("# Event ON")
    st.caption("AI 행사 설계 및 보고 플랫폼")
    a,b=st.columns(2, gap="large")
    with a:
        st.subheader("로그인")
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
        with st.form("signup_form"):
            name=st.text_input("이름")
            newun=st.text_input("사용할 아이디")
            newpw=st.text_input("비밀번호",type="password")
            role=st.text_input("직급",value="사용자")
            dept=st.text_input("소속 부서")
            company=st.text_input("회사명")
            ok2=st.form_submit_button("계정 만들기",use_container_width=True)
        if ok2:
            if not name.strip() or not newun.strip() or len(newpw)<4: st.error("이름과 아이디를 입력하고 비밀번호는 4자 이상으로 설정해 주세요.")
            elif conn.execute("SELECT 1 FROM users WHERE username=?",(newun.strip(),)).fetchone(): st.error("이미 사용 중인 아이디입니다.")
            else:
                conn.execute("INSERT INTO users(username,password_hash,display_name,role,department,company) VALUES(?,?,?,?,?,?)",(newun.strip(),hash_pw(newpw),name.strip(),role.strip() or "사용자",dept.strip(),company.strip())); conn.commit()
                st.success("가입이 완료됐어요. 왼쪽 로그인에서 로그인해 주세요.")
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
    st.markdown("## 행사 기획을 더 똑똑하게, **Event ON**")
    st.markdown("행사 정보를 입력하고, 공간을 설계하고, 보고서까지 한 번에 준비하세요.")
    st.write("")
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
                st.session_state.event_data={"name":name,"purpose":purpose,"budget":budget,"visitors":visitors,"venue":venue,"event_date":event_date,"duration_days":duration,"start_time":start,"end_time":end,"mood":mood,"age":age,"inside":inside,"ticket":ticket,"ticket_price":ticket_price if ticket=="유료" else 0,"facilities":facilities,"extra":extra}
                st.session_state.overrides={}; st.session_state.data_confirmed=True; st.success("행사 기본정보가 업데이트됐어요."); st.rerun()
    data=st.session_state.event_data
    left,right=st.columns([1.55,1],gap="large")
    with left:
        st.markdown("#### 혼잡도 분석 · 실시간 이동 시뮬레이션")
        crowd_widget()
        st.markdown("#### 행사장 배치도")
        st.caption(f"{data.get('venue')} · 예상 방문객 {int(data.get('visitors',0)):,}명 · 시설 이름을 오른쪽에서 선택해 분석하세요.")
        st.image(make_layout_image(data,st.session_state.selected_zone),use_container_width=True)
        st.caption("배치도는 기본 모형을 바탕으로 생성된 예시 설계도입니다. 실제 장소 치수에 맞춘 도면 검증이 필요합니다.")
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
        st.caption("시설을 선택하고 새 구역을 지정해 배치안을 조정할 수 있어요.")
        move_zone=st.selectbox("이동할 시설",facilities,key="move_zone")
        spot_options={"앞쪽 왼편":(.18,.28),"앞쪽 중앙":(.49,.20),"앞쪽 오른편":(.80,.28),"중앙 왼편":(.22,.50),"중앙":(.50,.50),"중앙 오른편":(.78,.50),"뒤쪽 왼편":(.22,.75),"뒤쪽 중앙":(.50,.75),"뒤쪽 오른편":(.78,.75)}
        spot=st.selectbox("새 위치",list(spot_options.keys()),key="spot")
        if st.button("선택한 위치로 배치 변경",use_container_width=True):
            st.session_state.overrides[move_zone]=spot_options[spot]; st.success(f"{move_zone} 위치를 변경했어요."); st.rerun()
        if st.button("AI 추천 배치로 초기화",use_container_width=True): st.session_state.overrides={}; st.rerun()
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
