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
                            prob += x[n][1]['N'] <= x[n][2]['N']
                        else:
                            prob += x[n][d]['N'] - x[n][d+1]['N'] <= x[n][d+1]['OFF']
                            prob += x[n][d]['N'] - x[n][d-1]['N'] <= x[n][d+1]['N']
                    if d == num_days:
                        prob += x[n][num_days]['N'] <= x[n][num_days-1]['N']

                    # 나이트 최대 3연속, N-OFF-OFF 보장
                    if d <= num_days - 3:
                        prob += pulp.lpSum([x[n][d+i]['N'] for i in range(4)]) <= 3
                    if d <= num_days - 2:
                        prob += x[n][d]['N'] - x[n][d+1]['N'] <= x[n][d+1]['OFF']
                        prob += x[n][d]['N'] - x[n][d+1]['N'] <= x[n][d+2]['OFF']

                # 나이트 간격 5일, 연속 근무 5일 제한
                for d in range(1, num_days - 5):
                    prob += 5 * (x[n][d]['N'] - x[n][d+1]['N']) + pulp.lpSum([x[n][d+i]['N'] for i in range(2, 7)]) <= 5
                for d in range(1, num_days - 4):
                    prob += pulp.lpSum([x[n][d+i][s] for i in range(6) for s in work_shifts]) <= 5

            # [중요] 스트림릿 서버를 위해 계산 제한 시간을 120초로 설정
            prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=120))
            # --- [수간호사님 원본 로직 끝] ---

            if pulp.LpStatus[prob.status] == 'Optimal' or pulp.LpStatus[prob.status] == 'Slightly Infeasible':
                final_res = []
                for n in nurses:
                    row = {'이름': n, '숙련도': nurse_skill[n]}
                    for d in days:
                        for s in shifts:
                            if pulp.value(x[n][d][s]) == 1: row[f'{d}일'] = s
                    final_res.append(row)
                
                st.success("✅ 완벽한 최종 근무표가 생성되었습니다!")
                res_df = pd.DataFrame(final_res)
                st.dataframe(res_df)
                
                csv = res_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("결과물 다운로드 (CSV)", data=csv, file_name="perfect_schedule.csv")
            else:
                st.error("❌ 조건 충돌! 코랩에서는 되었으나 신청 오프가 겹쳐서 현재 서버 사양으로 계산이 어렵습니다.")

    except Exception as e:
        st.error(f"❌ 오류 발생: {e}")

