"""Design calculations for the X1 main board, from the part values in netlist.py.

Datasheet constants are quoted with their source (the extracted datasheet text, section or table).
check_design.py turns these into pass/fail checks; build_schematic.py prints some on the sheets.
"""
import netlist as NL

# --- datasheet constants -----------------------------------------------------------------------
DRV = dict(  # TI DRV8876, SLVSDS7B, 6.3 and 6.5 (Electrical Characteristics)
    vm_min=4.5, vm_max=37.0, vm_abs=40.0, a_ipropi=1000e-6, vref_max=3.6, i_ipropi_max=3e-3,
    aerr_low_A=7.5e-3, aerr_mid=0.05, aerr_high=0.04, t_off=25e-6, i_ocp_min=3.5, rds_hs=0.35, rds_ls=0.35,
    vih_min=1.5, logic_abs=5.75, f_pwm_max=100e3, t_wake=1e-3, r_theta_ja=35.0,  # 8.2.1.1 example board
    uvlo_rise_max=4.6)
BUCK = dict(  # TI TPS54302, SLVSDG6C, 5.3 / 5.5 / 7.2
    vin_min=4.5, vin_max=28.0, vref=0.596, vref_tol=0.025, f_sw=400e3, ilim_hs_min=4.0, ilim_hs_max=6.0,
    en_rise=1.28, en_fall=1.16, i_p=0.7e-6, i_h=1.55e-6, fo_max=40e3)
LDO = dict(vin_max=6.0, i_max=0.6, dropout_max=0.4, theta_ja=184.0)   # Diodes AP2112, DS39724
ESP = dict(vdd_min=3.0, vdd_max=3.6, i_supply_min=0.5, adc_max_12db=2.9)  # WROOM-1 v1.8 6.2; S3 v2.2 5-5
TVS_CLAMP = NL.VBAT_TRANSIENT
INDUCTOR = dict(L=10e-6, isat=7.6, irms=5.0, dcr=0.0266)   # Bourns SRP6060FA-100M (LCSC C2046759 listing)
SCHOTTKY_VF = 0.45            # B5819W at ~0.3 A, read from the datasheet curve (no table value)

VBAT = dict(min=9.0, nom=11.1, max=12.6, warn=10.5, stop=9.6)   # SPEC.md P2, S5


def value(ref):
    return NL.kind_info(NETLIST.parts[ref]["kind"])["ohms"]


NETLIST = NL.build()


def vref():
    r_top, r_bot = value("R151"), value("R152")
    return 3.3 * r_bot / (r_top + r_bot)


def itrip(ch):
    return vref() / (ch["r_ipropi"] * DRV["a_ipropi"])


def buck_vout(base):
    return BUCK["vref"] * (1 + value(f"R{base + 1}") / value(f"R{base + 2}"))


def buck_uvlo(base):
    """EN divider: start and stop input voltage (TPS54302 6.3.6, Equations 1-2 in forward form)."""
    r4, r5 = value(f"R{base + 3}"), value(f"R{base + 4}")
    start = BUCK["en_rise"] * (1 + r4 / r5) - BUCK["i_p"] * r4
    stop = BUCK["en_fall"] * (1 + r4 / r5) - (BUCK["i_p"] + BUCK["i_h"]) * r4
    return start, stop


def buck_ripple(vout, vin=VBAT["max"]):
    """Inductor ripple current (TPS54302 7.2.3.5.1, Equation 8 rearranged)."""
    return vout * (vin - vout) / (vin * INDUCTOR["L"] * BUCK["f_sw"])


def divider(r_top, r_bot):
    return value(r_bot) / (value(r_top) + value(r_bot))


def ldo_input(vbuck=None):
    v5 = vbuck if vbuck is not None else buck_vout(120)
    return v5 - SCHOTTKY_VF


def channel(key):
    return next(c for c in NL.CHANNELS if c["key"] == key)


BUDGET = dict(  # same assumptions as the spec budget (../source/draw_control_spec.py), board values for limits
    eff=0.90, act_stall=0.46, esp_peak=0.35, lamp=0.10, buzzer=0.10, expansion=2.0, fuse=5.0)


def power_budget():
    """Battery current, worst case (SPEC P4): tracks and swing at their regulation limits, actuators
    stalled at their own stall current (below the 0.5 A board limit), radio peak, both lamps, buzzer;
    bucks 90 % efficient; battery at the 9.6 V stop voltage."""
    b, v = BUDGET, VBAT["stop"]
    i_vbat = sum(itrip(c) for c in NL.CHANNELS if c["vm"] == "VBAT")
    p6 = 4 * b["act_stall"] * buck_vout(110)
    i5 = b["esp_peak"] + 2 * b["lamp"] + b["buzzer"]          # 3.3 V comes from 5 V through the LDO
    p5 = i5 * buck_vout(120)
    i_total = i_vbat + (p6 + p5) / b["eff"] / v
    i_exp = b["expansion"] * buck_vout(120) / b["eff"] / v
    return dict(tracks_swing_A=i_vbat, rail6_W=p6, rail5_A=i5, rail5_with_expansion_A=i5 + b["expansion"],
                rail6_limit_A=sum(itrip(c) for c in NL.CHANNELS if c["vm"] == "+6V"),
                total_A=i_total, with_expansion_A=i_total + i_exp, fuse_A=b["fuse"])


if __name__ == "__main__":
    print(f"VREF {vref():.3f} V")
    for c in NL.CHANNELS:
        print(f"{c['key']}: ITRIP {itrip(c):.3f} A")
    for b in (110, 120):
        print(f"buck {b}: Vout {buck_vout(b):.3f} V, UVLO {buck_uvlo(b)}, ripple {buck_ripple(buck_vout(b)):.3f} A")
    print(power_budget())
