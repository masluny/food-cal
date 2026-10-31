// food-cal display: SCAN -> the PC photographs the plate -> result -> RE-SCAN or ADD TODAY -> Today screen.
//
// Board: Freenove ESP32 3.2" (ST7789 240x320, touch via TFT_eSPI), ESP32-D0WD-V3, CH340 (COM3).
// TFT_eSPI takes its pins from the library's User_Setup_Select.h -> FNK0103L_3P2_240x320_ST7789.
// Upload: esp32/upload.ps1
//
// Screens (enum values are prefixed SCR_ because ESP-IDF already defines BUSY):
//   TODAY    date, today's kcal and P/F/C (from the PC's diary), SCAN + EDIT buttons (a touch outside EDIT scans)
//   BUSY     "Scanning..." / "Adding..." / "Loading..."; X (top right) cancels: back to TODAY, late answer dropped
//   RESULT   dish, kcal, P/F/C + RESCAN / CHANGE / ADD, X closes it unadded (mic moves left of the X);
//            back to TODAY after RESULT_TIMEOUT_MS
//   PICK     CHANGE: up to 3 other dishes the model considered (or similar ones) — tap one to correct the result
//   LIST     today's meals, newest first, 3 per page, DELETE (tap twice: DELETE -> SURE?), BACK and < > paging
//   LISTEN   while the MIC button (top right on TODAY / RESULT) is held: the PC records, on release it
//            transcribes, asks the OpenRouter model and sends a normal result (ADD works, CHANGE does not)
//   MESSAGE  errors; back to TODAY after MESSAGE_TIMEOUT_MS (a touch scans again)
//   OFF      no word from the PC for PC_TIMEOUT_MS (PC off): black screen, dimmed backlight, small red power
//            icon; touches ignored; the clock keeps counting and everything comes back when the PC does
// The BOOT button = SCAN (on the result screen: RESCAN, on the list / pick screen: BACK).
//
// Protocol: USB serial 115200, one message per line.
//   ESP -> PC:  "HELLO food-cal 5 up=..s reset=.. clock=.." (every 3 s until the PC answers), "SCAN", "RESCAN", "ADD", "LIST", "DEL <index>",
//               "PICK <index>", "MIC_START" (button pressed), "MIC_STOP" (released), "CANCEL" (X while waiting),
//               "TOUCH x y" (debug)
//   PC -> ESP:  JSON  {"t":"ping","clock":1791826800} (PC local time as seconds since 1970 -> clock in the header)
//               {"t":"status","msg":".."}  {"t":"error","msg":".."}
//               {"t":"result","name":"toast","kcal":324,"lo":259,"hi":389,"protein":15.8,"fat":15.8,"carbs":29.4,
//                "lines":["toast: 324 kcal"], "alts":[{"name":"bread","kcal":210,"conf":0.31}, ...]}
//                (kcal == null when the scale is not calibrated -> no ADD; alts = choices for CHANGE)
//               {"t":"today","date":"Mon 12 Oct 2026","kcal":1234,"protein":50,"fat":40,"carbs":150,"meals":3,
//                "last":"toast +324 kcal"}
//               {"t":"list","items":[{"time":"12:30","name":"toast","kcal":324}, ...]}   (newest first)
// Texts from the PC are ASCII only (the built-in TFT_eSPI fonts have no other characters).

#include <TFT_eSPI.h>
#include <ArduinoJson.h>
#include <sys/time.h>
#include <time.h>

TFT_eSPI tft;

const int BOOT_BTN = 0;
const int BL_PIN = 27;
const uint8_t BL_ON = 255, BL_OFF = 18;      // backlight PWM: normal / PC off (dim, so the black stays black)
const uint32_t PC_TIMEOUT_MS = 12000;
const uint32_t BUSY_TIMEOUT_MS = 45000;
const uint32_t RESULT_TIMEOUT_MS = 60000;   // the result disappears after a minute if not added
const uint32_t LIST_TIMEOUT_MS = 60000;     // the list / pick screen closes after a minute without a touch
const uint32_t MESSAGE_TIMEOUT_MS = 8000;
const uint32_t ARM_TIMEOUT_MS = 4000;       // "SURE?" waits this long for the second tap
const uint32_t TOUCH_GAP_MS = 400;
const uint32_t RELEASE_MS = 250;            // no touch for this long = the MIC button was released
const uint32_t MAX_MIC_MS = 20000;          // recording stops by itself after 20 s

