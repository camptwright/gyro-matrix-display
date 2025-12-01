/*
  ESP32-S3 Feather + MPU6050 Gesture Controller
  Simple threshold-based gesture detection (based on provided example)
  
  Sends gesture events:
    GESTURE,<axis>,<direction>  (e.g., "GESTURE,yaw,left" or "GESTURE,pitch,up")
  
  Sends button presses:
    BUTTON,PRESS
  
  Wiring:
    MPU6050: 3V->3V, GND->GND, SDA->SDA, SCL->SCL
    Button:  D9 -> button -> GND  (INPUT_PULLUP; pressed=0)
*/

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <NimBLEDevice.h>

#define BUTTON_PIN       9
#define SAMPLE_HZ         50
#define BIAS_SECONDS      1.0f

// Gesture detection parameters (fine-tuned from CSV analysis)
// Based on analysis of rightleft.csv and updown.csv:
// - Right/Left flicks: gz peaks at 300-530 deg/s, durations 200-500ms
// - Up/Down flicks: gy peaks at 270-500 deg/s, durations 200-580ms

// Gyroscope thresholds (deg/s) - primary detection method
// From CSV analysis: gestures peak at 300-530 deg/s, but we want to catch them earlier
// Use lower threshold but require sustained detection
#define GESTURE_GYRO_THRESHOLD     150.0f   // deg/s to start detecting (lower to catch gestures early)
#define GESTURE_GYRO_CONFIRM       200.0f   // deg/s to confirm gesture (must reach this)

// Accelerometer thresholds (mapped to 0-255 range) - secondary/fallback
#define ACCEL_X_MIN      -17000
#define ACCEL_X_MAX      17000
#define ACCEL_Y_MIN      -17000
#define ACCEL_Y_MAX      17000
#define GESTURE_UP_THRESHOLD       145    // Y > 145 = up (accelerometer)
#define GESTURE_DOWN_THRESHOLD     80     // Y < 80 = down (accelerometer)
#define GESTURE_LEFT_THRESHOLD     155    // X > 155 = left (accelerometer)
#define GESTURE_RIGHT_THRESHOLD    80     // X < 80 = right (accelerometer)

// Gesture timing parameters (from analysis: gestures last 200-500ms)
#define GESTURE_COOLDOWN_MS        600    // 600ms between gestures (prevents double-trigger)
#define GESTURE_DEBOUNCE_MS        150    // Must hold gesture for 150ms (from analysis: min 200ms, use 150ms)
#define GESTURE_MIN_DURATION_MS    100    // Minimum gesture duration
#define GESTURE_MAX_DURATION_MS    800    // Maximum gesture duration (from analysis: max ~580ms)

// BLE UUIDs (Nordic UART Service)
static const char* NUS_SERVICE = "6e400001-b5a3-f393-e0a9-e50e24dcca9e";
static const char* NUS_TX      = "6e400003-b5a3-f393-e0a9-e50e24dcca9e";

Adafruit_MPU6050 mpu;
NimBLEServer* pServer = nullptr;
NimBLECharacteristic* pTx = nullptr;

float gxBias = 0, gyBias = 0, gzBias = 0;

inline float rad2deg(float r) { return r * 180.0f / PI; }

void bleSendLine(const String& line) {
    if (pTx && pServer && pServer->getConnectedCount() > 0) {
        String out = line;
        if (!out.endsWith("\n")) out += "\n";
        pTx->setValue((uint8_t*)out.c_str(), out.length());
        pTx->notify();
    }
    Serial.println(line);
}

class ServerCallbacks: public NimBLEServerCallbacks {
    void onConnect(NimBLEServer* s) { 
        Serial.println("BLE: connected"); 
    }
    void onDisconnect(NimBLEServer* s) { 
        Serial.println("BLE: disconnected, restarting advertising..."); 
        delay(50);
        auto* adv = NimBLEDevice::getAdvertising();
        if (adv) {
            adv->start();
            Serial.println("BLE: advertising restarted");
        } else {
            Serial.println("BLE: warning - advertising object not available");
        }
    }
};

