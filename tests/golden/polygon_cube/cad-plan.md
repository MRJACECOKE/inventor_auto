# CAD Feature Plan — polygon_cube

- plan_version: 1.0
- units: mm
- measurement file: `tests/fixtures/parts/polygon_cube/measurement-input.json`
- measurement sha256: `e3ab1f424e761d7da75fdda305312d5e643349356519dd70bbf0c88d76908103`
- source images: IMG-001

## Feature order

1. F001 — base_extrude · sketch S1 · distance=p_cube_edge · dir=symmetric
2. F002 — extrude_cut · sketch S2 · distance=p_pocket_depth · dir=negative · after F001
3. F003 — extrude_cut · sketch S3 · distance=p_pocket_depth · dir=positive · after F001
4. F004 — extrude_cut · sketch S4 · distance=p_pocket_depth · dir=negative · after F001
5. F005 — extrude_cut · sketch S5 · distance=p_pocket_depth · dir=positive · after F001
6. F006 — extrude_cut · sketch S6 · distance=p_pocket_depth · dir=negative · after F001
7. F007 — extrude_cut · sketch S7 · distance=p_pocket_depth · dir=positive · after F001

## Parameter map

| parameter | source | value | unit |
|---|---|---|---|
| p_cube_edge | M001 | 100 | mm |
| p_half_edge | derived: M001 / 2 | 50 | mm |
| p_hept_dia | M007 | 36 | mm |
| p_hex_dia | M006 | 36 | mm |
| p_oct_dia | M008 | 36 | mm |
| p_pent_dia | M005 | 36 | mm |
| p_pocket_depth | M002 | 30 | mm |
| p_sq_dia | M004 | 36 | mm |
| p_tri_dia | M003 | 36 | mm |

## Sketches

- S1 on XY: {"corner": "center", "height_param": "cube_edge", "type": "rectangle", "width_param": "cube_edge"}
- S2 on YZ offset +p_half_edge: {"circumdiameter_param": "tri_dia", "sides": 3, "type": "polygon"}
- S3 on YZ offset -p_half_edge: {"circumdiameter_param": "sq_dia", "sides": 4, "type": "polygon"}
- S4 on XZ offset +p_half_edge: {"circumdiameter_param": "pent_dia", "sides": 5, "type": "polygon"}
- S5 on XZ offset -p_half_edge: {"circumdiameter_param": "hex_dia", "sides": 6, "type": "polygon"}
- S6 on XY offset +p_half_edge: {"circumdiameter_param": "hept_dia", "sides": 7, "type": "polygon"}
- S7 on XY offset -p_half_edge: {"circumdiameter_param": "oct_dia", "sides": 8, "type": "polygon"}
