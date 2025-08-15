from flask import Flask, request, render_template_string
import yt_dlp
from concurrent.futures import ThreadPoolExecutor, TimeoutError  # 非同期処理追加

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=1)  # スレッドプール

# 検索処理を関数化（非同期用）
def do_search(query):
    ydl_opts = {
        'quiet': False,  # ログ有効化でデバッグ
        'no_warnings': True,
        'cookiefile': 'cookies.txt',  # クッキー（フォーマット確認: LF/CRLF）
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'socket_timeout': 60,  # 追加: ソケットタイムアウト60秒
        'extract_flat': True  # 追加: プレイリストを展開せず、検索結果のメタデータのみ取得（高速化）
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        search_results = ydl.extract_info(f'ytsearch40:{query}', download=False)['entries']
    
    # 結果を動画のみにフィルタ（チャンネルやプレイリストを除外、ID長で簡易判定）
    video_results = [result for result in search_results if len(result.get('id', '')) == 11]  # 動画IDは通常11文字
    
    html = '<h1>検索結果</h1><ul>'
    for result in video_results:
        html += f'<li><a href="/video/{result["id"]}">{result["title"]}</a></li>'
    html += '</ul><a href="/">戻る</a>'
    return html

# ホーム画面: 検索フォーム
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
        return render_template_string(future.result(timeout=30))  # 30秒以内で応答、タイムアウト時はエラー
    except TimeoutError:
        return "検索がタイムアウトしました。後で再試行してください。", 504  # Gateway Timeout
    except Exception as e:
        return f"検索エラー: {str(e)}", 500

# 動画詳細画面（同様にオプション追加）
@app.route('/video/<video_id>')
def video(video_id):
    ydl_opts = {
        'quiet': False,  # ログ有効化
        'no_warnings': True,
        'cookiefile': 'cookies.txt',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'socket_timeout': 60  # 追加
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(video_id, download=False)
        except Exception as e:
            return f"動画情報取得エラー: {str(e)}"
    
    html = f'<h1>{info["title"]}</h1>'
    html += '<h2>利用可能なフォーマット（画質/音声）</h2>'
    html += '<table border="1"><tr><th>タイプ</th><th>フォーマットID</th><th>解像度/ノート</th><th>拡張子</th><th>ファイルサイズ</th><th>ビットレート</th><th>リンク</th></tr>'
    
    for fmt in info['formats']:
        format_type = '音声' if 'audio only' in fmt.get('resolution', '').lower() else '動画'
        format_id = fmt.get('format_id', '不明')
        resolution = fmt.get('resolution', '不明') if format_type == '動画' else fmt.get('format_note', 'N/A')
        ext = fmt.get('ext', '不明')
        filesize = f"{fmt.get('filesize', 0) / (1024*1024):.2f} MB" if fmt.get('filesize') else '不明'
        bitrate = f"{fmt.get('abr', 0)} kbps" if 'abr' in fmt else f"{fmt.get('vbr', 0)} kbps" if 'vbr' in fmt else '不明'
        url = fmt['url']
        
        html += f'<tr><td>{format_type}</td><td>{format_id}</td><td>{resolution}</td><td>{ext}</td><td>{filesize}</td><td>{bitrate}</td><td><a href="{url}" target="_blank">再生/ダウンロード</a></td></tr>'
    
    html += '</table>'
    html += '<a href="/">ホームに戻る</a>'
    
    return render_template_string(html)

if __name__ == '__main__':
    app.run(debug=True)