// screen layout 320x240 (rotation 1)
const int W = 320, H = 240, HDR_H = 26, BTN_Y = 184, BTN_H = 50, BAR_Y = 179;
const int LIST_ROWS = 3, ROW_Y0 = 28, ROW_H = 52, DEL_X = 226, DEL_W = 86;
const int MIC_X = 264, MIC_Y = 30, MIC_W = 48, MIC_H = 44;     // small microphone button, top right
const int MIC2_X = 210;                     // on a result the mic moves left: the X (close) takes the corner
const uint32_t IGNORE_MS = 90000;           // after X while waiting: the late answer is dropped (if within this)
const uint16_t C_BG = TFT_BLACK, C_HDR = 0x2124, C_BTN = 0x0461, C_BUSY = 0x52AA, C_RESCAN = 0x9A40, C_OFF = 0x3186;
const uint16_t C_EDIT = 0x2A6F, C_DEL = 0x6000, C_P = 0x5D1F, C_F = 0xFE60, C_C = 0x87F0, C_DIM = 0x9CF3;

enum Screen { SCR_TODAY, SCR_BUSY, SCR_RESULT, SCR_LIST, SCR_PICK, SCR_LISTEN, SCR_MESSAGE, SCR_OFF };
Screen screen = SCR_TODAY;
bool pcOnline = false, addEnabled = false, adding = false, listLoading = false;
bool wasTouching = false, bootWasDown = false, micActive = false;
uint32_t lastPcMsg = 0, screenSince = 0, lastAction = 0, lastHello = 0, armedAt = 0, lastTouchMs = 0;
int listenSecs = -1;
int barLast = -1;
String line;

// today's totals (sent by the PC)
bool haveToday = false;
String tDate, tLast, banner;
float tKcal = 0, tP = 0, tF = 0, tC = 0;
int tMeals = 0;

// today's meals for the EDIT list (sent by the PC)
const int MAX_ITEMS = 40;
String itemName[MAX_ITEMS], itemTime[MAX_ITEMS];
int itemKcal[MAX_ITEMS], nItems = 0, page = 0, armed = -1, deleting = -1;

// CHANGE alternatives of the current result (sent by the PC)
String lastResult, altName[3];
int altKcal[3], altConf[3], nAlts = 0;
bool picking = false;

// X pressed while waiting for a scan / voice / CHANGE answer: that answer is dropped when it arrives
bool expectReply = false, ignoreReply = false;
uint32_t ignoreSince = 0;

bool replyIgnored() {
  if (ignoreReply && millis() - ignoreSince > IGNORE_MS) ignoreReply = false;
  return ignoreReply;
}

// clock in the header: the PC's local time (sent with every ping) set as the ESP32's system time, so it keeps
// counting while the PC is off and survives a soft reset (not a power cut: this board has no battery clock).
// The system time holds LOCAL time, so gmtime() of it is the local date and time.
int clockShown = -2;
long tDay = -1;                              // day (days since 1970) of the totals in tKcal...

bool clockValid() { return time(nullptr) > 1600000000; }
int clockMinute() { return clockValid() ? (int)((time(nullptr) % 86400) / 60) : -1; }

void setClock(time_t t) {
  if (llabs((long long)(time(nullptr) - t)) <= 1) return;   // already right, don't jitter
  struct timeval tv = {t, 0};
  settimeofday(&tv, nullptr);
}

const char *headerLabel(Screen s) {
  return s == SCR_LIST ? "edit today" : s == SCR_PICK ? "change dish" : s == SCR_LISTEN ? "voice" : "";
}

void drawHeader() {
  tft.fillRect(0, 0, W, HDR_H, C_HDR);
  char buf[8];
  int m = clockShown = clockMinute();
  if (screen == SCR_OFF) return;               // PC off: the screen stays black
  if (m < 0) strcpy(buf, "--:--");
  else snprintf(buf, sizeof(buf), "%02d:%02d", m / 60, m % 60);
  tft.setTextDatum(ML_DATUM);
  tft.setTextColor(TFT_WHITE, C_HDR);
  tft.setFreeFont(&FreeSansBold9pt7b);
  int x = 8 + tft.drawString(buf, 8, HDR_H / 2);
  tft.setTextFont(2);
  if (*headerLabel(screen)) {
    tft.setTextColor(C_DIM, C_HDR);
    tft.drawString(String("  /  ") + headerLabel(screen), x, HDR_H / 2, 2);
  }
  tft.setTextDatum(MR_DATUM);
  tft.setTextColor(pcOnline ? TFT_GREEN : TFT_RED, C_HDR);
  tft.drawString(pcOnline ? "PC: OK" : "PC: offline", W - 22, HDR_H / 2, 2);
  tft.fillCircle(W - 11, HDR_H / 2, 5, pcOnline ? TFT_GREEN : TFT_RED);
}

