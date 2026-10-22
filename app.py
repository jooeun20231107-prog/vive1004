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
    st.markdown("<div class=\"eo-section\">AI 행사 설계 보고서</div>",unsafe_allow_html=True)
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
    st.markdown("<div class=\"eo-section\">설정</div>",unsafe_allow_html=True)
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
