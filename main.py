from flask import Flask, request, render_template_string
import yt_dlp
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import tempfile
import os

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=1)

# YouTubeのクッキー情報
YOUTUBE_COOKIES = """
# Netscape HTTP Cookie File

# Domain, Include Subdomains, Path, Secure, Expiry, Name, Value

.youtube.com\tTRUE\t/\tFALSE\t0\tPREF\ttz=UTC
.youtube.com\tTRUE\t/\tTRUE\t0\tVISITOR_INFO1_LIVE\tXR0xd-RHxkM
.youtube.com\tTRUE\t/\tTRUE\t0\tVISITOR_PRIVACY_METADATA\tCgJVUxIEGgAgJg%3D%3D
.youtube.com\tTRUE\t/\tTRUE\t0\t__Secure-ROLLOUT_TOKEN\tCMnsvMX91un_CRDE3JzWlYyPAxiQx_vWlYyPAw%3D%3D
.youtube.com\tTRUE\t/\tTRUE\t0\tYSC\twk_oCT5BVFM
.youtube.com\tTRUE\t/\tTRUE\t0\tGPS\t1
"""

# 検索・動画情報取得の共通オプション
def get_ydl_opts(user_agent):
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write(YOUTUBE_COOKIES)
        temp_file_path = temp_file.name

    return {
        'quiet': True,  # ログを非表示
        'no_warnings': True,
        'cookiefile': temp_file_path,
        'user_agent': user_agent,
        'socket_timeout': 60,
        'temp_file_path': temp_file_path # 後で削除するためにパスを保持
    }

# 検索処理を関数化（非同期用）
def do_search(query):
    opts = get_ydl_opts('Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36')
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            search_results = ydl.extract_info(f'ytsearch40:{query}', download=False)['entries']
        
        video_results = [r for r in search_results if len(r.get('id', '')) == 11]
        
        html = '<h1>検索結果</h1><ul>'
        for result in video_results:
            html += f'<li><a href="/video/{result["id"]}">{result["title"]}</a></li>'
        html += '</ul><a href="/">戻る</a>'
        return html
    finally:
        os.remove(opts['temp_file_path'])

# ホーム画面
@app.route('/')
def home():
    return render_template_string('''
        <h1>YouTube動画検索サイト</h1>
        <form method="get" action="/search">
            <input name="q" placeholder="検索キーワードを入力" required>
            <button type="submit">検索</button>
        </form>
    ''')

# 検索結果画面（非同期化）
@app.route('/search')
def search():
    query = request.args.get('q')
    if not query:
        return "検索キーワードを入力してください。"
    
    future = executor.submit(do_search, query)
    try:
        return render_template_string(future.result(timeout=30))
    except TimeoutError:
        return "検索がタイムアウトしました。後で再試行してください。", 504
    except Exception as e:
        return f"検索エラー: {str(e)}", 500

# 動画詳細画面
@app.route('/video/<video_id>')
def video(video_id):
    opts = get_ydl_opts('Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36')
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(video_id, download=False)
            except Exception as e:
                return f"動画情報取得エラー: {str(e)}"
    
        html = f'<h1>{info["title"]}</h1>'
        html += '<h2>利用可能なフォーマット</h2>'
        html += '<table border="1"><tr><th>タイプ</th><th>ID</th><th>解像度</th><th>拡張子</th><th>サイズ</th><th>ビットレート</th><th>リンク</th></tr>'
        
        for fmt in info['formats']:
            format_type = '音声' if 'audio' in fmt.get('format_note', '').lower() else '動画'
            html += f'<tr><td>{format_type}</td><td>{fmt.get("format_id", "不明")}</td><td>{fmt.get("resolution", fmt.get("format_note", "N/A"))}</td><td>{fmt.get("ext", "不明")}</td><td>{f"{fmt.get("filesize", 0) / (1024*1024):.2f} MB" if fmt.get("filesize") else "不明"}</td><td>{f"{fmt.get("abr", 0)} kbps" if "abr" in fmt else "不明"}</td><td><a href="{fmt["url"]}" target="_blank">再生/DL</a></td></tr>'
        
        html += '</table><a href="/">ホームに戻る</a>'
        
        return render_template_string(html)
    finally:
        os.remove(opts['temp_file_path'])
