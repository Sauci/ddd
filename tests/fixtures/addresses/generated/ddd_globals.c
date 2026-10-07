/*
 * ddd_globals.c
 *
 * Global variable data dictionary of project 'AddressFixture'.
 * Generated from 'project.ddd.json' by ddd 0.11.0.
 *
 * DO NOT EDIT - every change is lost the next time DDD runs.
 */
#include "ddd_globals.h"

/*
 * Definition of every global variable of the project.  Compile and link this
 * file exactly once; DDD is the only owner of these storage locations.
 */

/* ---------------------------------------------------------------------------
 * Engine - Owns one variable of every shape the address fixtures place
 * ------------------------------------------------------------------------ */

/* measurements */
/** An array of structures in one dimension */
Cell_t Cells[3];
/** Energy spent since the last reset [J] */
double Energy;
/** Engaged gear, negative in reverse */
int8_t Gear;
/** An array of structures in two dimensions */
Cell_t Grid[2][3];
/** The inlet sensor: a structure nesting another, with arrays inside */
volatile Sensor_t Inlet;
/** Values inside a bitfield's unit, and an eight byte unit */
Mixed_t Mixed;
/** Gear ratio */
float Ratio;
/** The last eight raw samples, an array of values */
uint8_t Samples[8];
/** Shaft speed [rpm] */
volatile uint16_t Speed;
/** Bitfields of one, two and four bytes between values */
volatile Status_t Status;
/** Timer ticks since the last reset */
volatile uint64_t Ticks;
/** Shaft torque, initialised so that it lands in .data [Nm] */
int32_t Torque = 7;

/* calibration data */
/** Whether the engine may start (calibration parameter) */
const bool Enabled = 1;
/** Speed loop gain (calibration parameter) */
const volatile float Gain = 1.5F;
/** Torque limit [Nm] (calibration parameter) */
const int16_t Limit = -100;
/** Four calibratable thresholds (calibration value block) */
const uint16_t Table[4] = { 1U, 2U, 3U, 4U };
/** The calibration of the speed loop, bitfields among its values */
const volatile Tuning_t Tuning;
