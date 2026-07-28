/*
  FurnaceTC Arduino Firmware
  --------------------------

  Reads a K-type thermocouple using a MAX31855 amplifier.

  Standard communication protocol:

      ID?      -> FurnaceTC
      READ?    -> <temperature> or ERROR
      STATUS?  -> OK or ERROR

  Temporary failed readings do not immediately erase the last valid
  temperature. The sensor reports ERROR only after several consecutive
  failures.
  
  last edit increased the reading period from 100ms to 250ms to give enough time to the amplifier.
  also it only flags an error if there are repeated error readings
*/

#include <SPI.h>
#include <Adafruit_MAX31855.h>

// ==========================================================
// Sensor Settings
// ==========================================================

const char* SENSOR_NAME = "FurnaceTC";
const char* UNIT = "C";

// The MAX31855 does not need to be read every 100 ms.
const unsigned long SENSOR_PERIOD = 250;

// Number of consecutive failures required before reporting ERROR.
const int MAX_FAILED_READS = 5;

// ==========================================================
// MAX31855 Connections
// ==========================================================

const int thermoDO  = 12;
const int thermoCS  = 10;
const int thermoCLK = 13;

Adafruit_MAX31855 thermocouple(
    thermoCLK,
    thermoCS,
    thermoDO
);

// ==========================================================
// Global Variables
// ==========================================================

unsigned long lastSensorTime = 0;

double temperature = NAN;

int failedReads = 0;
bool sensorOK = false;

// ==========================================================
// Setup
// ==========================================================

void setup()
{
    Serial.begin(9600);

    // Give the MAX31855 time to stabilize after startup.
    delay(500);
}

// ==========================================================
// Main Loop
// ==========================================================

void loop()
{
    updateSensor();
    handleSerial();
}

// ==========================================================
// Read Thermocouple
// ==========================================================

void updateSensor()
{
    unsigned long currentTime = millis();

    if (currentTime - lastSensorTime < SENSOR_PERIOD)
        return;

    lastSensorTime = currentTime;

    double newTemperature = thermocouple.readCelsius();

    if (!isnan(newTemperature))
    {
        // Store the newest valid measurement.
        temperature = newTemperature;

        failedReads = 0;
        sensorOK = true;
    }
    else
    {
        failedReads++;

        // Ignore occasional temporary failures, but do not keep
        // returning an old value indefinitely.
        if (failedReads >= MAX_FAILED_READS)
        {
            sensorOK = false;
        }
    }
}

// ==========================================================
// Handle Serial Commands
// ==========================================================

void handleSerial()
{
    if (!Serial.available())
        return;

    String command = Serial.readStringUntil('\n');
    command.trim();

    //--------------------------------------------------------
    // Return sensor identification
    //--------------------------------------------------------

    if (command == "ID?")
    {
        Serial.println(SENSOR_NAME);
    }

    //--------------------------------------------------------
    // Return latest valid temperature
    //--------------------------------------------------------

    else if (command == "READ?")
    {
        if (!sensorOK || isnan(temperature))
        {
            Serial.println("ERROR");
        }
        else
        {
            Serial.println(temperature, 2);
        }
    }

    //--------------------------------------------------------
    // Return sensor status
    //--------------------------------------------------------

    else if (command == "STATUS?")
    {
        if (sensorOK)
        {
            Serial.println("OK");
        }
        else
        {
            Serial.println("ERROR");
        }
    }
}