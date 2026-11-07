"""Electrical design checks for the X1 main board, against the datasheet limits in calcs.py.

Writes X1_main_board_A_design_checks.json (all_pass and every value with its limit).

    python check_design.py
"""
import json
import math
import sys
from pathlib import Path

import calcs as CA
import netlist as NL

BOARD = Path(__file__).resolve().parent.parent
STEM = f"X1_main_board_{NL.REV}"
PWM_HZ = 20e3                     # SPEC.md M3 / section 2
ESP_AVG_A = 0.15                  # ESP32-S3 with ESP-NOW at 50 Hz: average module current (assumed, bench item)
HEIGHT_LIMIT = 20.0               # SPEC.md B2


def main():
    checks = []

    def check(name, value, limit, ok, unit="", note=""):
        checks.append(dict(name=name, value=round(value, 4) if isinstance(value, float) else value, limit=limit,
                           unit=unit, ok=bool(ok), note=note))

    drv, buck, ldo, esp = CA.DRV, CA.BUCK, CA.LDO, CA.ESP
    vref = CA.vref()
    check("VREF within the DRV8876 range", vref, f"<= {drv['vref_max']}", vref <= drv["vref_max"], "V")
    for ch in NL.CHANNELS:
        it = CA.itrip(ch)
        tgt = NL.LIMIT_TARGET_A[ch["key"]]
        check(f"{ch['name']}: ITRIP close to the spec limit {tgt} A", it, f"{tgt} A +/- 5 %",
              abs(it / tgt - 1) <= 0.05, "A")
        check(f"{ch['name']}: IPROPI current at ITRIP", it * drv["a_ipropi"] * 1e3,
              f"<= {drv['i_ipropi_max'] * 1e3} mA", it * drv["a_ipropi"] <= drv["i_ipropi_max"], "mA")
    check("IPROPI voltage at ITRIP (= VREF) inside the ADC1 range at 12 dB", vref, f"<= {esp['adc_max_12db']}",
          vref <= esp["adc_max_12db"], "V")
    run = 0.12 * CA.channel("BL")["r_ipropi"] * drv["a_ipropi"]
    check("Actuator running current (0.12 A) reads above the ADC floor", run, ">= 0.3 V", run >= 0.3, "V",
          "about 0.6 V; the IPROPI offset error below 0.15 A is +/-7.5 mA (6 % of 0.12 A)")
    check("VBAT channels: battery and transient inside VM", CA.TVS_CLAMP, f"<= {drv['vm_max']} (abs {drv['vm_abs']})",
          CA.TVS_CLAMP <= drv["vm_max"], "V")
    check("6 V channels: VM above the driver UVLO", CA.buck_vout(110), f">= {drv['uvlo_rise_max']}",
          CA.buck_vout(110) >= drv["uvlo_rise_max"], "V")
    check("PWM frequency", PWM_HZ / 1e3, f"<= {drv['f_pwm_max'] / 1e3}", PWM_HZ <= drv["f_pwm_max"], "kHz")
    check("ESP32 3.3 V logic high above the DRV8876 VIH", 3.3 * 0.8, f">= {drv['vih_min']}",
          3.3 * 0.8 >= drv["vih_min"], "V", "ESP32-S3 VOH min 0.8 x VDD")
    check("nFAULT pull-up current (shared open drain)", 3.3 / 10e3 * 1e3, "<= 5 mA", 3.3 / 10e3 <= 5e-3, "mA")
    # driver dissipation, worst channel (tracks at the limit, continuous)
    it = CA.itrip(CA.channel("TL"))
    p = it ** 2 * (drv["rds_hs"] + drv["rds_ls"]) * 1.25 + 12.6 * it * 300e-9 * PWM_HZ + 12.6 * 3e-3
    tj = 60 + p * drv["r_theta_ja"]
    check("Track driver junction at the 1 A limit, 60 C inside the body", tj, "< 150 (TSD 160)", tj < 150, "C",
          f"{p:.2f} W, R_theta_JA {drv['r_theta_ja']} C/W as in the datasheet example (4-layer board, pad vias)")

    for base, name in ((110, "6 V"), (120, "5 V")):
        vo = CA.buck_vout(base)
        start, stop = CA.buck_uvlo(base)
        check(f"{name} buck output", vo, "6.0 / 5.0 +/- 3 %", abs(vo / (6.0 if base == 110 else 5.0) - 1) <= 0.03, "V")
        check(f"{name} buck input max (TVS clamp) inside VIN", CA.TVS_CLAMP, f"<= {buck['vin_max']}",
              CA.TVS_CLAMP <= buck["vin_max"], "V")
        check(f"{name} buck starts below the lowest battery voltage", start, f"< {CA.VBAT['min']}",
              start < CA.VBAT["min"], "V", f"stops at {stop:.2f} V; hysteresis {start - stop:.2f} V (TI: > 0.5 V)")
        rip = CA.buck_ripple(vo)
        pk = 3.0 + rip / 2
        check(f"{name} buck: inductor peak at 3 A below the minimum current limit", pk, f"< {buck['ilim_hs_min']}",
              pk < buck["ilim_hs_min"], "A", f"ripple {rip:.2f} A at 12.6 V")
        check(f"{name} buck: inductor saturation above the maximum current limit", CA.INDUCTOR["isat"],
              f">= {buck['ilim_hs_max']}", CA.INDUCTOR["isat"] >= buck["ilim_hs_max"], "A", "Bourns SRP6060FA-100M")
        # TI Eq. 14: fo [MHz] = 5.1 / (Vout x Co [uF]); the worst case is the DC-bias-derated capacitance
        fo_der = 5.1e6 / (vo * 2 * 22 * 0.6)
        check(f"{name} buck: crossover (TI Eq. 14, 2 x 22 uF derated to 60 %)", fo_der / 1e3, "< 40 kHz",
              fo_der < buck["fo_max"], "kHz")
        fo_nom = 5.1e6 / (vo * 2 * 22)          # TI sizes C6 on the nominal capacitance (5 V -> 75 pF)
        cff = 1 / (2 * math.pi * fo_nom * 100e3) * 1e12
        check(f"{name} buck: feed-forward capacitor (TI Eq. 16) vs the 68 pF fitted", cff, "68 pF within 35 %",
              abs(68 / cff - 1) <= 0.35, "pF", f"crossover {fo_nom / 1e3:.1f} kHz with the nominal 44 uF")
    bud = CA.power_budget()
    check("6 V rail load: four actuators at the board limit", bud["rail6_limit_A"], "<= 3 A", bud["rail6_limit_A"] <= 3.0, "A")
    check("5 V rail load with the 2 A expansion reserve", bud["rail5_with_expansion_A"], "<= 3 A",
          bud["rail5_with_expansion_A"] <= 3.0, "A")
    vin = CA.ldo_input()
    check("LDO headroom from the 5 V buck (after the Schottky)", vin - 3.3, f">= {ldo['dropout_max']} at 600 mA",
          vin - 3.3 >= ldo["dropout_max"], "V")
    vin_usb = 4.75 - CA.SCHOTTKY_VF
    check("LDO headroom from USB VBUS (4.75 V minimum)", vin_usb - 3.3, f">= {ldo['dropout_max']}",
          vin_usb - 3.3 >= ldo["dropout_max"], "V")
    check("LDO rated current covers the module requirement", ldo["i_max"], f">= {esp['i_supply_min']}",
          ldo["i_max"] >= esp["i_supply_min"], "A", "WROOM-1 datasheet 6.2: supply must deliver at least 0.5 A")
    rise = (5.25 - 0.3 - 3.3) * ESP_AVG_A * ldo["theta_ja"]
    check("LDO temperature rise at the average radio load", rise, "< 60", rise < 60, "C",
          f"{ESP_AVG_A} A average assumed; 0.35 A bursts are short. Bench item.")
    k = CA.divider("R102", "R103")
    check("Battery sense at 12.6 V inside the ADC range", 12.6 * k, f"<= {esp['adc_max_12db']}",
          12.6 * k <= esp["adc_max_12db"], "V")
    check("Battery sense resolution at the 9.6 V stop", 9.6 * k / 4095 * 1 / k * 1000, "<= 10 mV/LSB",
          2.9 / 4095 / k * 1000 <= 10, "mV")
    check("6 V sense inside the ADC range", CA.buck_vout(110) * CA.divider("R131", "R132"), "<= 2.9",
          CA.buck_vout(110) * CA.divider("R131", "R132") <= 2.9, "V")
    check("Worst-case battery current under the 5 A fuse (SPEC P4)", bud["total_A"], "< 5", bud["total_A"] < 5, "A",
          f"with a 2 A expansion load: {bud['with_expansion_A']:.2f} A (fuse reviewed in the 4G phase)")
    rds, vgs = 0.013, 9.0
    p_q = bud["total_A"] ** 2 * rds
    check("Reverse-protection FET loss at the worst-case current", p_q, "< 0.5 W (SO-8)", p_q < 0.5, "W",
          f"AO4407A RDS(on) {rds * 1e3:.0f} mOhm max at VGS -10 V; gate at -{vgs} V or more above 9 V")
    check("FET gate clamp below VGS max", 12.7, "<= 25 V", 12.7 <= 25, "V", "BZT52C12 at 12.7 V max")
    check("TVS stand-off above the full battery", 15.0, f">= {CA.VBAT['max']}", 15.0 >= CA.VBAT["max"], "V")
    check("Lamp PTC hold current covers both lamps", 0.5, ">= 0.2 A", 0.5 >= 0.2, "A")
    check("Expansion PTC hold current covers the 2 A reserve", 2.0, ">= 2.0 A at 25 C", True, "A",
          "hold current falls with temperature; review with the real 4G stick")
    nl = NL.build()
    tall = max((nl.info(r)["height"], r) for r in nl.parts)
    check("Tallest part (plugs mate sideways)", tall[0], f"<= {HEIGHT_LIMIT}", tall[0] <= HEIGHT_LIMIT, "mm", tall[1])
    for name, ok, detail in NL.rules(nl):
        checks.append(dict(name=name, value=str(detail), limit="", unit="", ok=bool(ok), note="netlist rule"))

    report = dict(board=f"{NL.TITLE} rev {NL.REV}", all_pass=all(c["ok"] for c in checks), budget=bud,
                  vref_V=round(vref, 4), itrip_A={c["key"]: round(CA.itrip(c), 4) for c in NL.CHANNELS},
                  checks=checks)
    (BOARD / f"{STEM}_design_checks.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    for c in checks:
        print(("PASS " if c["ok"] else "FAIL ") + f"{c['name']}: {c['value']} {c['unit']} ({c['limit']})")
    print("all_pass", report["all_pass"])
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
