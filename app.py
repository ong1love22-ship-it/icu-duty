import streamlit as st
import pandas as pd
import pulp
import os

st.set_page_config(page_title="MICU 근무표", layout="wide")
st.title("🏥 MICU AI 근무표 (최종 복구 버전)")

# 1. 비밀번호 확인
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    pw = st.text_input("비밀번호 (1234)", type="password")
    if st.button("로그인"):
        if pw == "1234":
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    st.stop()

# 2. 파일 로드 및 확인
file_path = 'request_off.xlsx'
if not os.path.exists(file_path):
    st.error(f"❌ '{file_path}' 파일이 깃허브에 없습니다! 파일을 먼저 올려주세요.")
    st.stop()

# 3. 근무표 생성 로직
if st.button("근무표 생성 시작"):
    try:
        df_input = pd.read_excel(file_path)
        nurses = df_input.iloc[:, 0].dropna().tolist()
        skill = dict(zip(nurses, df_input.iloc[:, 1]))
        
        days = range(1, 31)
        shifts = ['D', 'E', 'N', 'OFF']
        
        # 문제 정의
        prob = pulp.LpProblem("Nurse_Schedule", pulp.LpMinimize)
        x = pulp.LpVariable.dicts("x", (nurses, days, shifts), cat=pulp.LpBinary)

        # [제약조건] 가장 필수적인 것만 남기고 다 풀었습니다 (작동 확인용)
        for d in days:
            prob += pulp.lpSum([x[n][d]['D'] for n in nurses]) == 4
            prob += pulp.lpSum([x[n][d]['E'] for n in nurses]) == 5
            prob += pulp.lpSum([x[n][d]['N'] for n in nurses]) == 4

        for n in nurses:
            for d in days:
                prob += pulp.lpSum([x[n][d][s] for s in shifts]) == 1
                # 나이트-데이 금지만 남김
                if d < 30:
                    prob += x[n][d]['N'] + x[n][d+1]['D'] <= 1

        # 계산 실행
        status = prob.solve(pulp.PULP_CBC_CMD(msg=0))
        
        if pulp.LpStatus[status] == 'Optimal':
            res = []
            for n in nurses:
                row = {'이름': n}
                for d in days:
                    for s in shifts:
                        if pulp.value(x[n][d][s]) == 1:
                            row[f"{d}일"] = s
                res.append(row)
            
            final_df = pd.DataFrame(res)
            st.success("✅ 근무표 생성에 성공했습니다!")
            st.dataframe(final_df)
        else:
            st.error(f"❌ AI가 답을 못 찾음 (상태: {pulp.LpStatus[status]})")
            st.warning("팁: 근무 인원(4,5,4)을 조정하거나 제약을 더 풀어야 합니다.")

    except Exception as e:
        st.error(f"⚠️ 시스템 오류 발생: {e}")
        st.info("이 에러가 뜨면 'requirements.txt'에 pulp, openpyxl이 있는지 확인하세요.")