void setupBLE() {
    NimBLEDevice::init("IMU Controller");
    NimBLEDevice::setDeviceName("IMU Controller");
    NimBLEDevice::setPower(ESP_PWR_LVL_P9);
    
    auto* server = NimBLEDevice::createServer();
    server->setCallbacks(new ServerCallbacks());
    
    auto* svc = server->createService(NUS_SERVICE);
    pTx = svc->createCharacteristic(NUS_TX, NIMBLE_PROPERTY::NOTIFY | NIMBLE_PROPERTY::READ);
    pTx->setValue("ready\n");
    svc->start();
    
    auto* adv = NimBLEDevice::getAdvertising();
    adv->addServiceUUID(NUS_SERVICE);
    NimBLEAdvertisementData resp;
    resp.setName("IMU Controller");
    adv->setScanResponseData(resp);
    adv->setMinInterval(32);
    adv->setMaxInterval(160);
    adv->start();
    
    pServer = server;
    Serial.println("BLE: advertising (auto-reconnect enabled, persistent)");
}

void setup() {
    Serial.begin(115200);
    delay(50);
    
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    delay(5);
    
    Wire.begin();
    if (!mpu.begin()) {
        Serial.println("MPU6050 not found!");
        while(1) delay(100);
    }
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);  // 8G range like example
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    
    // Calibrate gyro bias (still useful for raw data if needed)
    Serial.println("Calibrating gyro...");
    unsigned long t0 = millis();
    double sx = 0, sy = 0, sz = 0;
    uint32_t n = 0;
    while (millis() - t0 < (unsigned long)(1000.0f * BIAS_SECONDS)) {
        sensors_event_t a, g, t;
        mpu.getEvent(&a, &g, &t);
        sx += g.gyro.x;
        sy += g.gyro.y;
        sz += g.gyro.z;
        n++;
        delay(1);
    }
    gxBias = (float)(sx / max<uint32_t>(1, n));
    gyBias = (float)(sy / max<uint32_t>(1, n));
    gzBias = (float)(sz / max<uint32_t>(1, n));
    Serial.printf("Gyro bias: %.5f, %.5f, %.5f\n", gxBias, gyBias, gzBias);
    
    setupBLE();
    Serial.println("Gesture detection initialized (threshold-based)");
}