// big font when the label fits, otherwise a smaller bold one (small = always the smaller one, e.g. a row of 3)
void drawButton(int x, int w, uint16_t color, const char *label, bool small = false) {
  tft.fillRoundRect(x, BTN_Y, w, BTN_H, 12, color);
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(TFT_WHITE, color);
  if (!small && tft.textWidth(label, 4) <= w - 16) {
    tft.drawString(label, x + w / 2, BTN_Y + BTN_H / 2, 4);
  } else {
    tft.setFreeFont(&FreeSansBold9pt7b);
    tft.drawString(label, x + w / 2, BTN_Y + BTN_H / 2);
    tft.setTextFont(2);
  }
}

// microphone icon: capsule, U-shaped holder, stem and base (s = scale)
void drawMicIcon(int cx, int cy, uint16_t color, int s = 1) {
  tft.fillRoundRect(cx - 5 * s, cy - 13 * s, 10 * s, 17 * s, 5 * s, color);
  for (int t = 0; t < 2 * s; t++) tft.drawCircleHelper(cx, cy - 2 * s, 9 * s - t, 4 | 8, color);
  tft.fillRect(cx - s, cy + 7 * s, 2 * s, 4 * s, color);
  tft.fillRect(cx - 5 * s, cy + 11 * s, 10 * s, 2 * s, color);
}

// hidden while the PC is offline — nothing would record or answer
void drawMicButton(bool active, int x = MIC_X) {
  if (!pcOnline) {
    tft.fillRect(x, MIC_Y, MIC_W, MIC_H, C_BG);
    return;
  }
  uint16_t c = active ? TFT_RED : C_EDIT;
  tft.fillRoundRect(x, MIC_Y, MIC_W, MIC_H, 10, c);
  drawMicIcon(x + MIC_W / 2, MIC_Y + MIC_H / 2 + 1, TFT_WHITE);
}

// X in the top right corner: cancel while waiting, close a result without adding it
void drawCloseButton() {
  int cx = MIC_X + MIC_W / 2, cy = MIC_Y + MIC_H / 2;
  tft.fillRoundRect(MIC_X, MIC_Y, MIC_W, MIC_H, 10, C_DEL);
  tft.drawWideLine(cx - 9, cy - 9, cx + 9, cy + 9, 4, TFT_WHITE, C_DEL);
  tft.drawWideLine(cx - 9, cy + 9, cx + 9, cy - 9, 4, TFT_WHITE, C_DEL);
}

bool inTopRow(int y) { return y >= HDR_H - 4 && y <= MIC_Y + MIC_H + 8; }
bool onMicButton(int x, int y) { return pcOnline && x >= MIC_X - 8 && inTopRow(y); }
bool onCloseButton(int x, int y) { return x >= MIC_X - 6 && inTopRow(y); }
bool onResultMic(int x, int y) { return pcOnline && x >= MIC2_X - 6 && x < MIC_X - 6 && inTopRow(y); }

void clearMain() { tft.fillRect(0, HDR_H, W, BTN_Y - HDR_H, C_BG); }
void clearButtons() { tft.fillRect(0, BTN_Y, W, H - BTN_Y, C_BG); }

void setScreen(Screen s) {
  bool headerChange = strcmp(headerLabel(s), headerLabel(screen)) != 0;
  screen = s;
  screenSince = millis();
  barLast = -1;
  if (headerChange) drawHeader();
}

