/*
 * driver_status.h - the vendor's own view of the sensor driver.
 *
 * This header stands in for one a driver vendor ships: DDD never reads it, generates no
 * typedef for DriverStatus_t, and knows neither its layout nor its meaning. The types file
 * declares the name as an external type, and the generated ddd_types.h includes this header
 * so that a structure with a DriverStatus_t member compiles.
 */
#ifndef DRIVER_STATUS_H
#define DRIVER_STATUS_H

typedef struct
{
    unsigned char state;    /* the driver's internal state machine */
    unsigned char lastFault; /* vendor specific fault code, 0 when sound */
} DriverStatus_t;

#endif /* DRIVER_STATUS_H */
