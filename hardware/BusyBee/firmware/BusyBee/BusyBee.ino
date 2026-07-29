/*
  BusyBee Arduino Firmware
  ------------------------

  Reads the Busy Bee analog pressure output using an ADS1115.

  Standard OpenLabDAQ protocol:

      ID?      -> BusyBee
      READ?    -> <fresh pressure in Torr> or ERROR
      STATUS?  -> OK or ERROR

  Each READ? command performs one new hardware measurement. The firmware
  does not return an older value, count failures, retry communication, or
  reconnect the serial port. OpenLabDAQ handles communication retries and
  reconnection in Python.
*/

#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include <math.h>


// ==========================================================
// Instrument settings
// ==========================================================

const char* SENSOR_NAME = "BusyBee";


// ==========================================================
// ADS1115 hardware configuration
// ==========================================================

Adafruit_ADS1115 ads;

const uint8_t ADC_I2C_ADDRESS = 0x48;
const uint8_t ADC_CHANNEL = 1;

const float R_TOP_OHMS = 10030.0;
const float R_BOTTOM_OHMS = 9960.0;

bool adcReady = false;


// ==========================================================
// Busy Bee pressure correction
// ==========================================================

const float BRANCH_THRESHOLD_TORR = 1.0;
const float HIGH_BRANCH_OFFSET_TORR = 36.25;


// ==========================================================
// Setup and loop
// ==========================================================

void setup()
{
    Serial.begin(9600);

    // Do not print unsolicited startup text.
    delay(500);

    initializeADC();
}

void loop()
{
    handleSerial();
}


// ==========================================================
// ADS1115 access
// ==========================================================

bool initializeADC()
{
    if (!ads.begin(ADC_I2C_ADDRESS))
    {
        adcReady = false;
        return false;
    }

    // Approximately 8 V before the divider becomes about 4 V at A1.
    ads.setGain(GAIN_ONE);

    adcReady = true;
    return true;
}

bool adcIsPresent()
{
    Wire.beginTransmission(ADC_I2C_ADDRESS);
    return Wire.endTransmission() == 0;
}

bool readPressure(float& pressureTorr)
{
    // If the ADC was previously unavailable, one new READ? request also
    // performs one new initialization attempt.
    if (!adcReady && !initializeADC())
    {
        return false;
    }

    if (!adcIsPresent())
    {
        adcReady = false;
        return false;
    }

    int16_t rawADC = ads.readADC_SingleEnded(ADC_CHANNEL);

    if (rawADC < 0)
    {
        return false;
    }

    float adcVoltage = ads.computeVolts(rawADC);

    float dividerMultiplier = (
        R_TOP_OHMS + R_BOTTOM_OHMS
    ) / R_BOTTOM_OHMS;

    float busyBeeVoltage = adcVoltage * dividerMultiplier;

    float rawPressureTorr = pow(
        10.0,
        busyBeeVoltage - 5.0
    );

    if (isnan(rawPressureTorr) || isinf(rawPressureTorr))
    {
        return false;
    }

    if (rawPressureTorr < BRANCH_THRESHOLD_TORR)
    {
        pressureTorr = rawPressureTorr;
    }
    else
    {
        pressureTorr = rawPressureTorr - HIGH_BRANCH_OFFSET_TORR;

        if (pressureTorr < 0.0)
        {
            pressureTorr = 0.0;
        }
    }

    return !isnan(pressureTorr) && !isinf(pressureTorr);
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
        float pressureTorr;

        if (readPressure(pressureTorr))
        {
            printScientificPressure(pressureTorr, 6);
        }
        else
        {
            Serial.println("ERROR");
        }
    }
    else if (command == "STATUS?")
    {
        float pressureTorr;
        Serial.println(readPressure(pressureTorr) ? "OK" : "ERROR");
    }
}


// ==========================================================
// Numeric output formatting
// ==========================================================

void printScientificPressure(float value, uint8_t decimalPlaces)
{
    if (value == 0.0)
    {
        Serial.println("0.000000e+00");
        return;
    }

    int exponent = floor(log10(value));
    float mantissa = value / pow(10.0, exponent);

    if (mantissa >= 10.0)
    {
        mantissa /= 10.0;
        exponent++;
    }
    else if (mantissa < 1.0)
    {
        mantissa *= 10.0;
        exponent--;
    }

    Serial.print(mantissa, decimalPlaces);
    Serial.print("e");
    Serial.print(exponent >= 0 ? "+" : "-");

    int absoluteExponent = abs(exponent);

    if (absoluteExponent < 10)
    {
        Serial.print("0");
    }

    Serial.println(absoluteExponent);
}