// kcal in the big digit font + P/F/C row; used by both TODAY and RESULT
void drawNumbers(float kcal, float p, float f, float c) {
  char buf[32];
  snprintf(buf, sizeof(buf), "%d", (int)lround(kcal));
  tft.setTextDatum(TL_DATUM);
  tft.setTextColor(TFT_WHITE, C_BG);
  int x = 8 + tft.drawString(buf, 8, 62, 6);   // font 6: digits only, 48 px
  tft.drawString(" kcal", x, 82, 4);
  const char *labels[3] = {"P ", "F ", "C "};
  float vals[3] = {p, f, c};
  uint16_t colors[3] = {C_P, C_F, C_C};
  for (int i = 0; i < 3; i++) {
    snprintf(buf, sizeof(buf), "%s%.0fg", labels[i], vals[i]);
    tft.setTextColor(colors[i], C_BG);
    tft.drawString(buf, 8 + i * 104, 114, 4);
  }
}

void showMessage(const char *title, const char *sub, uint16_t color) {
  setScreen(SCR_MESSAGE);
  clearMain();
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(color, C_BG);
  tft.drawString(title, W / 2, 85, 4);
  tft.setTextColor(C_DIM, C_BG);
  tft.drawString(sub, W / 2, 125, 2);
  clearButtons();
  drawButton(8, 304, C_BTN, "SCAN");
}

void showBusy(const char *title, const char *sub) {
  setScreen(SCR_BUSY);
  clearMain();
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(TFT_WHITE, C_BG);
  tft.drawString(title, W / 2, 85, 4);
  tft.setTextColor(C_DIM, C_BG);
  tft.drawString(sub, W / 2, 125, 2);
  clearButtons();
  drawButton(8, 304, C_BUSY, "PLEASE WAIT...");
  drawCloseButton();
}

// power symbol in red with a soft halo of darker reds around it
void drawPowerIcon(int cx, int cy) {
  const uint16_t halo[] = {0x0800, 0x1000, 0x1800, 0x2000, 0x2800};   // RGB565 reds, outer to inner
  for (int i = 0; i < 5; i++) tft.fillSmoothCircle(cx, cy, 34 - i * 4, halo[i], i ? halo[i - 1] : C_BG);
  uint16_t in = halo[4];
  tft.drawSmoothArc(cx, cy, 14, 11, 0, 140, TFT_RED, in, true);      // ring with a gap at the top
  tft.drawSmoothArc(cx, cy, 14, 11, 220, 360, TFT_RED, in, true);    // (0 deg = 6 o'clock, clockwise)
  tft.drawWideLine(cx, cy - 17, cx, cy - 3, 3, TFT_RED, in);
}

// PC off: black screen, dimmed backlight, only the red power icon (the clock keeps counting in the background)
void showOff() {
  micActive = false;
  setScreen(SCR_OFF);
  tft.fillScreen(C_BG);
  drawPowerIcon(W / 2, H / 2);
  analogWrite(BL_PIN, BL_OFF);
}

void showToday() {
  if (!pcOnline) { showOff(); return; }
  setScreen(SCR_TODAY);
  clearMain();
  if (!haveToday) {
    tft.setTextDatum(MC_DATUM);
    tft.setTextColor(TFT_WHITE, C_BG);
    tft.drawString("Ready", W / 2, 85, 4);
    tft.setTextColor(C_DIM, C_BG);
    tft.drawString("Put a plate under the camera and press SCAN", W / 2, 125, 2);
  } else {
    tft.setTextDatum(TL_DATUM);
    tft.setTextColor(TFT_WHITE, C_BG);
    int tw = tft.drawString("Today", 8, 32, 4);
    tft.setTextColor(C_DIM, C_BG);
    tft.drawString(tDate, 8 + tw + 12, 39, 2);
    drawNumbers(tKcal, tP, tF, tC);
    tft.setTextDatum(TL_DATUM);
    tft.setTextColor(C_DIM, C_BG);
    String meals = String(tMeals) + (tMeals == 1 ? " meal" : " meals");
    if (tLast.length()) meals += "   last: " + tLast;
    tft.drawString(meals.substring(0, 50), 8, 146, 2);
    if (banner.length()) {
      tft.setTextColor(TFT_GREEN, C_BG);
      tft.drawString(banner.substring(0, 50), 8, 162, 2);
      banner = "";
    }
  }
  drawMicButton(false);
  clearButtons();
  drawButton(8, 216, C_BTN, "SCAN");
  drawButton(232, 80, C_EDIT, "EDIT");
}

