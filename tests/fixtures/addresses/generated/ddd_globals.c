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

/*
 * A link with --gc-sections drops a definition no code references, a
 * measurement only the calibration tool reads among them, and the a2l then
 * describes storage the image does not hold.  A project on ELF that links so
 * defines DDD_RETAIN as __attribute__((used, retain)), with -D or in a header
 * the build includes first, with a gcc that knows 'retain' and a binutils that
 * keeps such a section; where gcc ignores 'retain' (PE), a reference to the
 * object or a linker script that keeps its section does the same.  Left
 * undefined it is empty, and the definitions are what they were.
 */
#ifndef DDD_RETAIN
#define DDD_RETAIN
#endif

/* ---------------------------------------------------------------------------
 * Engine - Owns one variable of every shape the address fixtures place
 * ------------------------------------------------------------------------ */

/* measurements */
/** An array of structures in one dimension */
DDD_RETAIN Cell_t Cells[3];
/** Energy spent since the last reset [J] */
DDD_RETAIN double Energy;
/** Engaged gear, negative in reverse */
DDD_RETAIN int8_t Gear;
/** An array of structures in two dimensions */
DDD_RETAIN Cell_t Grid[2][3];
/** The inlet sensor: a structure nesting another, with arrays inside */
DDD_RETAIN volatile Sensor_t Inlet;
/** Values inside a bitfield's unit, and an eight byte unit */
DDD_RETAIN Mixed_t Mixed;
/** Gear ratio */
DDD_RETAIN float Ratio;
/** The last eight raw samples, an array of values */
DDD_RETAIN uint8_t Samples[8];
/** Shaft speed [rpm] */
DDD_RETAIN volatile uint16_t Speed;
/** Bitfields of one, two and four bytes between values */
DDD_RETAIN volatile Status_t Status;
/** Timer ticks since the last reset */
DDD_RETAIN volatile uint64_t Ticks;
/** Shaft torque, initialised so that it lands in .data [Nm] */
DDD_RETAIN int32_t Torque = 7;

/* calibration data */
/** Whether the engine may start (calibration parameter) */
DDD_RETAIN const bool Enabled = 1;
/** Speed loop gain (calibration parameter) */
DDD_RETAIN const volatile float Gain = 1.5F;
/** Torque limit [Nm] (calibration parameter) */
DDD_RETAIN const int16_t Limit = -100;
/** Four calibratable thresholds (calibration value block) */
DDD_RETAIN const uint16_t Table[4] = { 1U, 2U, 3U, 4U };
/** The calibration of the speed loop, bitfields among its values */
DDD_RETAIN const volatile Tuning_t Tuning;
