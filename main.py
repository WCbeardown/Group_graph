import streamlit as st
import numpy as np 
import pandas as pd
import datetime 
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import re
import unicodedata

st.set_page_config(layout="wide")
st.title("羽曳野大会レイティンググループのグラフ")

# --- 共通：既存データ読み込み ---
rating_data = pd.read_csv("rating_data_all.csv", index_col=0)
rating_data["日付"] = pd.to_datetime(rating_data["日付"].astype(str).str.replace("/", "-"), errors="coerce")
rating_data = rating_data.sort_values("日付")
try:
    last = rating_data["日付"].dropna().tail(1).item()
    last_display = last.strftime('%Y-%m-%d')
    latest_year = last.year
except Exception:
    last_display = "不明"
    latest_year = datetime.datetime.now().year

st.write('最終更新日：', last_display)
st.write('使い方：写真をGoogleレンズでテキスト読み込みした文字列を下の欄に貼り付けてください（番号 会員番号 氏名 レイティングの順）')

# --- ペースト入力（修正版） ---

# session_state の初期化
if "pasted_text" not in st.session_state:
    st.session_state["pasted_text"] = ""

# text_area に初期値をセット
#text_input = st.text_area("参加者リストを貼り付け", value=st.session_state["pasted_text"], height=240)

# 入力欄
text_input = st.text_area("参加者リストを貼り付け", value=st.session_state["pasted_text"], height=240, key="input_text")
# 入力を確定するボタン
if st.button("ペースト完了"):
    st.session_state["confirmed_text"] = st.session_state["input_text"]
    st.write("入力を確定しました:", st.session_state["confirmed_text"])


# ボタン
#if st.button("ペースト完了"):
    st.session_state["pasted_text"] = text_input

# 貼り付け内容を取得
pasted_text = st.session_state["pasted_text"]



# ---------------- ヘルパー関数（省略せず全部入れています） ----------------
def parse_candidate_number(num: str):
    try:
        if len(num) >= 8:
            return int(num[-7:])
        if len(num) == 7 or (len(num) == 6 and num.startswith("9")):
            return int(num)
    except:
        return None
    return None

def lookup_points(abs_diff):
    table = [
        (0, 12,  8, 8),
        (13,37,  7,10),
        (38,62,  6,13),
        (63,87,  5,16),
        (88,112, 4,20),
        (113,137,3,25),
        (138,162,2,30),
        (163,187,2,35),
        (188,212,1,40),
        (213,237,1,45),
        (238,99999,0,50),
    ]
    for lo, hi, high_pt, low_pt in table:
        if lo <= abs_diff <= hi:
            return high_pt, low_pt
    return 0, 0

def parse_member_table(text: str):
    if not isinstance(text, str):
        return pd.DataFrame(columns=["番号","会員番号","氏名","レイティング"])
    text = unicodedata.normalize("NFKC", text)
    raw_lines = [ln.strip() for ln in text.splitlines()]
    skip_keywords = set(["会員番号", "氏名", "R", "A6ブロック", "(コート)"])
    lines = [ln for ln in raw_lines if ln != "" and ln not in skip_keywords]

    results = []
    used_members = set()
    i = 0
    while i < len(lines):
        if re.fullmatch(r'^\d{6,}$', lines[i]):
            member = parse_candidate_number(lines[i])
            name = None
            rating_val = None
            if i+1 < len(lines):
                name = lines[i+1].strip()
            if i+2 < len(lines):
                rt = lines[i+2].strip()
                if rt.isdigit():
                    rating_val = int(rt)
                elif rt == "初":
                    rating_val = "初"
            if member is not None and member not in used_members:
                results.append({
                    "会員番号": member,
                    "氏名": name if name else "不明",
                    "レイティング": rating_val if rating_val is not None else 0
                })
                used_members.add(member)
            i += 3
        else:
            i += 1

    if not results:
        return pd.DataFrame(columns=["番号","会員番号","氏名","レイティング"])
    df = pd.DataFrame(results)
    df = df.drop_duplicates(subset=["会員番号"], keep="first").reset_index(drop=True)
    df.insert(0, "番号", range(1, len(df) + 1))
    df["レイティング_num"] = pd.to_numeric(df["レイティング"], errors="coerce")
    return df

