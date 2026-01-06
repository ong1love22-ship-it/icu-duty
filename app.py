import streamlit as st
import pandas as pd

# --- [여기서부터 관리님의 AI 로직(함수)을 붙여넣으세요] ---
def run_duty_ai():
    # 수간호사님이 코랩(Colab)에서 성공하셨던 
    # AI 알고리즘 코드를 이 아래에 그대로 붙여넣으시면 됩니다.
    
    # (예시 데이터: 25명 간호사 이름 생성)
    names = [f"간호사 {i}" for i in range(1, 26)]
    days = [f"{i}일" for i in range(1, 32)]
    df = pd.DataFrame("D", index=names, columns=days)
    return df
# --- [여기까지가 로직 부분입니다] ---

# 웹 화면 구성
st.set_page_config(page_title="MICU AI Duty", layout="wide")
st.title("🏥 우리 중환자실 AI 근무표 시스템")

# 보안을 위한 간단한 비번 (수간호사님만 아는 번호로 수정 가능)
password = st.sidebar.text_input("비밀번호를 입력하세요", type="password")

if password == "1234": # 비번이 1234일 때만 작동
    st.sidebar.success("인증되었습니다.")
    
    st.subheader("🗓️ 이번 달 근무표 생성")
    if st.button("🚀 AI 근무표 생성 시작"):
        with st.spinner('AI가 최적의 조합을 찾는 중입니다...'):
            result_df = run_duty_ai() # AI 실행
            st.success("근무표 생성이 완료되었습니다!")
            st.dataframe(result_df) # 결과 표 보여주기
            
            # 엑셀 다운로드 버튼
            csv = result_df.to_csv().encode('utf-8-sig')
            st.download_button("📥 엑셀로 다운로드", data=csv, file_name='duty.csv')
else:
    st.info("비밀번호를 입력하면 시스템이 활성화됩니다.")