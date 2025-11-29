#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// WiFi + HTTPS for cloud logging
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>

// OTA support
#include <ArduinoOTA.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// === pins ===
#define SOIL_PIN 34
#define LDR_PIN  32

// === calibration ===
const int SOIL_WET_RAW   = 700;
const int SOIL_DRY_RAW   = 2300;
const int LDR_DARK_RAW   = 450;
const int LDR_BRIGHT_RAW = 3000;

// === tuning ===
int clampPct(int v){ return v<0 ? 0 : (v > 100 ? 100 : v); }
int soilToPct(int raw){ return clampPct(map(raw, SOIL_DRY_RAW, SOIL_WET_RAW, 0, 100)); }
int lightToPct(int raw){ return clampPct(map(raw, LDR_DARK_RAW, LDR_BRIGHT_RAW, 0, 100)); }

// === WiFi credentials ===
const char* WIFI_SSID = "Aain";      // your WiFi SSID
const char* WIFI_PASS = "baingann";  // your WiFi password

const int MAX_RETRY_ATTEMPTS = 5;
const int RETRY_DELAY = 5000;  // ms

// === InfluxDB Cloud config ===
const char* INFLUX_WRITE_URL =
  "https://us-east-1-1.aws.cloud2.influxdata.com/api/v2/write?org=PlantPet&bucket=PlantPet&precision=s";

// IMPORTANT: put your real token back here locally, not in chat
const char* INFLUX_TOKEN       = "api_token_goes_here";

const char* INFLUX_MEASUREMENT = "plant_status";
const char* INFLUX_DEVICE_ID   = "plantpet-01";

// === Supabase config ===
// Use your real table name here; assuming table is: plantpet_mins
const char* SUPABASE_URL =
  "https://cwrnkigirfwvtsyazcoz.supabase.co/rest/v1/plantpetmins";

// IMPORTANT: put your real anon key back here locally, not in chat
const char* SUPABASE_ANON_KEY = "api_token_goes_here";

// === 10-minute aggregation ===
const unsigned long LOG_INTERVAL_MS = 600000UL;  // 10 minutes
unsigned long lastSendMs = 0;
long aggSoilSum  = 0;
long aggLightSum = 0;
long aggScoreSum = 0;
long aggCount    = 0;

// ================= Display helpers =================
void drawFace(const char* mood){
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(45, 0);
  display.println(mood);

  if (strcmp(mood,"HAPPY")==0){
    display.fillCircle(40,30,5,SSD1306_WHITE);
    display.fillCircle(88,30,5,SSD1306_WHITE);
    display.drawLine(40,50,50,55,SSD1306_WHITE);
    display.drawLine(50,55,78,55,SSD1306_WHITE);
    display.drawLine(78,55,88,50,SSD1306_WHITE);
  }
  else if (strcmp(mood,"OK")==0){
    display.fillCircle(40,30,5,SSD1306_WHITE);
    display.fillCircle(88,30,5,SSD1306_WHITE);
    display.drawLine(40,50,88,50,SSD1306_WHITE);
  }
  else if (strcmp(mood,"ANGRY")==0){
    display.drawLine(35,25,45,35,SSD1306_WHITE);
    display.drawLine(83,25,93,35,SSD1306_WHITE);
    display.drawLine(45,50,83,50,SSD1306_WHITE);
  }
  else if (strcmp(mood,"DEAD")==0){
    display.drawLine(35,25,45,35,SSD1306_WHITE);
    display.drawLine(45,25,35,35,SSD1306_WHITE);
    display.drawLine(83,25,93,35,SSD1306_WHITE);
    display.drawLine(93,25,83,35,SSD1306_WHITE);
    display.drawLine(40,55,88,55,SSD1306_WHITE);
  }
  display.display();
}

void drawHeartbeat(int base) {
  static int frame = 0;
  frame++;

  float pulse = 1.0 + 0.2 * sin(frame * 0.2);
  int dynamic = constrain((int)(base * pulse), 0, 100);
  int width = map(dynamic, 0, 100, 0, SCREEN_WIDTH);

  display.fillRect(0, 55, SCREEN_WIDTH, 6, SSD1306_BLACK);
  display.fillRect(0, 55, width, 6, SSD1306_WHITE);
  display.display();
}

// ================= WiFi with logging =================
void connectToWiFi() {
  int attempt = 0;

  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true);
  delay(100);

  Serial.println();
  Serial.println("--------------------------------");
  Serial.println("[WiFi] Connecting...");
  Serial.print("[WiFi] SSID: ");
  Serial.println(WIFI_SSID);
  Serial.println("--------------------------------");

  while (attempt < MAX_RETRY_ATTEMPTS) {
    attempt++;

    Serial.print("[WiFi] Attempt ");
    Serial.println(attempt);

    WiFi.begin(WIFI_SSID, WIFI_PASS);

    int timeout = 0;
    while (WiFi.status() != WL_CONNECTED && timeout < 20) {
      delay(500);
      Serial.print(".");
      timeout++;
    }

    if (WiFi.status() == WL_CONNECTED) {
      Serial.println();
      Serial.println("[WiFi] Connected successfully!");
      Serial.print("[WiFi] IP Address: ");
      Serial.println(WiFi.localIP());
      Serial.println("--------------------------------");
      return;
    }

    Serial.println();
    Serial.println("[WiFi] Failed, retrying...");
    delay(RETRY_DELAY);
  }

  Serial.println("[WiFi] Could not connect after retries, restarting ESP32...");
  delay(2000);
  ESP.restart();
}