def extract_name_dict(text: str):
    if not isinstance(text, str):
        return {}
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'[\u200E\u200F\u202A-\u202E]', '', text)
    lines = [ln.strip() for ln in text.splitlines()]
    name_dict = {}
    for i, line in enumerate(lines):
        if not line:
            continue
        m = re.search(r'(\d+)\s*([^\d].+)$', line)
        if m:
            num = m.group(1)
            raw_name = m.group(2).strip()
            try:
                if len(num) >= 8:
                    kid = int(num[-7:])
                elif len(num) == 7 or (len(num) == 6 and num.startswith("9")):
                    kid = int(num)
                else:
                    kid = None
            except:
                kid = None
            if kid is not None and raw_name:
                name_dict[kid] = raw_name
                continue
        nums = re.findall(r'\d+', line)
        for num in nums:
            try:
                if len(num) >= 8:
                    kid = int(num[-7:])
                elif len(num) == 7 or (len(num) == 6 and num.startswith("9")):
                    kid = int(num)
                else:
                    kid = None
            except:
                kid = None
            if kid is None:
                continue
            name = None
            for j in range(i+1, min(i+4, len(lines))):
                nl = lines[j].strip()
                if not nl:
                    continue
                if re.fullmatch(r'\d+', nl):
                    continue
                name = nl
                break
            if name:
                name_dict[kid] = name
    return name_dict

# ---------------- メイン表示（表） ----------------
df_members = parse_member_table(pasted_text) if pasted_text else pd.DataFrame(columns=["番号","会員番号","氏名","レイティング","レイティング_num"])

if df_members.empty:
    st.info("参加者情報が見つかりません。ペーストして「ペースト完了」を押してください。")
else:
    numeric_ratings = df_members["レイティング_num"].dropna()
    if not numeric_ratings.empty:
        min_rating = int(numeric_ratings.min())
        df_members.loc[df_members["レイティング"].astype(str) == "初", "レイティング_num"] = min_rating
        df_members.loc[df_members["レイティング"].astype(str) == "初", "レイティング"] = df_members["レイティング"].apply(
            lambda x: f"初({min_rating})" if x == "初" else x
        )

    st.subheader("現在のレイティング一覧（貼り付けから抽出）")
    st.table(df_members[["番号","会員番号","氏名","レイティング"]])

    # --- 修正済み: options を明確に作り、session_state を widget 前に初期化する ---
    options_ids = list(df_members["会員番号"].astype(int))
    if options_ids:
        # widget を作る前に session_state[target_id] を初期化（かつ有効な選択肢であることを保証）
        if "target_id" not in st.session_state or st.session_state.get("target_id") not in options_ids:
            st.session_state["target_id"] = options_ids[0]

        def fmt_member(x):
            row = df_members[df_members["会員番号"] == x]
            if not row.empty:
                return f"{row['氏名'].iloc[0]}"
            return str(x)

        st.write("基準選手を選択してください")
        default_index = options_ids.index(st.session_state["target_id"])
        # widget を作成（ここで session_state["target_id"] が自動で更新される）
        target_id = st.radio("基準選手", options=options_ids, index=default_index, format_func=fmt_member, key="target_id")
        # 重要: ここで st.session_state["target_id"] を上書きしない（Streamlitの制約）
        # 以降は st.session_state["target_id"] を参照してください

        base_rating = int(df_members[df_members["会員番号"] == st.session_state["target_id"]]["レイティング_num"].iloc[0])

        # ヘッダ
        cols_head = st.columns([2, 4, 2, 2, 2, 2])
        cols_head[0].markdown("**会員番号**")
        cols_head[1].markdown("**氏名**")
        cols_head[2].markdown("**レイティング**")
        cols_head[3].markdown("**差**")
        cols_head[4].markdown("**勝敗**")
        cols_head[5].markdown("**増減**")

        total_change = 0
        rows_out = []
        for _, row in df_members.iterrows():
            kid = int(row["会員番号"])
            name = row["氏名"]
            rating_val_raw = row["レイティング"]
            rating_val = int(row["レイティング_num"])
            signed_diff = base_rating - rating_val
            abs_diff = abs(base_rating - rating_val)

            c1, c2, c3, c4, c5, c6 = st.columns([2, 4, 2, 2, 2, 2])
            with c1:
                st.write(kid)
            with c2:
                st.write(name)
            with c3:
                st.write(rating_val_raw)
            with c4:
                st.write(signed_diff)

            chk_key = f"chk_{st.session_state['target_id']}_{kid}"
            with c5:
                if chk_key in st.session_state:
                    checked = st.checkbox("", key=chk_key)
                else:
                    checked = st.checkbox("", value=True, key=chk_key)

            if kid == st.session_state["target_id"]:
                change = "ー"
            else:
                high_pt, low_pt = lookup_points(abs_diff)
                if base_rating >= rating_val:
                    change = high_pt if st.session_state.get(chk_key, True) else -low_pt
                else:
                    change = low_pt if st.session_state.get(chk_key, True) else -high_pt

            with c6:
                st.write(change)

            if isinstance(change, int):
                total_change += change

            rows_out.append({
                "会員番号": kid,
                "氏名": name,
                "レイティング": rating_val_raw,
                "差(基準-相手)": signed_diff,
                "勝敗": "勝ち" if st.session_state.get(chk_key, True) else "負け",
                "増減": change
            })

        base_name = df_members[df_members["会員番号"] == st.session_state["target_id"]]["氏名"].iloc[0]
        st.markdown(f"**基準選手（{base_name} の増減合計）:** {total_change}")
        base_rating_now = int(df_members[df_members["会員番号"] == st.session_state["target_id"]]["レイティング_num"].iloc[0])
        st.markdown(f"**基準選手の最終レイティング（仮）:** {base_rating_now + total_change}")

        df_results = pd.DataFrame(rows_out)
        st.subheader("対戦一覧（基準視点）")
        st.dataframe(df_results)

