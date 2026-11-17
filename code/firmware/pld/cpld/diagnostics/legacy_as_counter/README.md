# Legacy AS-counter CPLD firmware

Archived before promoting the address-based ROM handoff on 2026-11-17.
IC2 removes the reset-vector ROM after four AS rising edges. The assembled
board showed intermittent cold-start and reset failures with this image.
Retained for rollback and reproducing the diagnostic comparison, not the
recommended production firmware. IC3 is the unchanged production glue image.