void showResult(JsonDocument &doc) {
  setScreen(SCR_RESULT);
  clearMain();
  tft.setTextDatum(TL_DATUM);
  tft.setTextColor(TFT_WHITE, C_BG);
  String name = doc["name"] | "?";
  while (name.length() > 1 && tft.textWidth(name, 4) > MIC2_X - 12) name = name.substring(0, name.length() - 1);
  tft.drawString(name, 8, 32, 4);

  addEnabled = !doc["kcal"].isNull();
  if (!addEnabled) {
    tft.setTextColor(TFT_ORANGE, C_BG);
    tft.drawString("Scale not calibrated", 8, 70, 2);
    tft.setTextColor(C_DIM, C_BG);
    tft.drawString("Tray icon > Calibrate scale...", 8, 88, 2);
  } else {
    drawNumbers(doc["kcal"].as<float>(), doc["protein"] | 0.0f, doc["fat"] | 0.0f, doc["carbs"] | 0.0f);
    char buf[32];
    snprintf(buf, sizeof(buf), "%d-%d", (int)lround(doc["lo"] | 0.0f), (int)lround(doc["hi"] | 0.0f));
    tft.setTextDatum(TR_DATUM);
    tft.setTextColor(C_DIM, C_BG);
    tft.drawString(buf, W - 8, 92, 2);
  }

  int y = 144;
  tft.setTextDatum(TL_DATUM);
  tft.setTextColor(C_DIM, C_BG);
  for (JsonVariant v : doc["lines"].as<JsonArray>()) {
    if (y > 161) break;
    String s = v.as<String>();
    if (s.length() > 48) s = s.substring(0, 47) + ".";
    tft.drawString(s, 8, y, 2);
    y += 17;
  }
  nAlts = 0;
  for (JsonObject a : doc["alts"].as<JsonArray>()) {
    if (nAlts >= 3) break;
    altName[nAlts] = a["name"] | "?";
    altKcal[nAlts] = a["kcal"].isNull() ? -1 : (int)(a["kcal"] | 0);
    altConf[nAlts] = (int)lround((a["conf"] | 0.0f) * 100);
    nAlts++;
  }
  clearButtons();
  drawButton(8, 96, C_RESCAN, "RESCAN", true);
  drawButton(112, 96, nAlts ? C_EDIT : C_OFF, "CHANGE", true);
  drawButton(216, 96, addEnabled ? C_BTN : C_OFF, "ADD", true);
  drawMicButton(false, MIC2_X);
  drawCloseButton();
}

void showListening() {
  setScreen(SCR_LISTEN);
  listenSecs = -1;
  clearMain();
  drawMicIcon(W / 2, 74, TFT_RED, 2);
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(TFT_WHITE, C_BG);
  tft.drawString("Listening...", W / 2, 128, 4);
  tft.setTextColor(C_DIM, C_BG);
  tft.drawString("say what you ate, then release", W / 2, 152, 2);
  clearButtons();
  drawButton(8, 304, TFT_RED, "RELEASE TO FINISH");
}

void startMic() {
  micActive = true;
  lastTouchMs = millis();
  showListening();
  sendCmd("MIC_START");
}

void stopMic() {
  micActive = false;
  expectReply = true;
  showBusy("Thinking...", "Transcribing and asking the model");
  sendCmd("MIC_STOP");
}

void backToResult() {
  JsonDocument doc;
  if (lastResult.length() && !deserializeJson(doc, lastResult)) showResult(doc);
  else showToday();
}

void showPick() {
  setScreen(SCR_PICK);
  clearMain();
  for (int i = 0; i < nAlts; i++) {
    int y0 = ROW_Y0 + i * ROW_H;
    tft.fillRoundRect(8, y0 + 3, W - 16, ROW_H - 6, 8, C_HDR);
    tft.setTextDatum(TL_DATUM);
    tft.setTextColor(TFT_WHITE, C_HDR);
    String name = altName[i];
    if (name.length() > 18) name = name.substring(0, 17) + ".";
    tft.drawString(name, 18, y0 + 8, 4);
    String info = altKcal[i] >= 0 ? String(altKcal[i]) + " kcal" : String("");
    if (altConf[i] > 0) info += (info.length() ? "   " : "") + String("model ") + String(altConf[i]) + "%";
    tft.setTextDatum(TR_DATUM);
    tft.setTextColor(C_DIM, C_HDR);
    tft.drawString(info, W - 18, y0 + 34, 2);
  }
  clearButtons();
  drawButton(8, 304, C_BUSY, "BACK");
}

