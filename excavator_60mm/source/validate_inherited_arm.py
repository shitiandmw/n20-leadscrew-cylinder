"""Rerun the original arm60 checks without changing its report or assets."""
from design import ROOT
import validate_arm

if __name__=='__main__':
    validate_arm.ROOT=ROOT/'simulation/inherited_arm'
    validate_arm.ROOT.mkdir(exist_ok=True)
    raise SystemExit(0 if validate_arm.check() else 1)
