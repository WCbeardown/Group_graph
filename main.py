import streamlit as st
import numpy as np 
import pandas as pd
import datetime 
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import re
import unicodedata

st.title("羽曳野大会レーティンググループのグラフ")

# データ読み込み
rating_data = pd.read_csv("rating_data_all.csv", index_col=0)

# 日付列を datetime 型に変換（スラッシュもハイフンも対応）
rating_data["日付"] = pd.to_datetime(rating_data["日付"].str.replace("/", "-"))

# 日付順にソート
rating_data = rating_data.sort_values("日付")

# 更新日（最後のデータ日付を整形して表示）
last = rating_data["日付"].tail(1).item()
latest_year = last.year
last_display = last.strftime('%Y-%m-%d')
st.write('   最終更新日：', last_display)

st.write('使い方：自分のリーグのみの写真を用意してください。')
st.write('写真をGoogleレンズでテキスト読み込みした文字列を下の欄に貼り付けてください。')
st.write('上の矢印で描画開始年を変更できます。')
st.write('羽曳野・若葉・奈良・HPC・神戸・カミ・向日市のデータのみです')

# --- ペースト入力 ---
text_input = st.text_area("参加者リストを貼り付け", height=200)

# 開始年と終了年
year_s = st.sidebar.number_input("開始年", 2000, 2040, 2019)
year_l = st.sidebar.number_input("終了年", 2000, 2040, latest_year)


# --- 氏名抽出用関数（改良版） ---
def extract_name_dict(text: str):
    """
    Google Lens 等からの貼り付けテキストに対応する頑健な氏名抽出。
    - Unicode NFKC 正規化（全角数字→半角など）
    - 行内 "1234567 山田太郎" 形式を優先して抽出
    - 同行に氏名が無ければ次の非数値行を氏名とする
    """
    if not isinstance(text, str):
        return {}

    # 正規化（全角→半角、全角スペースなどの統一）、制御文字の除去
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'[\u200E\u200F\u202A-\u202E]', '', text)  # 方向付け等を除去
    lines = [ln.strip() for ln in text.splitlines()]

    name_dict = {}
    for i, line in enumerate(lines):
        if not line:
            continue

        # 1) 行内に "数字 + 空白 + 非数字文字列" があるかをまず見る
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

        # 2) 行内に数字があるが氏名は次行以降にあるパターン
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

            # 次の数行まで見て、最初の非数値行を氏名とする
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


# --- グラフ描画ボタン ---
if st.button("グラフ描画"):

    kaiin = []
    name_dict = {}
    if text_input:
        # 会員番号と氏名の辞書を構築
        name_dict = extract_name_dict(text_input)

        # 辞書のキー（会員番号）を最大7人まで
        kaiin = list(name_dict.keys())[:7]

        # 抽出した氏名を rating_data に反映
        if name_dict:
            try:
                rating_data["会員番号"] = rating_data["会員番号"].astype(int)
            except Exception:
                pass
            for kid, nm in name_dict.items():
                rating_data.loc[rating_data["会員番号"] == kid, "氏名"] = nm

    if kaiin:
        # 会員ごとのデータ
        rating = []
        for kid in kaiin:
            rating.append(rating_data[rating_data["会員番号"] == kid])

        # グラフ描画
        fig, ax = plt.subplots()
        colorlist = ["r", "g", "b", "c", "m", "y", "k"]

        for j, df in enumerate(rating):
            date = df["日付"]
            # 凡例は会員番号で統一
            ax.plot(date, df["レイティング"], color=colorlist[j % len(colorlist)],
                    marker="o", linestyle="solid", label=str(kaiin[j]))

        plt.style.use('ggplot')
        plt.rcParams["font.size"] = 24
        plt.tick_params(labelsize=18)
        ax.set_title("Rating Graph", fontsize=30)
        ax.set_xlabel("date", fontsize=24)
        ax.set_ylabel("Rating", fontsize=24)
        ax.legend(loc="upper left")
        fig.set_figheight(12)
        fig.set_figwidth(18)

        dates = mdates.YearLocator()
        dates_fmt = mdates.DateFormatter('%Y')
        ax.xaxis.set_major_locator(dates)
        ax.xaxis.set_major_formatter(dates_fmt)
        ax.set_xlim([datetime.datetime(year_s, 1, 1), datetime.datetime(year_l, 12, 31)])
        ax.grid(which="major", axis="x", color="green", alpha=0.8, linestyle="--", linewidth=2)
        ax.grid(which="major", axis="y", color="green", alpha=0.8, linestyle="--", linewidth=2)
        st.pyplot(fig)

        # 年平均まとめ
        st.write('レイティング　年平均比較表')
        matome = ["会員番号", "氏名"] + list(range(year_s, year_l + 1))
        temp = []
        for j, df in enumerate(rating):
            nen_heikin = [kaiin[j], name_dict.get(kaiin[j], "不明")]
            for k in range(year_s, year_l + 1):
                try:
                    nen_heikin.append(int(df[pd.DatetimeIndex(df["日付"]).year == k]["レイティング"].mean()))
                except:
                    nen_heikin.append(0)
            temp.append(nen_heikin)
        nen_heikin_matome = pd.DataFrame(temp, columns=matome)
        st.dataframe(nen_heikin_matome)

        # 分析まとめ
        st.write('分析データ')
        stats = []
        for j, df in enumerate(rating):
            agaru = 0
            sagaru = 0
            agaruhi = '2000-01-01'
            sagaruhi = '2000-01-01'
            for i in range(len(df) - 1):
                diff = df["レイティング"].iloc[i+1] - df["レイティング"].iloc[i]
                if diff > agaru:
                    agaru = diff
                    agaruhi = df["日付"].iloc[i+1]
                elif diff < sagaru:
                    sagaru = diff
                    sagaruhi = df["日付"].iloc[i+1]
            if len(df) > 1:
                temp = [
                    df["会員番号"].iloc[0],
                    name_dict.get(kaiin[j], "不明"),
                    len(df),
                    df["レイティング"].min(),
                    df[df["レイティング"] == df["レイティング"].min()]["日付"].iloc[0],
                    df["レイティング"].max(),
                    df[df["レイティング"] == df["レイティング"].max()]["日付"].iloc[0],
                    agaru, agaruhi, sagaru, sagaruhi
                ]
            else:
                temp = [kaiin[j], name_dict.get(kaiin[j], "不明"),
                        0, 0, '2000-01-01', 0, '2000-01-01',
                        0, '2000-01-01', 0, '2000-01-01']
            stats.append(temp)

        stats_matome = pd.DataFrame(stats, columns=[
            "会員番号","氏名","出場回数","最低値","最低日","最高値","最高日",
            "最大UP","UP日","最大DOWN","DOWN日"
        ])
        for col in ["最低日","最高日","UP日","DOWN日"]:
            stats_matome[col] = pd.to_datetime(stats_matome[col]).dt.strftime('%Y-%m-%d')

        st.table(stats_matome)

        # 個人データの表示
        rating_data_disp = rating_data.set_index('場所').copy()
        rating_data_disp["日付"] = rating_data_disp["日付"].dt.strftime('%Y-%m-%d')
        rating_data_disp = rating_data_disp.sort_values('日付', ascending=False)

        for idx, kid in enumerate(kaiin):
            name = name_dict.get(kid, str(kid))
            st.write(f'{name} の詳細データ')
            st.table(rating_data_disp[rating_data_disp["会員番号"] == kid].head(10))
