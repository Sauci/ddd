/* consumer.c - a unit that reads the project's variables through Engine.h, as a software
 * component does; written by hand for docker/build_address_fixtures.py, which links it into the
 * images of the variants that differ in that header. It reads each variable it lists, which is
 * what makes its compiler state the declaration in its debug information. Whole numbers and
 * addresses only: the images are linked without a runtime library.
 */
#include "Engine.h"

__attribute__((used)) unsigned long consumer_poll(void)
{
    unsigned long sum = Speed;

    sum += (unsigned long)&Gain;
    sum += (unsigned long)Limit;
    sum += Table[1];
    sum += Inlet.state;
    sum += Enabled ? 1U : 0U;
    sum += (unsigned long)&Tuning;
    return sum;
}
