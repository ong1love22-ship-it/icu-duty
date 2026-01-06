import streamlit as st
import pandas as pd
import pulp
import os

# 1. 로그인 세션 관리
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("MICU AI 근무표 시스템")
    password = st.text_input("비밀번호를 입력하세요", type="password")
    if st.button("로그인"):
        if password == "1234":
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    st.stop()

# 2. 메인 화면
st.title("🏥 MICU AI 최적화 근무표 생성기")
st.info("엑셀 파일(request_off.xlsx)의 신청 오프와 숙련도를 기반으로 완벽한 스케줄을 계산합니다.")

# 파일 존재 여부 확인
file_path = 'request_off.xlsx'
if not os.path.exists(file_path):
    st.error(f"'{file_path}' 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
    st.stop()

if st.button("최적화 근무표 생성 시작"):
    try:
        with st.spinner("AI가 수학적 최적화 모델(PuLP)을 가동 중입니다... (약 10~30초 소요)"):
            # --- [수간호사님의 핵심 로직 시작] ---
            df_input = pd.read_excel(file_path)
            nurses = df_input.iloc[:, 0].tolist()
            nurse_skill = dict(zip(nurses, df_input.iloc[:, 1]))
            num_days = 30
            days = range(1, num_days + 1)
            shifts = ['D', 'E', 'N', 'OFF']
            work_shifts = ['D', 'E', 'N']

            prob = pulp.LpProblem("Nurse_Scheduling_Master", pulp.LpMinimize)
            x = pulp.LpVariable.dicts("x", (nurses, days, shifts), cat=pulp.LpBinary)

            # [제약 조건들]
            for d in days:
                prob += pulp.lpSum([x[n][d]['D'] for n in nurses]) == 4
                prob += pulp.lpSum([x[n][d]['E'] for n in nurses]) == 5
                prob += pulp.lpSum([x[n][d]['N'] for n in nurses]) == 4
                for s in work_shifts:
                    prob += pulp.lpSum([x[n][d][s] for n in nurses if nurse_skill[n] == 1]) >= 1

            for n in nurses:
                for d in days:
                    # 엑셀 오프 반영 (d+1은 엑셀 열 위치에 따라 조정 필요할 수 있음)
                    if df_input.iloc[nurses.index(n), d+1] == 'O':
                        prob += x[n][d]['OFF'] == 1
                    prob += pulp.lpSum([x[n][d][s] for s in shifts]) == 1

                prob += pulp.lpSum([x[n][d]['OFF'] for d in days]) >= 10
                prob += pulp.lpSum([x[n][d]['OFF'] for d in days]) <= 15
                prob += pulp.lpSum([x[n][d]['N'] for d in days]) <= 8

                for d in days:
                    if d < num_days:
                        prob += x[n][d]['E'] + x[n][d+1]['D'] <= 1
                        prob += x[n][d]['N'] + x[n][d+1]['D'] <= 1
                        prob += x[n][d]['N'] + x[n][d+1]['E'] <= 1
                    
                    # 나이트 관련 상세 로직
                    if d <= num_days - 2:
                        prob += x[n][d]['N'] - x[n][d+1]['N'] <= x[n][d+2]['OFF']

            # 문제 해결
            prob.solve(pulp.PULP_CBC_CMD(msg=0))

            if pulp.LpStatus[prob.status] == 'Optimal':
                final_res = []
                for n in nurses:
                    row = {'이름': n, '숙련도': nurse_skill[n]}
                    for d in days:
                        for s in shifts:
                            if pulp.value(x[n][d][s]) == 1: row[f'{d}일'] = s
                    final_res.append(row)
                
                output_df = pd.DataFrame(final_res)
                st.success("✅ 완벽한 최종 근무표가 생성되었습니다!")
                st.dataframe(output_df) # 화면에 표 출력
                
                # 엑셀 다운로드
                csv = output_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("결과물 다운로드 (CSV)", data=csv, file_name="final_schedule.csv")
            else:
                st.error("❌ 조건 충돌! 신청 오프가 너무 많거나 제약 조건이 너무 까다롭습니다.")
            # --- [수간호사님의 핵심 로직 끝] ---

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
