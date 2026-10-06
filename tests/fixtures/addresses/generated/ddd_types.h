/*
 * ddd_types.h
 *
 * Global variable data dictionary of project 'AddressFixture'.
 * Generated from 'project.ddd.json' by ddd 0.11.0.
 *
 * DO NOT EDIT - every change is lost the next time DDD runs.
 */
#ifndef DDD_TYPES_H
#define DDD_TYPES_H

#include <stdint.h>
#include <stdbool.h>

/* Cell_t - One cell of a grid: two flags between two values */
typedef struct
{
    uint16_t raw; /**< The cell's raw reading */
    uint8_t valid : 1; /**< Set once the reading is trusted */
    int8_t bias : 3; /**< A signed correction, in counts */
    int16_t v; /**< The corrected reading, after the flags */
} Cell_t;

/* Mixed_t - Values inside a bitfield's unit, and bitfields of an eight byte unit */
typedef struct
{
    uint32_t flags : 3; /**< Three bits of a four byte unit */
    uint8_t after; /**< A byte right after the three bits, inside their unit */
    uint16_t next; /**< Two bytes after it, still inside the unit */
    uint64_t big : 40; /**< Forty bits, which would cross an eight byte unit after next */
    int64_t small : 7; /**< Seven signed bits after them */
    uint32_t last; /**< Four bytes after the eight byte bitfields */
} Mixed_t;

/* Sample_t - One reading and the instant it was taken */
typedef struct
{
    uint16_t value; /**< The reading itself */
    uint32_t timestamp; /**< Milliseconds since the last reset */
} Sample_t;

/* Sensor_t - A sensor: a nested structure, an array of values and an array of structures */
typedef struct
{
    Sample_t latest; /**< The most recent reading */
    uint16_t history[4]; /**< The last four readings, oldest first */
    Cell_t cells[2]; /**< The sensor's two cells */
    uint8_t state; /**< The sensor's state machine */
} Sensor_t;

/* Status_t - Bitfields in units of one, two and four bytes, each group followed by a value */
typedef struct
{
    uint8_t ready : 1; /**< Bit 0 of a byte */
    int8_t trim : 4; /**< Four signed bits after it */
    uint8_t mode : 5; /**< Five bits, which would cross the byte and so start the next one */
    uint8_t level; /**< A byte after the byte bitfields */
    uint16_t count : 9; /**< Nine bits, which would cross a two byte unit after level */
    int16_t delta : 7; /**< Seven signed bits after them */
    uint16_t word; /**< Two bytes after the two byte bitfields */
    uint32_t wide : 20; /**< Twenty bits of a four byte unit */
    int32_t drift : 12; /**< Twelve signed bits filling it */
    uint8_t tail; /**< A byte after the four byte bitfields */
} Status_t;

/* Tuning_t - What the calibration tool may change: values around two bitfields */
typedef struct
{
    float gain; /**< The loop gain */
    int16_t shift; /**< A signed offset, in counts */
    uint8_t enable : 1; /**< Whether the loop runs */
    uint8_t retries : 3; /**< How many times a failed step is tried again */
    uint16_t timeout; /**< Milliseconds before a step fails, after the bitfields */
} Tuning_t;

#endif /* DDD_TYPES_H */