# 以下、グラフ描画やサイドバー設定などは先の統合版と同様に実装してください。
# （必要ならこのまま完全版を再掲します）


# ---------------- サイドバー（グラフ年範囲） ----------------
year_s = st.sidebar.number_input("開始年", 2000, 2040, 2019)
year_l = st.sidebar.number_input("終了年", 2000, 2040, latest_year)

st.sidebar.write("※開始年/終了年はグラフの表示範囲です")

# ---------------- グラフ描画ボタン（表の下に表示されるように） ----------------
# グラフ描画ボタン
if st.button("グラフ描画"):
    if "confirmed_text" in st.session_state:

    #if st.button("グラフ描画"):
        # 優先：parse_member_table で抽出された df_members の会員を使う（最大7人）
        kaiin = []
        name_dict = {}

        if not df_members.empty:
            # df_members にある会員番号を上から最大7件採用
            try:
                kaiin = list(df_members["会員番号"].astype(int))[:7]
                # name_dict も構築
                for _, r in df_members.iterrows():
                    try:
                        kid = int(r["会員番号"])
                        name_dict[kid] = r["氏名"]
                    except:
                        continue
            except Exception:
                kaiin = []

        # fallback: 二つ目のコードの抽出方式を使って会員番号を探す（テキストに "1234 name" 形式があれば）
        if not kaiin and pasted_text:
            name_dict = extract_name_dict(pasted_text)
            kaiin = list(name_dict.keys())[:7]

        # グラフ用に rating_data をコピーして氏名を反映
        rd = rating_data.copy()
        try:
            rd["会員番号"] = rd["会員番号"].astype(int)
        except:
            pass
        # 既に name_dict に含まれる名前を反映（ファイルのデータに存在する会員の氏名更新）
        if name_dict:
            for kid, nm in name_dict.items():
                rd.loc[rd["会員番号"] == kid, "氏名"] = nm

        if not kaiin:
            st.warning("グラフに使用する会員が抽出できませんでした。貼り付けテキストの形式を確認してください。")
        else:
            # 会員ごとのデータ
            rating_list = []
            for kid in kaiin:
                df_k = rd[rd["会員番号"] == kid].sort_values("日付")
                rating_list.append(df_k)

            # グラフ描画
            fig, ax = plt.subplots()
            colorlist = ["r", "g", "b", "c", "m", "y", "k"]

            for j, df_k in enumerate(rating_list):
                date = df_k["日付"]
                ax.plot(date, df_k["レイティング"], marker="o", linestyle="solid",
                        label=str(kaiin[j]),  # ★ 凡例を会員番号に
                        color=colorlist[j % len(colorlist)])

            # 軽微なスタイル設定（ggplot は描画前に使うのが好ましいが最低限の設定）
            plt.rcParams["font.size"] = 12
            ax.set_title("Rating Graph", fontsize=18)
            ax.set_xlabel("date", fontsize=14)
            ax.set_ylabel("Rating", fontsize=14)
            ax.legend(loc="upper left", fontsize=10)
            fig.set_figheight(6)
            fig.set_figwidth(12)

            dates = mdates.YearLocator()
            dates_fmt = mdates.DateFormatter('%Y')
            ax.xaxis.set_major_locator(dates)
            ax.xaxis.set_major_formatter(dates_fmt)
            try:
                ax.set_xlim([datetime.datetime(year_s, 1, 1), datetime.datetime(year_l, 12, 31)])
            except Exception:
                pass
            ax.grid(which="major", axis="x", alpha=0.6, linestyle="--", linewidth=1)
            ax.grid(which="major", axis="y", alpha=0.6, linestyle="--", linewidth=1)
            st.pyplot(fig)

            # 年平均まとめ
            st.write('レイティング　年平均比較表')
            matome = ["会員番号", "氏名"] + list(range(year_s, year_l + 1))
            temp = []
            for j, df_k in enumerate(rating_list):
                nen_heikin = [kaiin[j], name_dict.get(kaiin[j], rd.loc[rd["会員番号"] == kaiin[j], "氏名"].iat[0] if not name_dict.get(kaiin[j]) and not rd.loc[rd["会員番号"] == kaiin[j], "氏名"].empty else name_dict.get(kaiin[j], "不明"))]
                for k in range(year_s, year_l + 1):
                    try:
                        nen_heikin.append(int(df_k[pd.DatetimeIndex(df_k["日付"]).year == k]["レイティング"].mean()))
                    except:
                        nen_heikin.append(0)
                temp.append(nen_heikin)
            nen_heikin_matome = pd.DataFrame(temp, columns=matome)
            st.dataframe(nen_heikin_matome)

            # 分析まとめ
            st.write('分析データ')
            stats = []
            for j, df_k in enumerate(rating_list):
                agaru = 0
                sagaru = 0
                agaruhi = pd.NaT
                sagaruhi = pd.NaT
                for i in range(len(df_k) - 1):
                    try:
                        diff = int(df_k["レイティング"].iloc[i+1]) - int(df_k["レイティング"].iloc[i])
                    except Exception:
                        continue
                    if diff > agaru:
                        agaru = diff
                        agaruhi = df_k["日付"].iloc[i+1]
                    if diff < sagaru:
                        sagaru = diff
                        sagaruhi = df_k["日付"].iloc[i+1]
                if len(df_k) > 0:
                    try:
                        min_val = int(df_k["レイティング"].min())
                        min_date = df_k[df_k["レイティング"] == df_k["レイティング"].min()]["日付"].iloc[0]
                    except:
                        min_val = 0
                        min_date = pd.NaT
                    try:
                        max_val = int(df_k["レイティング"].max())
                        max_date = df_k[df_k["レイティング"] == df_k["レイティング"].max()]["日付"].iloc[0]
                    except:
                        max_val = 0
                        max_date = pd.NaT
                    temp = [
                        kaiin[j],
                        name_dict.get(kaiin[j], rd.loc[rd["会員番号"] == kaiin[j], "氏名"].iat[0] if not name_dict.get(kaiin[j]) and not rd.loc[rd["会員番号"] == kaiin[j], "氏名"].empty else "不明"),
                        len(df_k),
                        min_val,
                        min_date,
                        max_val,
                        max_date,
                        agaru, agaruhi, sagaru, sagaruhi
                    ]
                else:
                    temp = [kaiin[j], name_dict.get(kaiin[j], "不明"),
                            0, 0, pd.NaT, 0, pd.NaT,
                            0, pd.NaT, 0, pd.NaT]
                stats.append(temp)

            stats_matome = pd.DataFrame(stats, columns=[
                "会員番号","氏名","出場回数","最低値","最低日","最高値","最高日",
                "最大UP","UP日","最大DOWN","DOWN日"
            ])
            for col in ["最低日","最高日","UP日","DOWN日"]:
                try:
                    stats_matome[col] = pd.to_datetime(stats_matome[col]).dt.strftime('%Y-%m-%d')
                except:
                    stats_matome[col] = stats_matome[col].astype(str)
            st.table(stats_matome)

            # 個人データの表示（最新順）
            rating_data_disp = rd.copy()
            rating_data_disp["日付"] = rating_data_disp["日付"].dt.strftime('%Y-%m-%d')
            rating_data_disp = rating_data_disp.sort_values('日付', ascending=False)
            for idx, kid in enumerate(kaiin):
                name = name_dict.get(kid, str(kid))
                st.write(f'{name} の詳細データ(直近１０大会)')
                st.table(rating_data_disp[rating_data_disp["会員番号"] == kid].head(10))
                
    else:
        st.warning("先に入力を送信してください")