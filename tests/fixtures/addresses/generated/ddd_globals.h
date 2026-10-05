/*
 * ddd_globals.h
 *
 * Global variable data dictionary of project 'AddressFixture'.
 * Generated from 'project.ddd.json' by ddd 0.11.0.
 *
 * DO NOT EDIT - every change is lost the next time DDD runs.
 */
#ifndef DDD_GLOBALS_H
#define DDD_GLOBALS_H

#include "ddd_types.h"

/*
 * Declarations of every global variable of the project.  Software components
 * shall include their own interface header instead of this file; it exists so
 * that ddd_globals.c can be compiled with full prototype checking.
 */

/* ---------------------------------------------------------------------------
 * Engine - Owns one variable of every shape the address fixtures place
 * ------------------------------------------------------------------------ */
/** An array of structures in one dimension */
extern Cell_t Cells[3];
/** Energy spent since the last reset [J] */
extern double Energy;
/** Engaged gear, negative in reverse */
extern int8_t Gear;
/** An array of structures in two dimensions */
extern Cell_t Grid[2][3];
/** The inlet sensor: a structure nesting another, with arrays inside */
extern volatile Sensor_t Inlet;
/** Values inside a bitfield's unit, and an eight byte unit */
extern Mixed_t Mixed;
/** Gear ratio */
extern float Ratio;
/** The last eight raw samples, an array of values */
extern uint8_t Samples[8];
/** Shaft speed [rpm] */
extern volatile uint16_t Speed;
/** Bitfields of one, two and four bytes between values */
extern volatile Status_t Status;
/** Timer ticks since the last reset */
extern volatile uint64_t Ticks;
/** Shaft torque, initialised so that it lands in .data [Nm] */
extern int32_t Torque;
/** Whether the engine may start (calibration parameter) */
extern const bool Enabled;
/** Speed loop gain (calibration parameter) */
extern const volatile float Gain;
/** Torque limit [Nm] (calibration parameter) */
extern const int16_t Limit;
/** Four calibratable thresholds (calibration value block) */
extern const uint16_t Table[4];
/** The calibration of the speed loop, bitfields among its values */
extern const volatile Tuning_t Tuning;

#endif /* DDD_GLOBALS_H */