void loop() {
    // Ensure BLE is always advertising
    if (pServer && pServer->getConnectedCount() == 0) {
        static unsigned long last_adv_check = 0;
        unsigned long now = millis();
        if (now - last_adv_check > 5000) {
            last_adv_check = now;
            auto* adv = NimBLEDevice::getAdvertising();
            if (adv && !adv->isAdvertising()) {
                Serial.println("BLE: Restarting advertising (was stopped)");
                adv->start();
            }
        }
    }
    
    // Sample at fixed rate
    static const unsigned long period_ms = (unsigned long)(1000.0f / SAMPLE_HZ);
    static unsigned long last_ms = 0;
    unsigned long now = millis();
    if (now - last_ms < period_ms) {
        delay(1);
        return;
    }
    last_ms = now;
    
    // Read IMU
    sensors_event_t a, g, t;
    mpu.getEvent(&a, &g, &t);
    
    // Get accelerometer values (in m/s^2, convert to raw-like values)
    // The example uses raw values in range -17000 to 17000
    // Adafruit library gives m/s^2, so we need to scale appropriately
    // 1G = 9.8 m/s^2, so for 8G range: ±78.4 m/s^2
    // Map to -17000 to 17000 range
    float ax_raw = (a.acceleration.x / 78.4f) * 17000.0f;
    float ay_raw = (a.acceleration.y / 78.4f) * 17000.0f;
    
    // Map to 0-255 range like the example
    byte data_X = map((int)ax_raw, ACCEL_X_MIN, ACCEL_X_MAX, 0, 255);
    byte data_Y = map((int)ay_raw, ACCEL_Y_MIN, ACCEL_Y_MAX, 0, 255);
    
    // Get gyroscope data for gesture detection
    float gx_dps = rad2deg(g.gyro.x - gxBias);  // roll (not used)
    float gy_dps = rad2deg(g.gyro.y - gyBias);  // pitch (up/down)
    float gz_dps = rad2deg(g.gyro.z - gzBias);  // yaw (left/right)
    
    // Button handling (debounced)
    static int last_btn = HIGH;
    static unsigned long last_edge_ms = 0;
    int btn = digitalRead(BUTTON_PIN);
    if (btn != last_btn && (now - last_edge_ms) >= 120) {
        last_edge_ms = now;
        last_btn = btn;
        if (btn == LOW) {
            bleSendLine("BUTTON,PRESS");
            Serial.println("Button pressed");
        }
    }
    
    // Simplified gesture detection using gyroscope
    // Based on CSV: gestures peak at 300-530 deg/s, last 200-500ms
    static unsigned long last_gesture_time = 0;
    static unsigned long gesture_start_time = 0;
    static String detected_gesture = "";
    static float peak_value = 0.0f;
    static bool gesture_sent = false;  // Track if we've already sent this gesture
    
    // Check cooldown
    if (now - last_gesture_time < GESTURE_COOLDOWN_MS) {
        return;
    }
    
    float abs_gy = abs(gy_dps);  // For up/down (pitch)
    float abs_gz = abs(gz_dps);  // For left/right (yaw)
    
    // Detect gesture: value exceeds threshold
    String current_gesture = "";
    if (abs_gy > GESTURE_GYRO_THRESHOLD) {
        current_gesture = (gy_dps > 0) ? "GESTURE,pitch,up" : "GESTURE,pitch,down";
    } else if (abs_gz > GESTURE_GYRO_THRESHOLD) {
        current_gesture = (gz_dps > 0) ? "GESTURE,yaw,right" : "GESTURE,yaw,left";
    }
    
    // Gesture state machine
    if (current_gesture != "") {
        // Gesture detected
        if (current_gesture == detected_gesture) {
            // Same gesture continuing - track peak and duration
            float current_peak = (abs_gy > abs_gz) ? abs_gy : abs_gz;
            if (current_peak > peak_value) {
                peak_value = current_peak;
            }
            
            // Check if we should send the gesture
            unsigned long duration = now - gesture_start_time;
            if (!gesture_sent && 
                peak_value >= GESTURE_GYRO_CONFIRM && 
                duration >= GESTURE_DEBOUNCE_MS &&
                duration <= GESTURE_MAX_DURATION_MS) {
                // Valid gesture - send it once
                bleSendLine(current_gesture);
                Serial.printf("%s (peak=%.1f deg/s, dur=%lu ms)\n", 
                              current_gesture.c_str(), peak_value, duration);
                last_gesture_time = now;
                gesture_sent = true;
            }
            
            // Reset if gesture goes too long
            if (duration > GESTURE_MAX_DURATION_MS) {
                detected_gesture = "";
                peak_value = 0.0f;
                gesture_sent = false;
            }
        } else {
            // New/different gesture detected - start tracking
            detected_gesture = current_gesture;
            gesture_start_time = now;
            peak_value = (abs_gy > abs_gz) ? abs_gy : abs_gz;
            gesture_sent = false;
        }
    } else {
        // No gesture detected - reset tracking
        if (detected_gesture != "") {
            unsigned long duration = now - gesture_start_time;
            // If gesture ended and we haven't sent it, check if it was valid
            if (!gesture_sent && duration >= GESTURE_MIN_DURATION_MS && peak_value >= GESTURE_GYRO_CONFIRM) {
                // Send gesture that just ended
                bleSendLine(detected_gesture);
                Serial.printf("%s (peak=%.1f deg/s, dur=%lu ms, ended)\n", 
                              detected_gesture.c_str(), peak_value, duration);
                last_gesture_time = now;
                gesture_sent = true;
            }
            // Reset after a short delay to allow gesture to complete
            if (duration > GESTURE_MAX_DURATION_MS || (gesture_sent && duration > 100)) {
                detected_gesture = "";
                peak_value = 0.0f;
                gesture_sent = false;
            }
        }
    }
}
