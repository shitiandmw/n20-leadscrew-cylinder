"""Retained JGY-370 motor envelope geometry, in millimetres."""
import tw_parts as old
DX,DZ=old.DX,old.DZ
FACE=-46.0
CAN_Y=FACE-13.2

def motor_shapes():
    gearbox=old.box(DX-14.5,DX+31.5,FACE-23,FACE,DZ-16,DZ+16)
    for x in [DX-9,DX+24]:
        for z in [DZ-9,DZ+9]:
            gearbox=gearbox.union(old.ycyl(3.5,FACE,FACE+2,x,z))
    gearbox=gearbox.union(old.ycyl(6.6,FACE,FACE+1.6,DX,DZ))
    can=old.xcyl(12,DX+31.5,DX+62.3,CAN_Y,DZ)
    shaft=old.ycyl(3,FACE+1.6,FACE+15.6,DX,DZ)
    shaft=shaft.cut(old.box(DX-4,DX+4,FACE+3.6,FACE+16,DZ+2.5,DZ+4))
    wire=old.box(DX+62.3,DX+72.3,CAN_Y-9,CAN_Y+9,DZ-11,DZ+11)
    return {'JGY_gearbox_envelope':gearbox,'JGY_can_envelope':can,
            'JGY_output_shaft':shaft,'reserved_terminal_and_wire_space':wire}