void onPickPress(int x, int y) {
  screenSince = millis();
  if (y >= BTN_Y - 4) { backToResult(); return; }
  int i = (y - ROW_Y0) / ROW_H;
  if (y < ROW_Y0 || i >= nAlts) return;
  picking = expectReply = true;
  showBusy("Changing...", altName[i].c_str());
  sendCmd("PICK " + String(i));
}

int pages() { return max(1, (nItems + LIST_ROWS - 1) / LIST_ROWS); }

void drawList() {
  clearMain();
  if (nItems == 0) {
    tft.setTextDatum(MC_DATUM);
    tft.setTextColor(C_DIM, C_BG);
    tft.drawString("No meals today", W / 2, 100, 4);
  }
  for (int r = 0; r < LIST_ROWS; r++) {
    int i = page * LIST_ROWS + r;
    if (i >= nItems) break;
    int y0 = ROW_Y0 + r * ROW_H;
    String name = itemName[i];
    if (name.length() > 15) name = name.substring(0, 14) + ".";
    tft.setTextDatum(TL_DATUM);
    tft.setTextColor(TFT_WHITE, C_BG);
    tft.drawString(name, 8, y0 + 4, 4);
    tft.setTextColor(C_DIM, C_BG);
    tft.drawString(itemTime[i] + "   " + String(itemKcal[i]) + " kcal", 8, y0 + 32, 2);
    uint16_t c = (i == deleting) ? C_OFF : (i == armed ? TFT_RED : C_DEL);
    tft.fillRoundRect(DEL_X, y0 + 8, DEL_W, 36, 8, c);
    tft.setTextDatum(MC_DATUM);
    tft.setTextColor(TFT_WHITE, c);
    tft.drawString(i == deleting ? "..." : (i == armed ? "SURE?" : "DELETE"), DEL_X + DEL_W / 2, y0 + 26, 2);
    tft.drawFastHLine(8, y0 + ROW_H - 1, W - 16, C_OFF);
  }
  if (pages() > 1) {
    tft.setTextDatum(TR_DATUM);
    tft.setTextColor(C_DIM, C_BG);
    tft.drawString(String(page + 1) + "/" + String(pages()), W - 8, BAR_Y - 14, 1);
  }
  clearButtons();
  drawButton(8, 148, C_BUSY, "BACK");
  drawButton(164, 70, page > 0 ? C_EDIT : C_OFF, "<");
  drawButton(242, 70, page + 1 < pages() ? C_EDIT : C_OFF, ">");
}

void showList() {
  setScreen(SCR_LIST);
  page = min(page, pages() - 1);
  drawList();
}

void drawCountdown() {  // thin bar above the buttons: time left before the result disappears
  uint32_t el = millis() - screenSince;
  uint32_t left = el >= RESULT_TIMEOUT_MS ? 0 : RESULT_TIMEOUT_MS - el;
  int w = (int)(304UL * left / RESULT_TIMEOUT_MS);
  if (w == barLast) return;
  tft.fillRect(8, BAR_Y, 304, 3, C_BG);
  tft.fillRect(8, BAR_Y, w, 3, C_DIM);
  barLast = w;
}

void setPc(bool online) {
  if (online == pcOnline) return;
  pcOnline = online;
  if (!online && screen != SCR_BUSY && screen != SCR_LISTEN) {   // a slow scan / voice answer may still come
    showOff();
    return;
  }
  if (online && screen == SCR_OFF) {
    analogWrite(BL_PIN, BL_ON);
    screen = SCR_TODAY;
    drawHeader();
    showToday();
    return;
  }
  drawHeader();
  if (screen == SCR_RESULT) drawMicButton(false, MIC2_X);
}

void sendCmd(const String &cmd) {
  lastAction = millis();
  Serial.println(cmd);
}

void doScan(bool rescan) {
  adding = listLoading = false;
  expectReply = true;
  showBusy(rescan ? "Scanning again..." : "Scanning...", pcOnline ? "Taking a photo of the plate" : "Waiting for the PC");
  sendCmd(rescan ? "RESCAN" : "SCAN");
}

void doAdd() {
  adding = true;
  expectReply = false;
  showBusy("Adding...", "Saving to today's diary");
  sendCmd("ADD");
}

// X while waiting: back to TODAY now; the PC finishes anyway, but its answer is not shown
void cancelBusy() {
  if (expectReply) {
    ignoreReply = true;
    ignoreSince = millis();
  }
  expectReply = adding = listLoading = picking = false;
  sendCmd("CANCEL");
  showToday();
}

