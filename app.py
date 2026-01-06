import streamlit as st
import pandas as pd
import pulp
import os

# 1. 앱 설정 및 보안
st.set_page_config(page_title="MICU AI 근무표 생성기", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🏥 MICU AI 근무표 시스템")
    pw = st.text_input("비밀번호를 입력하세요", type="password")
    if st.button("로그인"):
        if pw == "1234":
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    st.stop()

# 2. 메인 화면
st.title("🏥 MICU AI 최적화 근무표")
st.write("바탕화면의 '근무표파이선코드' 로직을 사용하여 스케줄을 생성합니다.")

file_path = 'request_off.xlsx'
if not os.path.exists(file_path):
    st.error(f"'{file_path}' 파일을 찾을 수 없습니다. 깃허브에 엑셀을 업로드해주세요.")
    st.stop()

# 3. 근무표 생성 버튼
if st.button("최종본 로직으로 근무표 생성 시작"):
    try:
        with st.spinner("최적의 근무 패턴을 계산 중입니다..."):
            # 데이터 로드
            df_input = pd.read_excel(file_path)
            nurses = df_input.iloc[:, 0].dropna().tolist()
            nurse_skill = dict(zip(nurses, df_input.iloc[:, 1]))
            num_days = 30
            days = range(1, num_days + 1)
            shifts = ['D', 'E', 'N', 'OFF']

            # 문제 정의
            prob = pulp.LpProblem("Nurse_Scheduling", pulp.LpMinimize)
            x = pulp.LpVariable.dicts("x", (nurses, days, shifts), cat=pulp.LpBinary)

            # [핵심 제약 조건]
            for d in days:
                # 매일 근무 인원 고정
                prob += pulp.lpSum([x[n][d]['D'] for n in nurses]) == 4
                prob += pulp.lpSum([x[n][d]['E'] for n in nurses]) == 5
                prob += pulp.lpSum([x[n][d]['N'] for n in nurses]) == 4
                # 숙련도 1인 간호사 각 조당 최소 1명
                for s in ['D', 'E', 'N']:
                    prob += pulp.lpSum([x[n][d][s] for n in nurses if nurse_skill.get(n) == 1]) >= 1

            for n in nurses:
                for d in days:
                    # 신청 오프(O) 반영
                    if str(df_input.iloc[nurses.index(n), d+1]).upper() == 'O':
                        prob += x[n][d]['OFF'] == 1
                    prob += pulp.lpSum([x[n][d][s] for s in shifts]) == 1

                # 🚫 금지 패턴 (ED, ND, NE 절대 금지)
                for d in range(1, num_days):
                    prob += x[n][d]['E'] + x[n][d+1]['D'] <= 1
                    prob += x[n][d]['N'] + x[n][d+1]['D'] <= 1
                    prob += x[n][d]['N'] + x[n][d+1]['E'] <= 1

                # 💤 나이트 세트 규칙 (2~3연속 권장 및 종료 후 2일 OFF)
                for d in range(1, num_days - 1):
                    # 나이트 종료 후 2일 OFF 보장 (N-OFF-OFF)
                    prob += x[n][d]['N'] - x[n][d+1]['N'] <= x[n][d+1]['OFF']
                    prob += x[n][d]['N'] - x[n][d+1]['N'] <= x[n][d+2]['OFF']

                # 📊 월간 균형 (휴무 10~13일, 나이트 최대 8회)
                prob += pulp.lpSum([x[n][d]['OFF'] for d in days]) >= 10
                prob += pulp.lpSum([x[n][d]['N'] for d in days]) <= 8

            # 계산 실행
            prob.solve(pulp.PULP_CBC_CMD(msg=0))

            if pulp.LpStatus[prob.status] == 'Optimal':
                final_res = []
                for n in nurses:
                    row = {'이름': n}
                    for d in days:
                        for s in shifts:
                            if pulp.value(x[n][d][s]) == 1: row[f'{d}일'] = s
                    final_res.append(row)
                
                st.success("✅ 성공적으로 생성되었습니다!")
                st.dataframe(pd.DataFrame(final_res))
                
                # 엑셀 다운로드 기능
                res_df = pd.DataFrame(final_res)
                csv = res_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("결과 파일 다운로드", data=csv, file_name="final_schedule.csv")
            else:
                st.error("❌ 조건 충돌! 신청 오프가 너무 많아 답을 찾을 수 없습니다.")

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
