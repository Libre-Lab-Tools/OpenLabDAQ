/*
  BusyBee Arduino Firmware
  ------------------------

  Reads the Busy Bee analog pressure output using an ADS1115.

  The firmware continuously calculates the corrected pressure and
  exposes it through the standard OpenLabDAQ serial protocol:

      ID?      -> BusyBee
      READ?    -> <pressure in Torr> or ERROR
      STATUS?  -> OK or ERROR

  The Python driver opens and closes the Arduino USB serial port.
  Separate CONNECT and DISCONNECT serial commands are not required.

  Connections
  -----------

  Arduino Nano       ADS1115
  ------------       -------
  5V                 VDD
  GND                GND
  A4                 SDA
  A5                 SCL

  Busy Bee voltage divider:

  Busy Bee output ---- R_TOP ----+---- ADS1115 A1
                                 |
                              R_BOTTOM
                                 |
                                GND

  Busy Bee analog common must connect to Arduino/ADS1115 GND.

  Optional filter:
      0.1 uF capacitor between ADS1115 A1 and GND.

  Calibration
  -----------
  The measured divider resistances and Busy Bee pressure correction
  are grouped near the top of this file so they can be edited easily.
*/

#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include <math.h>


// ==========================================================
// Instrument settings
// ==========================================================

const char* SENSOR_NAME = "BusyBee";
const char* UNIT = "Torr";

const unsigned long SENSOR_PERIOD_MS = 500;
const unsigned long ADC_RETRY_PERIOD_MS = 2000;


// ==========================================================
// ADS1115 hardware configuration
// ==========================================================

Adafruit_ADS1115 ads;

// Default ADS1115 I2C address when ADDR is connected to GND.
const uint8_t ADC_I2C_ADDRESS = 0x48;

// Channel 1 corresponds to the ADS1115 terminal labeled A1.
const uint8_t ADC_CHANNEL = 1;

// Measured divider resistance values.
const float R_TOP_OHMS = 10030.0;
const float R_BOTTOM_OHMS = 9960.0;


// ==========================================================
// Busy Bee pressure correction
// ==========================================================

// Above this raw pressure, the gauge is considered to have
// switched to its offset high-pressure branch.
const float BRANCH_THRESHOLD_TORR = 1.0;

// Offset observed after the gauge changes branches.
const float HIGH_BRANCH_OFFSET_TORR = 36.25;


// ==========================================================
// Runtime state
// ==========================================================

unsigned long lastSensorTime = 0;
unsigned long lastAdcRetryTime = 0;

float pressureTorr = NAN;

bool adcReady = false;
bool sensorOK = false;


// ==========================================================
// Setup
// ==========================================================

void setup()
{
    Serial.begin(9600);

    /*
      Do not print startup messages. The Python driver expects the
      serial connection to contain only replies to commands.
    */
    delay(500);

    initializeADC();
}


// ==========================================================
// Main loop
// ==========================================================

void loop()
{
    updateSensor();
    handleSerial();
}


// ==========================================================
// ADS1115 initialization and detection
// ==========================================================

bool initializeADC()
{
    lastAdcRetryTime = millis();

    if (!ads.begin(ADC_I2C_ADDRESS))
    {
        adcReady = false;
        sensorOK = false;
        return false;
    }

    /*
      GAIN_ONE provides an ADC full-scale range of +/-4.096 V.

      With the approximately 1:1 voltage divider:
          8 V Busy Bee output -> approximately 4 V at A1
    */
    ads.setGain(GAIN_ONE);

    adcReady = true;
    return true;
}


bool adcIsPresent()
{
    /*
      Confirm that the ADS1115 still responds before requesting a
      conversion. This lets the firmware report ERROR if the board
      is disconnected while OpenLabDAQ is running.
    */
    Wire.beginTransmission(ADC_I2C_ADDRESS);
    return Wire.endTransmission() == 0;
}


// ==========================================================
// Read and calculate pressure
// ==========================================================

