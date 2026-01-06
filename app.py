import streamlit as st
import pandas as pd
import pulp
import os

# 1. 페이지 설정 및 로그인
st.set_page_config(page_title="MICU AI 근무표 생성기", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🏥 MICU AI 근무표 시스템")
    pw = st.text_input("비밀번호 입력 (1234)", type="password")
    if st.button("로그인"):
        if pw == "1234":
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    st.stop()

# 2. 메인 화면
st.title("🏥 MICU 최적화 근무표 (바탕화면 최종본 로직)")
st.info("코랩에서 검증된 모든 제약 조건(N-OFF-OFF, 5일 간격 등)이 적용되었습니다.")

file_path = 'request_off.xlsx'

if st.button("근무표 생성 시작"):
    if not os.path.exists(file_path):
        st.error(f"'{file_path}' 파일을 찾을 수 없습니다. 엑셀 업로드를 확인해주세요.")
        st.stop()

    try:
        with st.spinner("AI가 최적의 패턴을 계산 중입니다... (약 1분 소요)"):
            # 데이터 로드
            df_input = pd.read_excel(file_path)
            nurses = df_input.iloc[:, 0].dropna().tolist()
            nurse_skill = dict(zip(nurses, df_input.iloc[:, 1]))
            num_days = 30
            days = range(1, num_days + 1)
            shifts = ['D', 'E', 'N', 'OFF']
            work_shifts = ['D', 'E', 'N']

            # 문제 정의
            prob = pulp.LpProblem("Nurse_Scheduling_Master_Final", pulp.LpMinimize)
            x = pulp.LpVariable.dicts("x", (nurses, days, shifts), cat=pulp.LpBinary)

            # [제약 조건 설정]
            for d in days:
                # 1. 일일 인원 고정
                prob += pulp.lpSum([x[n][d]['D'] for n in nurses]) == 4
                prob += pulp.lpSum([x[n][d]['E'] for n in nurses]) == 5
                prob += pulp.lpSum([x[n][d]['N'] for n in nurses]) == 4
                
                # 2. 숙련도 1인 베테랑 최소 1명 포함
                for s in work_shifts:
                    prob += pulp.lpSum([x[n][d][s] for n in nurses if nurse_skill.get(n) == 1]) >= 1

            for n in nurses:
                for d in days:
                    # 3. 신청 오프 반영
                    off_val = df_input.iloc[nurses.index(n), d+1]
                    if str(off_val).upper() == 'O':
                        prob += x[n][d]['OFF'] == 1
                    prob += pulp.lpSum([x[n][d][s] for s in shifts]) == 1

                # 4. 휴무/나이트 총량 제한
                prob += pulp.lpSum([x[n][d]['OFF'] for d in days]) >= 10
                prob += pulp.lpSum([x[n][d]['OFF'] for d in days]) <= 15
                prob += pulp.lpSum([x[n][d]['N'] for d in days]) <= 8

                # 5. 패턴 규칙 및 금지 사항
                for d in days:
                    if d < num_days:
                        prob += x[n][d]['E'] + x[n][d+1]['D'] <= 1
                        prob += x[n][d]['N'] + x[n][d+1]['D'] <= 1
                        prob += x[n][d]['N'] + x[n][d+1]['E'] <= 1

                    # 나이트 세트 규칙 (단독 N 방지 및 N-OFF-OFF)
                    if d <= num_days - 2:
                        prob += x[n][d]['N'] - x[n][d+1]['N'] <= x[n][d+1]['OFF']
                        prob += x[n][d]['N'] - x[n][d+1]['N'] <= x[n][d+2]['OFF']
                        
                        if d == 1:
                            prob += x[n][1]['N'] <= x[n][2]['N']
                        else:
                            prob += x[n][d]['N'] - x[n][d-1]['N'] <= x[n][d+1]['N']
                    
                    if d == num_days:
                        prob += x[n][num_days]['N'] <= x[n][num_days-1]['N']

                    # 4연속 나이트 금지
                    if d <= num_days - 3:
                        prob += pulp.lpSum([x[n][d+i]['N'] for i in range(4)]) <= 3

                # 6. 나이트 간격 5일 & 연속 근무 5일 제한
                for d in range(1, num_days - 5):
                    prob += 5 * (x[n][d]['N'] - x[n][d+1]['N']) + pulp.lpSum([x[n][d+i]['N'] for i in range(2, 7)]) <= 5
                for d in range(1, num_days - 4):
                    prob += pulp.lpSum([x[n][d+i][s] for i in range(6) for s in work_shifts]) <= 5

            # 7. 해결 (시간 제한 120초)
            prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=120))

            if pulp.LpStatus[prob.status] in ['Optimal', 'Slightly Infeasible']:
                final_res = []
                for n in nurses:
                    row = {'이름': n, '숙련도': nurse_skill[n]}
                    for d in days:
                        for s in shifts:
                            if pulp.value(x[n][d][s]) == 1: row[f'{d}일'] = s
                    final_res.append(row)
                
                st.success("✅ 생성이 완료되었습니다!")
                st.dataframe(pd.DataFrame(final_res))
            else:
                st.error("❌ 조건 충돌! 규칙이 너무 까다로워 현재 인원으로 생성이 불가능합니다.")

    except Exception as e:
        st.error(f"❌ 실행 오류: {e}")
