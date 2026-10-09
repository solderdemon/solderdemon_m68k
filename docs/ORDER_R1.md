# SolderDemon m68k r1 — first PCB order

Order **five bare boards**; assemble and test one before populating the rest.

| Order field | r1 design value |
| --- | --- |
| Fabrication upload | [`solderdemon_m68k-r1-factory.zip`](../design/CAMOutputs/solderdemon_m68k-r1-factory.zip) |
| Finished outline | 165 × 100 mm |
| Layers | 4: Top, Route2, Route15, Bottom |
| Material and thickness | FR-4, 1.6 mm |
| Copper in KiCad stackup | 0.035 mm on each layer (1 oz nominal) |
| Solder mask / silkscreen files | Both sides included |
| Drill files | Separate PTH and NPTH Excellon files; NPTH contains no holes |

The KiCad stackup leaves the copper surface finish as `None`; choose the finish in the
manufacturer's order form. Solder-mask colour and legend colour are also order-form choices;
the project renders show green mask with white legend. Check the rendered preview for all four
copper layers, outline, masks, both legends and plated holes before submitting the order.

The [ERC report](../design/CAMOutputs/solderdemon_m68k-r1-erc.rpt) has zero errors. The
[DRC report](../design/CAMOutputs/solderdemon_m68k-r1-drc.rpt) has zero errors and zero
unconnected pads; its warnings are library footprint and schematic field differences. The
[drill report](../design/CAMOutputs/solderdemon_m68k-r1-drill-report.txt) lists 1,122 plated
holes. The factory ZIP was regenerated from the current r1 board after route optimization.

For the first assembly, use the [current BOM](../design/CAMOutputs/solderdemon_m68k-r1-bom.csv)
and [schematic PDF](../design/CAMOutputs/solderdemon_m68k-r1-schematic.pdf). Verify the actual
PLCC-44 socket bodies and key orientation for IC2, IC3 and IC4, and the J9 JTAG connector
orientation before soldering. The BOM is a design list, not a supplier-verified shopping list.

If the PCB changes, regenerate all files with KiCad 10 Python:

```sh
"/c/Program Files/KiCad/10.0/bin/python.exe" design/tools/export_r1.py
```
