/**
 * GitHub Actions から届いた自動投稿を、スプレッドシートに1行追加する入口。
 * 今の Apps Script に「新しいファイル」としてこのまま貼り付けて使います。
 *
 * 準備(1回だけ):
 *  1. プロジェクトの設定 → スクリプト プロパティ に
 *       AUTOPOST_TOKEN = (GitHub の GAS_TOKEN と同じ、好きな長い文字列)
 *     を追加
 *  2. デプロイ → 新しいデプロイ → 種類「ウェブアプリ」
 *       次のユーザーとして実行: 自分
 *       アクセスできるユーザー: 全員
 *     で作成し、表示された URL を GitHub の GAS_URL に入れる
 */
const AUTOPOST_SHEET_NAME = ""; // 空なら一番左のシート。シート名を決めている場合はここに書く

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);
    const expected = PropertiesService.getScriptProperties().getProperty("AUTOPOST_TOKEN");
    if (!expected || body.token !== expected) return json_({ ok: false, error: "token" });

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = AUTOPOST_SHEET_NAME ? ss.getSheetByName(AUTOPOST_SHEET_NAME) : ss.getSheets()[0];

    // 同じ動画が二重に入らないように確認
    const last = sheet.getLastRow();
    if (last >= 2) {
      const urls = sheet.getRange(2, 8, last - 1, 1).getValues().flat();
      if (urls.indexOf(body.video_url) !== -1) return json_({ ok: true, duplicate: true });
    }

    // "2026/10/26 21:00" → 日付
    const m = String(body.schedule).match(/(\d{4})\/(\d{1,2})\/(\d{1,2}) (\d{1,2}):(\d{2})/);
    const when = new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]);

    const row = last + 1;
    sheet.getRange(row, 2).setValue("承認済み");          // B ステータス
    sheet.getRange(row, 3).setValue(body.caption);        // C 本文
    sheet.getRange(row, 6).setValue(body.hashtags);       // F ハッシュタグ
    sheet.getRange(row, 7).setValue(when);                // G 予約日時
    sheet.getRange(row, 8).setValue(body.video_url);      // H 動画URL
    sheet.getRange(row, 14).setValue(body.collaborators); // N 共同投稿者
    sheet.getRange(row, 1).setValue("自動:" + (body.type || "")); // A 目印
    return json_({ ok: true, row: row });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
