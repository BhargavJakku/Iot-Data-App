#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// === pins ===
#define SOIL_PIN 34
#define LDR_PIN  32

// === calibration ===
const int SOIL_WET_RAW = 700;
const int SOIL_DRY_RAW = 2300;
const int LDR_DARK_RAW = 450;
const int LDR_BRIGHT_RAW = 3000;

// === tuning ===
int clampPct(int v){ return v<0?0:(v>100?100:v); }
int soilToPct(int raw){ return clampPct(map(raw, SOIL_DRY_RAW, SOIL_WET_RAW, 0, 100)); }
int lightToPct(int raw){ return clampPct(map(raw, LDR_DARK_RAW, LDR_BRIGHT_RAW, 0, 100)); }

// === display helpers ===
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

// === heartbeat animation ===
void drawHeartbeat(int base) {
  static int frame = 0;
  frame++;
  
  // pulse between 80%–120% of base using a sine wave
  float pulse = 1.0 + 0.2 * sin(frame * 0.2);
  int dynamic = constrain((int)(base * pulse), 0, 100);
  int width = map(dynamic, 0, 100, 0, SCREEN_WIDTH);

  display.fillRect(0, 55, SCREEN_WIDTH, 6, SSD1306_BLACK); // clear bar area
  display.fillRect(0, 55, width, 6, SSD1306_WHITE);
  display.display();
}


// === setup ===
void setup(){
  Serial.begin(115200);
  delay(1000);
  Serial.println(" ESP32 Plant Pet v2 starting...");

  if(!display.begin(SSD1306_SWITCHCAPVCC,0x3C)){
    Serial.println(" OLED not found");
    while(true);
  }
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(10,25);
  display.println("Hello from Plant Pet!");
  display.display();
  delay(1500);
}

// === main loop ===
void loop(){
  int soilRaw = analogRead(SOIL_PIN);
  int ldrRaw  = analogRead(LDR_PIN);

  int soilPct  = soilToPct(soilRaw);
  int lightPct = lightToPct(ldrRaw);

  int score = (soilPct * 7.7 + lightPct * 2.5) / 10;

  Serial.print("SoilRaw: "); Serial.print(soilRaw);
  Serial.print(" | Soil%: "); Serial.print(soilPct);
  Serial.print(" | LightRaw: "); Serial.print(ldrRaw);
  Serial.print(" | Light%: "); Serial.print(lightPct);
  Serial.print(" | Score: "); Serial.println(score);


// === slide 1: live status with heartbeat animation ===
unsigned long start = millis();
while (millis() - start < 2500) {     // stay on this slide for 2.5 s
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0,0);
  display.println(" Plant Vitals");
  display.setCursor(0,18);
  display.printf("Soil: %d%%\n", soilPct);
  display.setCursor(0,30);
  display.printf("Light: %d%%\n", lightPct);
  display.setCursor(0,42);
  display.printf("Happy?: %d%%", score);
  drawHeartbeat(score);               // animated bar
  delay(80);                          // controls pulse speed
}


  // === slide 2: emotion face ===
  if (score >= 70)       drawFace("HAPPY");
  else if (score >= 45)  drawFace("OK");
  else if (score >= 25)  drawFace("ANGRY");
  else                   drawFace("DEAD");

  delay(2500); // stay on face before looping
}
