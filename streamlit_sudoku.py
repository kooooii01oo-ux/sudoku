# -*- coding: utf-8 -*-
"""
실습#5 : PyQt5 수도쿠(실습#3)를 streamlit 버전으로 개발
 - 데코레이터 : @st.cache_data, @st.fragment
 - 전역변수   : st.session_state
 - secrets   : st.secrets (관리자 비밀번호)
실행 : streamlit run streamlit_sudoku.py
"""
import random
import time
import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Streamlit 수도쿠", page_icon="🧩", layout="centered")

RANK_FILE = Path("ranking.csv")


# ---------------------------------------------------------------
# 1. secrets : 관리자 비밀번호는 코드에 쓰지 않고 secrets.toml에서 가져온다
# ---------------------------------------------------------------
def get_secret(key, default=""):
    try:
        return st.secrets[key]
    except Exception:          # secrets.toml이 없거나 key가 없을 때
        return default


ADMIN_PW = get_secret("ADMIN_PASSWORD")


# ---------------------------------------------------------------
# 2. 수도쿠 생성 로직 (백트래킹)
# ---------------------------------------------------------------
def is_valid(board, r, c, v):
    for i in range(9):
        if board[r][i] == v or board[i][c] == v:
            return False
    br, bc = r // 3 * 3, c // 3 * 3
    for i in range(3):
        for j in range(3):
            if board[br + i][bc + j] == v:
                return False
    return True


def fill_board(board, rng):
    for r in range(9):
        for c in range(9):
            if board[r][c] == 0:
                nums = list(range(1, 10))
                rng.shuffle(nums)
                for v in nums:
                    if is_valid(board, r, c, v):
                        board[r][c] = v
                        if fill_board(board, rng):
                            return True
                        board[r][c] = 0
                return False
    return True


@st.cache_data
def make_solution(seed):
    """정답판 생성. 클릭할 때마다 rerun 되어도 같은 seed면 다시 계산하지 않고 캐시에서 가져온다."""
    rng = random.Random(seed)
    board = [[0] * 9 for _ in range(9)]
    fill_board(board, rng)
    return board


def make_puzzle(solution, fill_ratio, seed):
    """채움 비율 0.7 -> 행당 빈칸 3개, 0.9 -> 행당 빈칸 1개 (실습#3과 동일한 규칙)"""
    rng = random.Random(seed + 1)
    blanks = round((1 - fill_ratio) * 9)
    puzzle = [row[:] for row in solution]
    for r in range(9):
        for c in rng.sample(range(9), blanks):
            puzzle[r][c] = 0
    return puzzle


# ---------------------------------------------------------------
# 3. 등수 기록 (ranking.csv) : 읽기는 캐시, 저장하면 캐시 비우기
# ---------------------------------------------------------------
@st.cache_data
def load_ranking():
    if RANK_FILE.exists():
        return pd.read_csv(RANK_FILE)
    return pd.DataFrame(columns=["name", "seconds", "fill_ratio", "date"])


def save_record(name, seconds, fill_ratio):
    df = load_ranking()
    new = pd.DataFrame([{
        "name": name,
        "seconds": round(seconds, 1),
        "fill_ratio": fill_ratio,
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }])
    pd.concat([df, new], ignore_index=True).to_csv(RANK_FILE, index=False)
    load_ranking.clear()       # 파일이 바뀌었으니 캐시 삭제


# ---------------------------------------------------------------
# 4. session_state : 전역변수처럼 rerun 사이에 값을 유지
# ---------------------------------------------------------------
def new_game():
    seed = random.randrange(10 ** 9)
    ratio = st.session_state.get("fill_ratio", 0.7)
    solution = make_solution(seed)
    st.session_state.game_id = st.session_state.get("game_id", 0) + 1
    st.session_state.solution = solution
    st.session_state.puzzle = make_puzzle(solution, ratio, seed)
    st.session_state.game_ratio = ratio
    st.session_state.start_time = time.time()
    st.session_state.finished = False
    st.session_state.elapsed = 0.0


