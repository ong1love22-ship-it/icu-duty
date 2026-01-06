import streamlit as st
import pandas as pd
import pulp
import os

# 1. 로그인 (비밀번호: 1234)
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("MICU AI 근무표 시스템")
    pw = st.text_input("비밀번호", type="password")
    if st.button("로그인"):
        if pw == "1234":
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("비밀번호 오류")
    st.stop()

# 2. 메인 화면
st.title("🏥 MICU AI 근무표 생성기")

# 파일 확인
file_path = 'request_off.xlsx'
if not os.path.exists(file_path):
    st.error(f"파일이 없습니다: {file_path} (깃허브에 업로드했는지 확인하세요!)")
    st.stop()

# 3. 버튼을 눌렀을 때만 AI가 작동하게 함
if st.button("근무표 생성 시작"):
    try:
        with st.spinner("AI 엔진 가동 중... 잠시만 기다려 주세요."):
            # 엑셀 데이터 읽기
            df_input = pd.read_excel(file_path)
            nurses = df_input.iloc[:, 0].dropna().tolist() # 이름 목록 자동 추출
            nurse_skill = dict(zip(nurses, df_input.iloc[:, 1]))
            
            num_days = 30
            days = range(1, num_days + 1)
            shifts = ['D', 'E', 'N', 'OFF']

            # PuLP 문제 정의
            prob = pulp.LpProblem("Nurse_Scheduling", pulp.LpMinimize)
            x = pulp.LpVariable.dicts("x", (nurses, days, shifts), cat=pulp.LpBinary)

            # [제약 조건] - 인원수가 23명이든 25명이든 작동하도록 설정
            for d in days:
                prob += pulp.lpSum([x[n][d]['D'] for n in nurses]) == 4
                prob += pulp.lpSum([x[n][d]['E'] for n in nurses]) == 5
                prob += pulp.lpSum([x[n][d]['N'] for n in nurses]) == 4
                
                # 숙련도 1인 베테랑 최소 1명 포함
                for s in ['D', 'E', 'N']:
                    prob += pulp.lpSum([x[n][d][s] for n in nurses if nurse_skill.get(n) == 1]) >= 1

            for n in nurses:
                for d in days:
                    # 엑셀의 신청 오프 반영 (O 표시)
                    if str(df_input.iloc[nurses.index(n), d+1]).upper() == 'O':
                        prob += x[n][d]['OFF'] == 1
                    prob += pulp.lpSum([x[n][d][s] for s in shifts]) == 1

                # 휴무 및 나이트 제한
                prob += pulp.lpSum([x[n][d]['OFF'] for d in days]) >= 9
                prob += pulp.lpSum([x[n][d]['N'] for d in days]) <= 8

                # 나이트-데이 금지 등 패턴 제약
                for d in range(1, num_days):
                    prob += x[n][d]['N'] + x[n][d+1]['D'] <= 1
                    prob += x[n][d]['N'] + x[n][d+1]['E'] <= 1
                    prob += x[n][d]['E'] + x[n][d+1]['D'] <= 1

            # 계산 시작
            prob.solve(pulp.PULP_CBC_CMD(msg=0))

            if pulp.LpStatus[prob.status] == 'Optimal':
                final_res = []
                for n in nurses:
                    row = {'이름': n}
                    for d in days:
                        for s in shifts:
                            if pulp.value(x[n][d][s]) == 1: row[f'{d}일'] = s
                    final_res.append(row)
                
                output_df = pd.DataFrame(final_res)
                st.success("✅ 근무표 생성 완료!")
                st.dataframe(output_df)
                
                csv = output_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("결과 다운로드", data=csv, file_name="schedule.csv")
            else:
                st.error("❌ 조건 충돌! 신청 오프가 너무 많아 계산이 불가능합니다.")

    except Exception as e:
        st.error(f"오류 발생: {e}")