void updateSensor()
{
    unsigned long currentTime = millis();

    // Retry ADS1115 initialization periodically if it was unavailable.
    if (!adcReady)
    {
        if (
            currentTime - lastAdcRetryTime
            >= ADC_RETRY_PERIOD_MS
        )
        {
            initializeADC();
        }

        if (!adcReady)
        {
            return;
        }
    }

    if (
        currentTime - lastSensorTime
        < SENSOR_PERIOD_MS
    )
    {
        return;
    }

    lastSensorTime = currentTime;

    if (!adcIsPresent())
    {
        adcReady = false;
        sensorOK = false;
        return;
    }

    // Read the voltage-divider output at ADS1115 A1.
    int16_t rawADC = ads.readADC_SingleEnded(
        ADC_CHANNEL
    );

    /*
      A single-ended input should not be negative. A negative result
      indicates an invalid measurement or wiring problem.
    */
    if (rawADC < 0)
    {
        sensorOK = false;
        return;
    }

    // Voltage physically reaching the ADS1115 input.
    float adcVoltage = ads.computeVolts(rawADC);

    // Reconstruct the original Busy Bee output voltage.
    float dividerMultiplier = (
        R_TOP_OHMS + R_BOTTOM_OHMS
    ) / R_BOTTOM_OHMS;

    float busyBeeVoltage = (
        adcVoltage * dividerMultiplier
    );

    /*
      Busy Bee logarithmic analog-output equation:

          Pressure in Torr = 10^(Voltage - 5)
    */
    float rawPressureTorr = pow(
        10.0,
        busyBeeVoltage - 5.0
    );

    if (
        isnan(rawPressureTorr)
        || isinf(rawPressureTorr)
    )
    {
        sensorOK = false;
        return;
    }

    // Apply the observed branch correction.
    float correctedPressureTorr;

    if (
        rawPressureTorr
        < BRANCH_THRESHOLD_TORR
    )
    {
        correctedPressureTorr = rawPressureTorr;
    }
    else
    {
        correctedPressureTorr = (
            rawPressureTorr
            - HIGH_BRANCH_OFFSET_TORR
        );

        /*
          Prevent a slightly negative pressure near the branch
          transition.
        */
        if (correctedPressureTorr < 0.0)
        {
            correctedPressureTorr = 0.0;
        }
    }

    if (
        isnan(correctedPressureTorr)
        || isinf(correctedPressureTorr)
    )
    {
        sensorOK = false;
        return;
    }

    pressureTorr = correctedPressureTorr;
    sensorOK = true;
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

    //--------------------------------------------------------
    // Return instrument identification
    //--------------------------------------------------------

    if (command == "ID?")
    {
        Serial.println(SENSOR_NAME);
    }

    //--------------------------------------------------------
    // Return the latest valid pressure
    //--------------------------------------------------------

    else if (command == "READ?")
    {
        if (!sensorOK || isnan(pressureTorr))
        {
            Serial.println("ERROR");
        }
        else
        {
            printScientificPressure(
                pressureTorr,
                6
            );
        }
    }

    //--------------------------------------------------------
    // Return instrument status
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


// ==========================================================
// Numeric output formatting
// ==========================================================

void printScientificPressure(
    float value,
    uint8_t decimalPlaces
)
{
    /*
      Print pressure in a portable scientific-notation format,
      for example:

          7.600000e+02
          1.234567e-04

      Python float() accepts this format directly.
    */

    if (value == 0.0)
    {
        Serial.println("0.000000e+00");
        return;
    }

    int exponent = floor(log10(value));

    float mantissa = (
        value / pow(10.0, exponent)
    );

    /*
      Keep the mantissa normalized if floating-point rounding
      produces a value at the edge of the next decade.
    */
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

    Serial.print(
        mantissa,
        decimalPlaces
    );

    Serial.print("e");

    if (exponent >= 0)
    {
        Serial.print("+");
    }
    else
    {
        Serial.print("-");
    }

    int absoluteExponent = abs(exponent);

    if (absoluteExponent < 10)
    {
        Serial.print("0");
    }

    Serial.println(absoluteExponent);
}