// ================= OTA =================
void setupOTA() {
  ArduinoOTA.setHostname("PlantPet-ESP32");

  ArduinoOTA.onStart([]() {
    Serial.println();
    Serial.println("[OTA] Start updating...");
  });

  ArduinoOTA.onEnd([]() {
    Serial.println();
    Serial.println("[OTA] Finished!");
  });

  ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
    Serial.printf("[OTA] %u%%\r", (progress * 100) / total);
  });

  ArduinoOTA.onError([](ota_error_t error) {
    Serial.printf("\n[OTA] Error[%u]\n", error);
  });
}

// ================= InfluxDB sender =================
void sendToInflux(float avgSoil, float avgLight, float avgScore) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[InfluxDB] Skipped (WiFi not connected)");
    return;
  }

  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;

  if (!http.begin(client, INFLUX_WRITE_URL)) {
    Serial.println("[InfluxDB] http.begin() failed");
    return;
  }

  String line =
    String(INFLUX_MEASUREMENT) + ",device_id=" + INFLUX_DEVICE_ID +
    " soil_pct=" + String(avgSoil,1) +
    ",ldr_pct=" + String(avgLight,1) +
    ",happiness=" + String((int)avgScore) + "i";

  http.addHeader("Authorization", String("Token ") + INFLUX_TOKEN);
  http.addHeader("Content-Type", "text/plain; charset=utf-8");

  int code = http.POST(line);

  if (code == 204) {
    Serial.println("[InfluxDB] OK (204) Data written successfully");
  } else {
    Serial.print("[InfluxDB] Error: ");
    Serial.println(code);
    String resp = http.getString();
    Serial.print("[InfluxDB] Response: ");
    Serial.println(resp);
  }

  http.end();
}

// ================= Supabase sender =================
void sendToSupabase(float avgSoil, float avgLight, float avgScore) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[Supabase] Skipped (WiFi not connected)");
    return;
  }

  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;

  if (!http.begin(client, SUPABASE_URL)) {
    Serial.println("[Supabase] http.begin() failed");
    return;
  }

  http.addHeader("apikey", SUPABASE_ANON_KEY);
  http.addHeader("Authorization", String("Bearer ") + SUPABASE_ANON_KEY);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Prefer", "return=minimal");

  String body =
    "{\"device_id\":\"" + String(INFLUX_DEVICE_ID) +
    "\",\"soil_pct\":" + String(avgSoil,1) +
    ",\"ldr_pct\":" + String(avgLight,1) +
    ",\"happiness\":" + String((int)avgScore) + "}";

  int code = http.POST(body);

  if (code == 201 || code == 204) {
    Serial.print("[Supabase] OK (");
    Serial.print(code);
    Serial.println(") Row inserted successfully");
  } else {
    Serial.print("[Supabase] Error: ");
    Serial.println(code);
    String resp = http.getString();
    Serial.print("[Supabase] Response: ");
    Serial.println(resp);
  }

  http.end();
}

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println();
  Serial.println("ESP32 Plant Pet v2 starting...");

  connectToWiFi();

  setupOTA();
  ArduinoOTA.begin();

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED not found at 0x3C");
    while (true) {
      delay(1000);
    }
  }

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(10, 25);
  display.println("Hello from Plant Pet!");
  display.display();
  delay(1500);
}

// ==================== LOOP ====================
void loop() {
  ArduinoOTA.handle();  // keep OTA responsive

  int soilRaw = analogRead(SOIL_PIN);
  int ldrRaw  = analogRead(LDR_PIN);

  int soilPct  = soilToPct(soilRaw);
  int lightPct = lightToPct(ldrRaw);

  int score = (soilPct * 7.7 + lightPct * 2.5) / 10;

  // aggregate for cloud logging
  aggSoilSum  += soilPct;
  aggLightSum += lightPct;
  aggScoreSum += score;
  aggCount++;

  // send every 10 minutes
  unsigned long now = millis();
  if (now - lastSendMs >= LOG_INTERVAL_MS && aggCount > 0) {
    float avgSoil  = float(aggSoilSum)  / aggCount;
    float avgLight = float(aggLightSum) / aggCount;
    float avgScore = float(aggScoreSum) / aggCount;

    Serial.println();
    Serial.println("========== 10-min summary ==========");
    Serial.print("avgSoil: ");  Serial.println(avgSoil);
    Serial.print("avgLight: "); Serial.println(avgLight);
    Serial.print("avgScore: "); Serial.println(avgScore);

    sendToInflux(avgSoil, avgLight, avgScore);
    sendToSupabase(avgSoil, avgLight, avgScore);

    aggSoilSum = aggLightSum = aggScoreSum = 0;
    aggCount   = 0;
    lastSendMs = now;
    Serial.println("====================================");
  }

  // === Slide 1: vitals + heartbeat ===
  unsigned long slideStart = millis();
  while (millis() - slideStart < 2500) {
    ArduinoOTA.handle();

    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println(" Plant Vitals");
    display.setCursor(0, 18);
    display.printf("Soil: %d%%\n", soilPct);
    display.setCursor(0, 30);
    display.printf("Light: %d%%\n", lightPct);
    display.setCursor(0, 42);
    display.printf("Happy?: %d%%", score);
    drawHeartbeat(score);
    delay(80);
  }

  // === Slide 2: mood face ===
  if (score >= 70)       drawFace("HAPPY");
  else if (score >= 45)  drawFace("OK");
  else if (score >= 25)  drawFace("ANGRY");
  else                   drawFace("DEAD");

  for (int i = 0; i < 25; i++) { // 25 * 100ms = 2.5s
    ArduinoOTA.handle();
    delay(100);
  }
}
