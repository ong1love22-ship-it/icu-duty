import streamlit as st
import pandas as pd
import pulp
import os

# 1. 페이지 설정
st.set_page_config(page_title="MICU AI 근무표 생성기", layout="wide")

# 로그인 세션 (비밀번호: 1234)
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🏥 MICU AI 근무표 시스템")
    pw = st.text_input("비밀번호 입력", type="password")
    if st.button("로그인"):
        if pw == "1234":
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    st.stop()

# 2. 메인 화면
st.title("🏥 MICU 최적화 근무표 (바탕화면 최종본 로직)")
st.info("코랩에서 검증된 '근무표파이선코드'의 모든 제약 조건이 적용되었습니다.")

file_path = 'request_off.xlsx'

if st.button("근무표 생성 시작 (고성능 모드)"):
    if not os.path.exists(file_path):
        st.error(f"'{file_path}' 파일을 찾을 수 없습니다.")
        st.stop()

    try:
        with st.spinner("코랩 엔진 가동 중... 정교한 계산을 위해 최대 1~2분이 소요될 수 있습니다."):
            # --- [수간호사님 원본 로직 시작] ---
            df_input = pd.read_excel(file_path)
            nurses = df_input.iloc[:, 0].tolist()
            nurse_skill = dict(zip(nurses, df_input.iloc[:, 1]))
            num_days = 30
            days = range(1, num_days + 1)
            shifts = ['D', 'E', 'N', 'OFF']
            work_shifts = ['D', 'E', 'N']

            prob = pulp.LpProblem("Nurse_Scheduling_Master_Final", pulp.LpMinimize)
            x = pulp.LpVariable.dicts("x", (nurses, days, shifts), cat=pulp.LpBinary)

            for d in days:
                prob += pulp.lpSum([x[n][d]['D'] for n in nurses]) == 4
                prob += pulp.lpSum([x[n][d]['E'] for n in nurses]) == 5
                prob += pulp.lpSum([x[n][d]['N'] for n in nurses]) == 4
                for s in work_shifts:
                    prob += pulp.lpSum([x[n][d][s] for n in nurses if nurse_skill[n] == 1]) >= 1

            for n in nurses:
                for d in days:
                    # 엑셀 오프 반영
                    if str(df_input.iloc[nurses.index(n), d+1]).upper() == 'O':
                        prob += x[n][d]['OFF'] == 1
                    prob += pulp.lpSum([x[n][d][s] for s in shifts]) == 1

                # 휴무 10~15일, 나이트 최대 8회
                prob += pulp.lpSum([x[n][d]['OFF'] for d in days]) >= 10
                prob += pulp.lpSum([x[n][d]['OFF'] for d in days]) <= 15
                prob += pulp.lpSum([x[n][d]['N'] for d in days]) <= 8

                for d in days:
                    # ED, ND, NE 금지
                    if d < num_days:
                        prob += x[n][d]['E'] + x[n][d+1]['D'] <= 1
                        prob += x[n][d]['N'] + x[n][d+1]['D'] <= 1
                        prob += x[n][d]['N'] + x[n][d+1]['E'] <= 1

                    # 나이트 최소 2연속 및 단독 나이트 방지
                    if d <= num_days - 2:
                        if d == 1:
                            prob += x[n][1]['N'] <=
