# User config
set ::env(DESIGN_NAME) multi_project_harness

set ::env(FP_CORE_UTIL) 15

set ::env(FP_PDN_VOFFSET) 0
set ::env(FP_PDN_VPITCH) 30

# doesn't work
#set ::env(VERILOG_FILES_BLACKBOX) "seven_segment_seconds ws2812 vga_clockv"

set ::env(MACRO_PLACEMENT_CFG) $::env(OPENLANE_ROOT)/designs/$::env(DESIGN_NAME)/macro_placement.cfg


set ::env(PL_TARGET_DENSITY) 0.35
set ::env(PL_BASIC_PLACEMENT) 1
set ::env(CELL_PAD) 0

set ::env(CLOCK_PERIOD) "100"
set ::env(CLOCK_PORT) "wb_clk_i"
set ::env(CLOCK_TREE_SYNTH) 0

set ::env(DIODE_INSERTION_STRATEGY) 0

# Change if needed
set ::env(VERILOG_FILES) [glob $::env(DESIGN_DIR)/src/*.v]
set ::env(EXTRA_LEFS) [glob $::env(DESIGN_DIR)/macros/lef/*.lef]
set ::env(EXTRA_GDS_FILES) [glob $::env(DESIGN_DIR)/macros/gds/*.gds]

set filename $::env(DESIGN_DIR)/$::env(PDK)_$::env(STD_CELL_LIBRARY)_config.tcl
if { [file exists $filename] == 1} {
	source $filename
}
