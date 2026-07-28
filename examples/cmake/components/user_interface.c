#include "UserInterface.h"

void user_interface_step(void);

void user_interface_step(void)
{
    ValueI = (ValueE > 1000U) ? 1U : 0U;
    ValueI += BlockA[0] + CurveB[0] + (uint32_t)ValueJ;
}
