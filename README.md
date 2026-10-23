# tsunagalink-autopost

つながりんく(@tsunaga_link)の Instagram リールを、週2回(月・木)自動で作って予約する仕組みです。

## 流れ
1. 月・木の 9:07(日本時間)に GitHub Actions が動く
2. `content/posts.json` の「型」から、最近使っていないものを選んでリール動画を作る(ハワイアンのBGM付き)
3. 動画を GitHub Pages(`docs/media/`)に置く
4. つながりんくのスプレッドシートに、その日 21:00 の予約として1行追加する(A列に「自動:型名」)
5. 21:00 に、いつもの Apps Script が投稿する

止めたいときは、21:00 までにスプレッドシートのB列を「承認済み」以外(例:「中止」)に書き換えるだけです。

## フォルダ
- `content/posts.json` … 投稿の型(文面・画面・ハッシュタグ)。ここを書き換えると内容が変わります
- `assets/` … ロゴと写真
- `music/sources.txt` … BGMのURL。足すと次の実行で取り込まれます
- `scripts/generate.py` … 動画を作る本体
- `gas/受け取り口.gs` … Apps Script に貼る「行を追加する入口」
- `docs/` … 公開される動画置き場(30日より古いものは自動で削除)

## 手で動かす
Actions → 「Tsunagalink auto post」→「Run workflow」
- type に型名を入れるとその型で作る
- send_to_sheet をオンにすると、スプレッドシートにも予約を入れる

## 必要な設定(Settings)
- Pages → Source を「GitHub Actions」に
- Secrets and variables → Actions に `GAS_URL`(Apps Script ウェブアプリのURL)と `GAS_TOKEN`(合言葉)