# ---------------------------------------------------------------
# 5. 타이머 : @st.fragment 로 이 부분만 1초마다 다시 실행
#    (전체 코드를 rerun 하면 랙이 생기므로)
# ---------------------------------------------------------------
@st.fragment(run_every="1s")
def timer_view():
    if st.session_state.finished:
        sec = st.session_state.elapsed
    else:
        sec = time.time() - st.session_state.start_time
    m, s = divmod(int(sec), 60)
    st.metric("⏱️ 경과 시간", f"{m:02d}:{s:02d}")


# ---------------------------------------------------------------
# 6. 화면 구성
# ---------------------------------------------------------------
st.title("🧩 Streamlit 수도쿠")

with st.sidebar:
    st.header("설정")
    st.text_input("이름", key="player", placeholder="등수 기록에 사용")
    st.slider("채움 비율", 0.5, 0.9, 0.7, 0.1, key="fill_ratio",
              help="0.7이면 행마다 빈칸 3개, 0.9면 빈칸 1개")
    st.button("🔄 새 게임", on_click=new_game, use_container_width=True)

    st.divider()
    st.subheader("관리자")
    pw = st.text_input("비밀번호", type="password", key="admin_pw")
    if not ADMIN_PW:
        st.caption("secrets.toml 에 ADMIN_PASSWORD 가 설정되지 않았습니다.")
    elif pw == ADMIN_PW:
        if st.button("🗑️ 등수 기록 초기화"):
            RANK_FILE.unlink(missing_ok=True)
            load_ranking.clear()
            st.success("등수 기록을 초기화했습니다.")
    elif pw:
        st.error("비밀번호가 틀렸습니다.")

if "puzzle" not in st.session_state:
    new_game()

puzzle = st.session_state.puzzle
solution = st.session_state.solution
gid = st.session_state.game_id

timer_view()

# 폼으로 묶으면 칸을 입력할 때마다 rerun 되지 않고 [제출]을 눌렀을 때만 실행된다.
with st.form("board_form"):
    for r in range(9):
        cols = st.columns(9)
        for c in range(9):
            if puzzle[r][c]:
                cols[c].text_input(f"fix{r}{c}", value=str(puzzle[r][c]), disabled=True,
                                   key=f"g{gid}_{r}_{c}_fix", label_visibility="collapsed")
            else:
                cols[c].text_input(f"in{r}{c}", max_chars=1, key=f"g{gid}_{r}_{c}",
                                   label_visibility="collapsed")
        if r in (2, 5):
            st.divider()
    submitted = st.form_submit_button("✅ 제출", use_container_width=True)

if submitted and not st.session_state.finished:
    wrong = empty = 0
    for r in range(9):
        for c in range(9):
            if puzzle[r][c] == 0:
                raw = st.session_state.get(f"g{gid}_{r}_{c}", "").strip()
                if raw == "":
                    empty += 1
                elif not raw.isdigit() or int(raw) != solution[r][c]:
                    wrong += 1

    if empty or wrong:
        st.warning(f"아직 완성되지 않았어요. 빈칸 {empty}개, 틀린 칸 {wrong}개")
    else:
        st.session_state.finished = True
        st.session_state.elapsed = time.time() - st.session_state.start_time
        name = st.session_state.get("player", "").strip() or "익명"
        save_record(name, st.session_state.elapsed, st.session_state.game_ratio)
        st.balloons()
        st.success(f"🎉 {name}님 완료! 기록: {st.session_state.elapsed:.1f}초")

if st.session_state.finished:
    st.info("게임이 끝났어요. 사이드바의 [새 게임]을 눌러 다시 도전하세요.")

# ---------------------------------------------------------------
# 7. 등수 표시 (현재 난이도 기준)
# ---------------------------------------------------------------
st.subheader(f"🏆 등수 (채움 비율 {st.session_state.game_ratio})")
rank = load_ranking()
rank = rank[rank["fill_ratio"].round(1) == round(st.session_state.game_ratio, 1)]
if rank.empty:
    st.caption("아직 기록이 없습니다.")
else:
    rank = rank.sort_values("seconds").head(10).reset_index(drop=True)
    rank.index = rank.index + 1
    rank.index.name = "등수"
    st.dataframe(rank[["name", "seconds", "date"]].rename(
        columns={"name": "이름", "seconds": "시간(초)", "date": "날짜"}))
