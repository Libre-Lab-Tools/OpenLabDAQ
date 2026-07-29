/*
  FurnaceTC Arduino Firmware
  --------------------------

  Reads a K-type thermocouple using a MAX31855 amplifier.

  Standard OpenLabDAQ protocol:

      ID?      -> FurnaceTC
      READ?    -> <fresh temperature in C> or ERROR
      STATUS?  -> OK or ERROR

  Each READ? command performs one new hardware measurement. The firmware
  does not return an older value, count failures, retry communication, or
  reconnect the serial port. OpenLabDAQ handles communication retries and
  reconnection in Python.
*/

#include <SPI.h>
#include <Adafruit_MAX31855.h>


// ==========================================================
// Instrument settings
// ==========================================================

const char* SENSOR_NAME = "FurnaceTC";


// ==========================================================
// MAX31855 connections
// ==========================================================

const int thermoDO = 12;
const int thermoCS = 10;
const int thermoCLK = 13;

Adafruit_MAX31855 thermocouple(
    thermoCLK,
    thermoCS,
    thermoDO
);


// ==========================================================
// Setup and loop
// ==========================================================

void setup()
{
    Serial.begin(9600);

    // Give the MAX31855 time to stabilize after startup.
    delay(500);
}

void loop()
{
    handleSerial();
}


// ==========================================================
// Sensor reading
// ==========================================================

bool readTemperature(double& temperature)
{
    temperature = thermocouple.readCelsius();
    return !isnan(temperature);
}


// ==========================================================
// Serial command protocol
// ==========================================================

void handleSerial()
{
    if (!Serial.available())
    {
        return;
    }

    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "ID?")
    {
        Serial.println(SENSOR_NAME);
    }
    else if (command == "READ?")
    {
        double temperature;

        if (readTemperature(temperature))
        {
            // Report whole degrees so the Arduino display matches the
            // resolution used by the furnace controller.
            long roundedTemperature = (long)round(temperature);
            Serial.println(roundedTemperature);
        }
        else
        {
            Serial.println("ERROR");
        }
    }
    else if (command == "STATUS?")
    {
        double temperature;
        Serial.println(readTemperature(temperature) ? "OK" : "ERROR");
    }
}
