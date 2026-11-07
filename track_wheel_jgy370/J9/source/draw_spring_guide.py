"""Dimensioned axial sections of the spring pocket, using the CAD parameters."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from shapely.geometry import box
import j9_design as D

ROOT = Path(__file__).resolve().parent.parent
INK, FRAME, YOKE = '#19363e', '#a9c5c9', '#bd9dd3'


def patch(ax, shape, color):
    ax.add_patch(Polygon(np.asarray(shape.exterior.coords), closed=True, fc=color, ec=INK, lw=1))
    for ring in shape.interiors:
        ax.add_patch(Polygon(np.asarray(ring.coords), closed=True, fc='white', ec=INK, lw=1))


def draw(ax, recoil):
    p = D.SPRING_POCKET
    # Longitudinal section at Y=0; Z is measured from the spring axis.
    frame = box(17, D.WEB_Z[0]-D.AXLE_Z, D.WEB_X[1], D.WEB_Z[1]-D.AXLE_Z)
    frame = frame.union(box(*[D.SPRING_GUIDE_X[0], -p['outer_d']/2,
                             D.SPRING_GUIDE_X[1], p['outer_d']/2]))
    frame = frame.difference(box(D.SPRING_X0, -p['bore_d']/2, D.SPRING_GUIDE_X[1]+1, p['bore_d']/2))
    frame = frame.union(box(D.SPRING_X0-.01, -D.SPIGOT_R, D.SPRING_X0+D.SPIGOT_L, D.SPIGOT_R))
    patch(ax, frame, FRAME)
    x0, x1 = [x-recoil for x in D.YOKE_BASE_X]
    seat = x0-p['recess']
    yoke = box(x0, -7, x1, D.ARM_HALF_Z).union(box(seat, -p['piston_d']/2, x0+.01, p['piston_d']/2))
    yoke = yoke.union(box(seat-D.SPIGOT_L, -D.SPIGOT_R, seat+.01, D.SPIGOT_R))
    patch(ax, yoke, YOKE)
    # Two orange bands denote the entire spring wire envelope in section.
    for sign in (-1, 1):
        z0,z1=sorted([sign*D.SPRING['id']/2,sign*D.SPRING['od']/2])
        rect = box(D.SPRING_X0,z0,seat,z1)
        ax.add_patch(Polygon(np.asarray(rect.exterior.coords),closed=True,fc='#d98b49',ec='#945021',lw=.8))
    ax.plot([17,76],[0,0],':',color='#85979b',lw=.8)
    ax.annotate('',(D.SPRING_X0,-15),(seat,-15),arrowprops=dict(arrowstyle='<->',color=INK,lw=.8))
    ax.text((D.SPRING_X0+seat)/2,-14.4,f'Spring length {D.SPRING_SET-recoil:.1f} mm',ha='center',fontsize=9,color=INK)
    ax.set_title('Normal track tension' if recoil==0 else 'At the 4.2 mm recoil stop',loc='left',fontsize=12,weight='bold',color=INK)
    ax.set_xlim(16,78);ax.set_ylim(-19,20);ax.set_aspect('equal');ax.axis('off')
    ax.annotate('Main web + integral guide', (31,10.6), (18,17),fontsize=9,color=INK,
                arrowprops=dict(arrowstyle='-',lw=.7,color=INK))
    ax.annotate('Yoke piston', (x0-3,7.8), (59,17),fontsize=9,color=INK,
                arrowprops=dict(arrowstyle='-',lw=.7,color=INK))
    if recoil:
        ax.annotate('0.8 mm mouth clearance', (D.SPRING_GUIDE_X[1]+.4,-9), (52,-18),fontsize=8,color=INK,
                    arrowprops=dict(arrowstyle='-',lw=.7,color=INK))


def main():
    fig,axes=plt.subplots(1,2,figsize=(13,5.3))
    fig.subplots_adjust(left=.03,right=.99,top=.80,bottom=.23,wspace=.10)
    fig.suptitle('J9 spring guide — recessed into the main beam',x=.03,ha='left',fontsize=18,weight='bold',color=INK)
    fig.text(.03,.89,'Axial sections at Y = 0. Orange bands show the spring envelope; dimensions in mm.',fontsize=10,color=INK)
    draw(axes[0],0);draw(axes[1],D.RECOIL)
    fig.text(.03,.15,'Guide bore Ø16.4  ·  outside Ø21.2  ·  wall 2.4  ·  piston Ø15.6 × 8  ·  spring Ø15.24',fontsize=11,color=INK)
    fig.text(.03,.10,'Spring radial clearance 0.58  ·  piston radial clearance 0.40  ·  fixed seat recessed 8  ·  spring preload remains 77 N',fontsize=10,color=INK)
    fig.text(.03,.045,'Use revised J901 + J908 together. Nominal CAD dimensions; print fit, debris tolerance and durability still need prototype checks.',fontsize=9,color='#50616a')
    (ROOT/'images').mkdir(exist_ok=True)
    fig.savefig(ROOT/'J9_spring_guide_detail.pdf')
    fig.savefig(ROOT/'images/J9_spring_guide_detail.png',dpi=170)
    plt.close(fig)


if __name__=='__main__':main()
