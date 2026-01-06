import streamlit as st
import pandas as pd
import pulp
import os

st.set_page_config(page_title="MICU 근무표", layout="wide")
st.title("🏥 MICU AI 근무표 (패턴 최적화 버전)")

# (비밀번호 부분은 동일하므로 생략 - 기존 코드 유지)

file_path = 'request_off.xlsx'
if st.button("최적화 근무표 생성 시작"):
    try:
        with st.spinner("전문가급 패턴으로 스케줄을 조정 중입니다..."):
            df_input = pd.read_excel(file_path)
            nurses = df_input.iloc[:, 0].dropna().tolist()
            skill = dict(zip(nurses, df_input.iloc[:, 1]))
            
            days = range(1, 31)
            shifts = ['D', 'E', 'N', 'OFF']
            
            prob = pulp.LpProblem("Nurse_Optimization", pulp.LpMinimize)
            x = pulp.LpVariable.dicts("x", (nurses, days, shifts), cat=pulp.LpBinary)

            for d in days:
                # 1. 일일 투입 인원 고정 (4, 5, 4명)
                prob += pulp.lpSum([x[n][d]['D'] for n in nurses]) == 4
                prob += pulp.lpSum([x[n][d]['E'] for n in nurses]) == 5
                prob += pulp.lpSum([x[n][d]['N'] for n in nurses]) == 4
                # 숙련도 1인 베테랑 각 조에 1명 이상 배치
                for s in ['D', 'E', 'N']:
                    prob += pulp.lpSum([x[n][d][s] for n in nurses if skill.get(n) == 1]) >= 1

            for n in nurses:
                for d in days:
                    prob += pulp.lpSum([x[n][d][s] for s in shifts]) == 1
                    
                    # 2. 절대 금지 패턴 (ND, NE, ED)
                    if d < 30:
                        prob += x[n][d]['N'] + x[n][d+1]['D'] <= 1
                        prob += x[n][d]['N'] + x[n][d+1]['E'] <= 1
                        prob += x[n][d]['E'] + x[n][d+1]['D'] <= 1

                    # 3. 나이트 세트 종료 후 2일 OFF 보장
                    if d <= 28:
                        prob += x[n][d]['N'] - x[n][d+1]['N'] <= x[n][d+2]['OFF']
                        prob += x[n][d]['N'] - x[n][d+1]['N'] <= x[n][d+1]['OFF'] # N 다음 바로 OFF

                # 4. 나이트 최소 2연속 이상 (단독 나이트 방지)
                for d in range(1, 30):
                    if d == 1:
                        prob += x[n][1]['N'] <= x[n][2]['N']
                    elif d == 30:
                        prob += x[n][30]['N'] <= x[n][29]['N']
                    else:
                        prob += x[n][d]['N'] <= x[n][d-1]['N'] + x[n][d+1]['N']

                # 5. 한 달 전체 휴무(10~13일) 및 나이트(6~8회) 균형
                prob += pulp.lpSum([x[n][d]['OFF'] for d in days]) >= 10
                prob += pulp.lpSum([x[n][d]['N'] for d in days]) <= 8

            # 계산 실행
            prob.solve(pulp.PULP_CBC_CMD(msg=0))
            
            if pulp.LpStatus[prob.status] == 'Optimal':
                res = []
                for n in nurses:
                    row = {'이름': n}
                    for d in days:
                        for s in shifts:
                            if pulp.value(x[n][d][s]) == 1:
                                row[f"{d}일"] = s
                    res.append(row)
                
                st.success("✅ 간호부 규칙이 모두 적용된 근무표입니다!")
                st.dataframe(pd.DataFrame(res))
            else:
                st.error("❌ 모든 규칙을 만족하는 답이 없습니다. 규칙을 조금만 더 풀어볼까요?")

    except Exception as e:
        st.error(f"오류 발생: {e}")
