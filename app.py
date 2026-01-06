import streamlit as st
import pandas as pd
import pulp
import os

st.set_page_config(page_title="MICU AI 근무표", layout="wide")

# ... (로그인 부분 생략 - 기존 코드 유지) ...

if st.button("23인 맞춤형 로직으로 재생성"):
    try:
        with st.spinner("23명 인원에 맞춰 규칙을 미세 조정하며 계산 중입니다 (최대 10분)..."):
            df_input = pd.read_excel('request_off.xlsx')
            nurses = df_input.iloc[:, 0].dropna().tolist()
            nurse_skill = dict(zip(nurses, df_input.iloc[:, 1]))
            num_days, days, shifts = 30, range(1, 31), ['D', 'E', 'N', 'OFF']
            work_shifts = ['D', 'E', 'N']

            prob = pulp.LpProblem("MICU_Final_Adjusted", pulp.LpMinimize)
            x = pulp.LpVariable.dicts("x", (nurses, days, shifts), cat=pulp.LpBinary)

            for d in days:
                prob += pulp.lpSum([x[n][d]['D'] for n in nurses]) == 4
                prob += pulp.lpSum([x[n][d]['E'] for n in nurses]) == 5
                prob += pulp.lpSum([x[n][d]['N'] for n in nurses]) == 4
                for s in work_shifts:
                    prob += pulp.lpSum([x[n][d][s] for n in nurses if nurse_skill.get(n) == 1]) >= 1

            for n in nurses:
                # [조정] 휴무 최소 9일, 나이트 최대 9회로 23인 현실 반영
                prob += pulp.lpSum([x[n][d]['OFF'] for d in days]) >= 9
                prob += pulp.lpSum([x[n][d]['N'] for d in days]) <= 9
                
                for d in days:
                    prob += pulp.lpSum([x[n][d][s] for s in shifts]) == 1
                    if d < 30: # 금지 패턴
                        prob += x[n][d]['E'] + x[n][d+1]['D'] <= 1
                        prob += x[n][d]['N'] + x[n][d+1]['D'] <= 1
                        prob += x[n][d]['N'] + x[n][d+1]['E'] <= 1
                    
                    if d <= 28: # N-OFF-OFF
                        prob += x[n][d]['N'] - x[n][d+1]['N'] <= x[n][d+1]['OFF']
                        prob += x[n][d]['N'] - x[n][d+1]['N'] <= x[n][d+2]['OFF']

                # [조정] 나이트 간격 5일 -> 4일로 살짝 완화 (23명 인원 맞춤)
                for d in range(1, 26):
                    prob += 4 * (x[n][d]['N'] - x[n][d+1]['N']) + pulp.lpSum([x[n][d+i]['N'] for i in range(2, 6)]) <= 4

                for d in range(1, 26): # 연속 근무 5일 제한
                    prob += pulp.lpSum([x[n][d+i][s] for i in range(6) for s in work_shifts]) <= 5

            prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=600))

            if pulp.LpStatus[prob.status] in ['Optimal', 'Slightly Infeasible']:
                # ... (결과 출력 로직 동일) ...
                st.success("✅ 드디어 성공했습니다!")
            else:
                st.error("❌ 여전히 충돌이 납니다. 일일 근무 인원(4-5-4) 중 한 명을 줄여야 할 것 같습니다.")
