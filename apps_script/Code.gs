const RECORD_HEADERS = [
  '日期', '晨重', '睡眠', '排便', '精神', '训练', '训练详情', '饮水', '饮食',
  '蛋白质估算', '备注', '酸痛', '综合评分', '用户ID', '更新时间'
];
const USER_HEADERS = ['用户ID', '收集阶段', '更新时间', '启用提醒'];

function setup() {
  getSheet_('每日记录', RECORD_HEADERS);
  getSheet_('用户', USER_HEADERS);
}

function doGet(e) {
  try {
    checkSecret_(e.parameter.secret);
    const action = e.parameter.action;
    if (action === 'list_users') return json_(true, listUsers_());
    if (action === 'get_phase') return json_(true, getPhase_(e.parameter.user_id));
    if (action === 'get_record') return json_(true, getRecord_(e.parameter.user_id, e.parameter.day));
    if (action === 'list_records') {
      return json_(true, listRecords_(e.parameter.user_id, Number(e.parameter.limit || 0)));
    }
    throw new Error('Unknown action');
  } catch (error) { return json_(false, null, String(error)); }
}

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);
    checkSecret_(body.secret);
    if (body.action === 'upsert_record') upsertRecord_(body.row);
    else if (body.action === 'register_user') registerUser_(body.user_id);
    else if (body.action === 'set_phase') setPhase_(body.user_id, body.phase || '');
    else throw new Error('Unknown action');
    return json_(true, true);
  } catch (error) { return json_(false, null, String(error)); }
}

function checkSecret_(value) {
  const expected = PropertiesService.getScriptProperties().getProperty('API_SECRET');
  if (!expected || value !== expected) throw new Error('Unauthorized');
}

function getSheet_(name, headers) {
  const book = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = book.getSheetByName(name);
  if (!sheet) sheet = book.insertSheet(name);
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(headers);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold').setBackground('#d9eaff');
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function rowsAsObjects_(sheet) {
  const values = sheet.getDataRange().getDisplayValues();
  if (values.length < 2) return [];
  return values.slice(1).map(row => Object.fromEntries(values[0].map((key, i) => [key, row[i]])));
}

function upsertRecord_(row) {
  const sheet = getSheet_('每日记录', RECORD_HEADERS);
  const values = sheet.getDataRange().getDisplayValues();
  for (let i = 1; i < values.length; i++) {
    if (values[i][0] === String(row[0]) && values[i][13] === String(row[13])) {
      sheet.getRange(i + 1, 1, 1, RECORD_HEADERS.length).setValues([row]);
      return;
    }
  }
  sheet.appendRow(row);
}

function getRecord_(userId, day) {
  return rowsAsObjects_(getSheet_('每日记录', RECORD_HEADERS))
    .find(row => row['用户ID'] === userId && row['日期'] === day) || null;
}

function listRecords_(userId, limit) {
  let rows = rowsAsObjects_(getSheet_('每日记录', RECORD_HEADERS))
    .filter(row => row['用户ID'] === userId)
    .sort((a, b) => a['日期'].localeCompare(b['日期']));
  return limit ? rows.slice(-limit) : rows;
}

function registerUser_(userId) {
  const sheet = getSheet_('用户', USER_HEADERS);
  const rows = sheet.getDataRange().getDisplayValues();
  if (!rows.slice(1).some(row => row[0] === userId)) {
    sheet.appendRow([userId, '', new Date().toISOString(), '是']);
  }
}

function listUsers_() {
  return rowsAsObjects_(getSheet_('用户', USER_HEADERS))
    .filter(row => row['启用提醒'] !== '否').map(row => row['用户ID']);
}

function findUserRow_(sheet, userId) {
  const rows = sheet.getDataRange().getDisplayValues();
  for (let i = 1; i < rows.length; i++) if (rows[i][0] === userId) return i + 1;
  return 0;
}

function setPhase_(userId, phase) {
  registerUser_(userId);
  const sheet = getSheet_('用户', USER_HEADERS);
  const row = findUserRow_(sheet, userId);
  sheet.getRange(row, 2, 1, 2).setValues([[phase, new Date().toISOString()]]);
}

function getPhase_(userId) {
  const sheet = getSheet_('用户', USER_HEADERS);
  const row = findUserRow_(sheet, userId);
  return row ? sheet.getRange(row, 2).getDisplayValue() : '';
}

function json_(ok, data, error) {
  return ContentService.createTextOutput(JSON.stringify({ok, data, error}))
    .setMimeType(ContentService.MimeType.JSON);
}
