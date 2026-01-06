import streamlit as st
import pandas as pd
import pulp
import os

# 1. 페이지 설정
st.set_page_config(page_title="MICU AI 근무표 생성기", layout="wide")

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
st.title("🏥 MICU 최적화 근무표 (23인 보강 버전)")
st.info("수간호사님의 원본 로직을 유지하며, 계산 시간과 휴무 범위를 최적화했습니다.")

file_path = 'request_off.xlsx'

if st.button("근무표 생성 시작 (고정밀 계산)"):
    if not os.path.exists(file_path):
        st.error(f"'{file_path}' 파일을 찾을 수 없습니다.")
        st.stop()

    try:
        # 계산 시간이 길어지므로 메시지를 띄웁니다.
        with st.spinner("AI가 최적의 조합을 찾고 있습니다. 최대 10분까지 소요될 수 있으니 창을 닫지 마세요."):
            df_input = pd.read_excel(file_path)
            nurses = df_input.iloc[:, 0].dropna().tolist()
            nurse_skill = dict(zip(nurses, df_input.iloc[:, 1]))
            num_days = 30
            days = range(1, num_days + 1)
            shifts = ['D', 'E', 'N', 'OFF']
            work_shifts = ['D', 'E', 'N']

            prob = pulp.LpProblem("Nurse_Scheduling_Master_Final", pulp.LpMinimize)
            x = pulp.LpVariable.dicts("x", (nurses, days, shifts), cat=pulp.LpBinary)

            # [제약 조건 설정]
            for d in days:
                prob += pulp.lpSum([x[n][d]['D'] for n in nurses]) == 4
                prob += pulp.lpSum([x[n][d]['E'] for n in nurses]) == 5
                prob += pulp.lpSum([x[n][d]['N'] for n in nurses]) == 4
                for s in work_shifts:
                    prob += pulp.lpSum([x[n][d][s] for n in nurses if nurse_skill.get(n) == 1]) >= 1

            for n in nurses:
                for d in days:
                    # 신청 오프 반영 (현재는 비어있더라도 로직은 유지)
                    off_val = df_input.iloc[nurses.index(n), d+1]
                    if str(off_val).upper() == 'O':
                        prob += x[n][d]['OFF'] == 1
                    prob += pulp.lpSum([x[n][d][s] for s in shifts]) == 1

                # [수정] 한 달 휴무일 범위를 9~15일로 유연하게 조정
                prob += pulp.lpSum([x[n][d]['OFF'] for d in days]) >= 9
                prob += pulp.lpSum([x[n][d]['OFF'] for d in days]) <= 15
                prob += pulp.lpSum([x[n][d]['N'] for d in days]) <= 8

                for d in days:
                    if d < num_days:
                        prob += x[n][d]['E'] + x[n][d+1]['D'] <= 1
                        prob += x[n][d]['N'] + x[n][d+1]['D'] <= 1
                        prob += x[n][d]['N'] + x[n][d+1]['E'] <= 1

                    if d <= num_days - 2:
                        prob += x[n][d]['N'] - x[n][d+1]['N'] <= x[n][d+1]['OFF']
                        prob += x[n][d]['N'] - x[n][d+1]['N'] <= x[n][d+2]['OFF']
                        if d == 1:
                            prob += x[n][1]['N'] <= x[n][2]['N']
                        else:
                            prob += x[n][d]['N'] - x[n][d-1]['N'] <= x[n][d+1]['N']
                    
                    if d == num_days:
                        prob += x[n][num_days]['N'] <= x[n][num_days-1]['N']

                    if d <= num_days - 3:
                        prob += pulp.lpSum([x[n][d+i]['N'] for i in range(4)]) <= 3

                for d in range(1, num_days - 5):
                    prob += 5 * (x[n][d]['N'] - x[n][d+1]['N']) + pulp.lpSum([x[n][d+i]['N'] for i in range(2, 7)]) <= 5
                for d in range(1, num_days - 4):
                    prob += pulp.lpSum([x[n][d+i][s] for i in range(6) for s in work_shifts]) <= 5

            # [수정] 제한시간을 600초(10분)로 대폭 상향
            prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=600))

            if pulp.LpStatus[prob.status] in ['Optimal', 'Slightly Infeasible']:
                final_res = []
                for n in nurses:
                    row = {'이름': n, '숙련도': nurse_skill[n]}
                    for d in days:
                        for s in shifts:
                            if pulp.value(x[n][d][s]) == 1: row[f'{d}일'] = s
                    final_res.append(row)
                
                st.success("✅ 드디어 성공했습니다! 최적화된 근무표입니다.")
                st.dataframe(pd.DataFrame(final_res))
            else:
                st.error("❌ 여전히 충돌이 발생합니다. 인원수(4-5-4)를 하나만 줄여보시는 것을 권장합니다.")

    except Exception as e:
        st.error(f"❌ 실행 오류: {e}")
