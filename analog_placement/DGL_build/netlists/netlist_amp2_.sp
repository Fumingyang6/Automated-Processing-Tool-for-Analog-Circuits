
************************************************************************
* auCdl Netlist:
* 
* Library Name:  AMP_18
* Top Cell Name: amp2
* View Name:     schematic
* Netlisted on:  Apr  4 16:37:57 2023
************************************************************************

*.BIPOLAR
*.RESI = 2000 
*.RESVAL
*.CAPVAL
*.DIOPERI
*.DIOAREA
*.EQUATION
*.SCALE METER
*.MEGA
.PARAM



************************************************************************
* Library Name: AMP_18
* Cell Name:    amp2
* View Name:    schematic
************************************************************************

.SUBCKT amp2 GND VDD VINN VINP out1 out2 vin1
*.PININFO GND:B VDD:B VINN:B VINP:B out1:B out2:B vin1:B
XC0 out2 GND mim2_ckt m=1 l=25u w=25u
XC1 out1 GND mim2_ckt m=1 l=25u w=25u
MM3 out2 VINP net37 GND n50 W=10u L=1.4u M=4
MM2 out1 VINN net37 GND n50 W=10u L=1.4u M=4
MM5 net37 out2 GND GND n50 W=3u L=1.4u M=6
MM4 net37 out1 GND GND n50 W=3u L=1.4u M=6
MM1 out2 vin1 VDD VDD p50 W=20u L=1u M=2
MM0 out1 vin1 VDD VDD p50 W=20u L=1u M=2
.ENDS

