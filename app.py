import streamlit as st
import pandas as pd
import pulp
import os

# (로그인 부분 생략 - 그대로 유지하세요)

st.title("🏥 MICU 근무표 진단 모드")

file_path = 'request_off.xlsx'
if st.button("진단 시작 (근무표 생성)"):
    if not os.path.exists(file_path):
        st.error("엑셀 파일이 깃허브에 없습니다!")
    else:
        df_input = pd.read_excel(file_path)
        # 여기서 'D'만 나오는 이유를 찾기 위해 로직을 강제로 돌립니다.
        st.write(f"데이터 확인: 총 {len(df_input)}명의 명단을 확인했습니다.")
        
        # ... (중략: 제가 위에 드린 PuLP 로직) ...
        
        prob.solve(pulp.PULP_CBC_CMD(msg=0))
        
        # 상태 확인 (중요!)
        status = pulp.LpStatus[prob.status]
        st.write(f"AI 계산 상태: {status}") # 여기서 'Optimal'이 아니면 에러입니다.
        
        if status == 'Optimal':
            st.success("계산 성공! 표를 그립니다.")
            # 표 그리는 로직...
        else:
            st.error("❌ 계산 실패! 신청 오프가 너무 많거나 조건이 너무 까다롭습니다.")
            st.warning("팁: 엑셀에서 'O' 표시를 몇 개 지우고 다시 해보세요.")