void openList() {
  listLoading = true;
  expectReply = false;
  page = 0;
  armed = deleting = -1;
  showBusy("Loading...", "Today's meals");
  sendCmd("LIST");
}

void onListPress(int x, int y) {
  screenSince = millis();                      // any touch keeps the list open
  if (y >= BTN_Y - 4) {                        // bottom buttons
    armed = -1;
    if (x < 160) { showToday(); return; }
    if (x < 238 && page > 0) page--;
    else if (x >= 238 && page + 1 < pages()) page++;
    drawList();
    return;
  }
  int r = (y - ROW_Y0) / ROW_H;
  int i = page * LIST_ROWS + r;
  if (y < ROW_Y0 || r >= LIST_ROWS || i >= nItems || x < DEL_X - 12 || deleting >= 0) {
    if (armed >= 0) { armed = -1; drawList(); }
    return;
  }
  if (armed == i && millis() - armedAt < ARM_TIMEOUT_MS) {
    armed = -1;
    deleting = i;
    drawList();
    sendCmd("DEL " + String(i));
  } else {
    armed = i;
    armedAt = millis();
    drawList();
  }
}

void onPress(int x, int y, bool fromBoot) {
  if (millis() - lastAction < TOUCH_GAP_MS) return;
  lastAction = millis();
  if (!fromBoot) Serial.printf("TOUCH %d %d\n", x, y);
  switch (screen) {
    case SCR_TODAY:
      if (!fromBoot && onMicButton(x, y)) startMic();
      else if (!fromBoot && y >= H / 2 && x >= 224) openList();
      else doScan(false);
      break;
    case SCR_MESSAGE:
      doScan(false);
      break;
    case SCR_RESULT:
      if (fromBoot) doScan(true);
      else if (onCloseButton(x, y)) showToday();          // X: close without adding
      else if (onResultMic(x, y)) startMic();
      else if (y >= H / 2) {                   // lower half of the screen = the three buttons
        if (x < 108) doScan(true);
        else if (x < 212) { if (nAlts) showPick(); }
        else if (addEnabled) doAdd();
      }
      break;
    case SCR_PICK:
      if (fromBoot) backToResult();
      else onPickPress(x, y);
      break;
    case SCR_LIST:
      if (fromBoot) showToday();
      else onListPress(x, y);
      break;
    case SCR_BUSY:
      if (!fromBoot && onCloseButton(x, y)) cancelBusy();
      break;
    case SCR_LISTEN:
    case SCR_OFF:
      break;
  }
}

void handleLine(const String &s) {
  if (!s.startsWith("{")) return;
  JsonDocument doc;
  if (deserializeJson(doc, s)) return;
  lastPcMsg = millis();
  if (!doc["clock"].isNull()) setClock(doc["clock"].as<long long>());
  setPc(true);
  String t = doc["t"] | "";
  if (t == "today") {
    haveToday = true;
    tDay = clockValid() ? time(nullptr) / 86400 : -1;
    tDate = doc["date"] | "";
    tKcal = doc["kcal"] | 0.0f;
    tP = doc["protein"] | 0.0f;
    tF = doc["fat"] | 0.0f;
    tC = doc["carbs"] | 0.0f;
    int before = tMeals;
    tMeals = doc["meals"] | 0;
    tLast = doc["last"] | "";
    if (adding || (screen == SCR_RESULT && tMeals > before)) {   // answer to ADD (from here or the tray icon)
      adding = false;
      banner = "Added: " + tLast;
      showToday();
    } else if (screen == SCR_TODAY) {
      showToday();
    }
  } else if (t == "list") {
    JsonArray items = doc["items"].as<JsonArray>();
    nItems = 0;
    for (JsonObject it : items) {
      if (nItems >= MAX_ITEMS) break;
      itemName[nItems] = it["name"] | "?";
      itemTime[nItems] = it["time"] | "";
      itemKcal[nItems] = it["kcal"] | 0;
      nItems++;
    }
    armed = deleting = -1;
    if (listLoading || screen == SCR_LIST) {
      listLoading = false;
      showList();
    }
  } else if (t == "status") {
    if (replyIgnored()) return;                               // still working on the cancelled request
    if (screen != SCR_BUSY) adding = listLoading = false;   // a scan started from the tray icon
    showBusy(doc["msg"] | "...", "");
  } else if (t == "result") {
    if (replyIgnored()) { ignoreReply = false; return; }      // answer to a request cancelled with X
    picking = expectReply = false;
    lastResult = s;
    showResult(doc);
  } else if (t == "error") {
    if (replyIgnored()) { ignoreReply = false; return; }
    adding = listLoading = picking = expectReply = false;
    deleting = -1;
    showMessage("Error", doc["msg"] | "", TFT_RED);
  }
}

