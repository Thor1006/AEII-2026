# Plan B correction: DCA1000 removed entirely

**Status:** done
**Date:** 2026-10-18

The user clarified that DCA1000 is not part of Plan B now or as a future upgrade. Updated the active procurement plan, implementation boundary, project context, project summary, decision record and hardware handoff to reflect this. Earlier deferred-DCA suggestions are superseded.

The active radar path is AWR2944PEVM onboard processing -> Ethernet -> notebook, with Raspberry Pi retained as the later prototype target. Custom Range-Doppler/complex-phase outputs require implementation and testing. Full DCA-equivalent raw ADC capture is not promised.

Remove DCA1000EVM, its 5-V supply and Samtec/LVDS capture cable from the graphic and purchase list. Keep the other hardware groups: radar/development, Raspberry Pi, MyoWare, IMU, and experiment/demo equipment.

The submitted poster and proposal remain untouched. No commit or push was requested or performed.