// PC off past midnight: the new day starts at zero here too (the PC sends the real totals when it is back)
void newDayOffline() {
  time_t t = time(nullptr);
  if (!clockValid() || !haveToday || t / 86400 == tDay) return;
  struct tm tm;
  gmtime_r(&t, &tm);
  char buf[24];
  strftime(buf, sizeof(buf), "%a %d %b %Y", &tm);   // same format as the PC's date
  tDate = buf;
  tDay = t / 86400;
  tKcal = tP = tF = tC = 0;
  tMeals = 0;
  tLast = "";
  if (screen == SCR_TODAY) showToday();
}

const char *resetName() {
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON: return "power-on";        // also the EN pin / USB auto-reset
    case ESP_RST_BROWNOUT: return "brownout";       // the 5 V dipped
    case ESP_RST_SW: return "software";
    case ESP_RST_PANIC: return "crash";
    default: return "other";
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(BOOT_BTN, INPUT_PULLUP);
  pinMode(BL_PIN, OUTPUT);
  analogWrite(BL_PIN, BL_ON);
  tft.init();
  tft.setRotation(1);
  tft.fillScreen(C_BG);
  drawHeader();
  showToday();
  line.reserve(4096);
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      line.trim();
      handleLine(line);
      line = "";
    } else if (line.length() < 4096) {
      line += c;
    }
  }

  uint32_t now = millis();
  if (!pcOnline && now - lastHello > 3000) {
    // uptime + reset reason: the PC logs them, so it shows whether the display restarted while the PC was off
    Serial.printf("HELLO food-cal 5 up=%lus reset=%s clock=%s\n", (unsigned long)(now / 1000), resetName(),
                  clockValid() ? "kept" : "unset");
    lastHello = now;
  }
  if (pcOnline && now - lastPcMsg > PC_TIMEOUT_MS) setPc(false);
  if (clockMinute() != clockShown) {
    drawHeader();
    if (!pcOnline) newDayOffline();
  }

  uint32_t age = now - screenSince;
  if (screen == SCR_RESULT) {
    if (age > RESULT_TIMEOUT_MS) showToday();
    else drawCountdown();
  } else if (screen == SCR_LISTEN) {
    int secs = age / 1000;
    if (secs != listenSecs) {                  // elapsed seconds while recording
      listenSecs = secs;
      tft.setTextDatum(MC_DATUM);
      tft.setTextColor(C_DIM, C_BG);
      tft.setTextPadding(80);
      tft.drawString(String(secs) + " s", W / 2, 170, 2);
      tft.setTextPadding(0);
    }
  } else if (screen == SCR_PICK) {
    if (age > LIST_TIMEOUT_MS) showToday();
  } else if (screen == SCR_LIST) {
    if (age > LIST_TIMEOUT_MS) showToday();
    else if (armed >= 0 && now - armedAt > ARM_TIMEOUT_MS) { armed = -1; drawList(); }
  } else if (screen == SCR_MESSAGE && age > MESSAGE_TIMEOUT_MS) {
    showToday();
  } else if (screen == SCR_BUSY && age > BUSY_TIMEOUT_MS) {
    adding = listLoading = false;
    showMessage("PC not responding", "Try again", TFT_RED);
  }

  uint16_t x, y;
  bool touching = tft.getTouch(&x, &y);
  if (touching) lastTouchMs = now;
  if (micActive) {                             // hold to talk: released (or too long) -> stop
    if ((!touching && now - lastTouchMs > RELEASE_MS) || now - screenSince > MAX_MIC_MS) stopMic();
  } else if (touching && !wasTouching) {
    onPress(x, y, false);
  }
  wasTouching = touching;

  bool bootDown = digitalRead(BOOT_BTN) == LOW;
  if (bootDown && !bootWasDown) onPress(0, 0, true);
  bootWasDown = bootDown;
  delay(10);
}
