"""Round insulated-wire envelopes with true circular bends and declared nets."""
import math
import cadquery as cq


def V(p):return cq.Vector(*p)


def route(points,radius):
    # radius: one bend radius, or one per interior point.
    pts=[V(p) for p in points]
    radii=list(radius) if isinstance(radius,(list,tuple)) else [radius]*len(pts)
    corners={}
    for i in range(1,len(pts)-1):
        u=(pts[i]-pts[i-1]).normalized();v=(pts[i+1]-pts[i]).normalized()
        a=math.acos(max(-1,min(1,u.dot(v))))
        if a<1e-5:continue
        assert a<math.pi-1e-4,'Use two bends for a reversal.'
        corners[i]=dict(u=u,v=v,angle=a,d=radii[i-1]*math.tan(a/2))
    # Share each straight segment between its adjacent tangent setbacks.
    for _ in range(3):
        for i in range(len(pts)-1):
            left=corners.get(i);right=corners.get(i+1)
            dl=left['d'] if left else 0;dr=right['d'] if right else 0
            budget=(pts[i+1]-pts[i]).Length*.98
            if dl+dr>budget:
                factor=budget/(dl+dr)
                if left:left['d']*=factor
                if right:right['d']*=factor
    segments=[];current=pts[0]
    for i in range(1,len(pts)-1):
        if i not in corners:continue
        c=corners[i];u,v,a,d=c['u'],c['v'],c['angle'],c['d']
        r=d/math.tan(a/2);a0=pts[i]-u*d;a1=pts[i]+v*d
        n=(v-u*math.cos(a)).normalized();center=a0+n*r
        mid=center+((a0-center).normalized()+(a1-center).normalized()).normalized()*r
        if (a0-current).Length>1e-7:segments.append(('line',current,a0))
        segments.append(('arc',a0,mid,a1,center,r))
        current=a1
    if (pts[-1]-current).Length>1e-7:segments.append(('line',current,pts[-1]))
    return segments


def tangent(s,at_end=False):
    if s[0]=='line':return (s[2]-s[1]).normalized()
    a,m,b,c,r=s[1:]
    normal=(m-a).cross(b-m).normalized()
    radial=(b-c if at_end else a-c).normalized()
    return normal.cross(radial).normalized()


def offset_yz_route(segments,dx,dz):
    # Center route lies in the YZ plane; X is a fixed cross-section axis.
    u=cq.Vector(1,0,0);out=[]
    for s in segments:
        t0=tangent(s);t1=tangent(s,True);v0=t0.cross(u);v1=t1.cross(u)
        if s[0]=='line':
            out.append(('line',s[1]+u*dx+v0*dz,s[2]+u*dx+v1*dz))
        else:
            a,m,b,c,r=s[1:];sgn=v0.dot((a-c).normalized());newr=r+sgn*dz;cc=c+u*dx
            out.append(('arc',cc+(a-c).normalized()*newr,cc+(m-c).normalized()*newr,
                        cc+(b-c).normalized()*newr,cc,newr))
    return out


def path_wire(segments):
    edges=[]
    for s in segments:
        if s[0]=='line':edges.append(cq.Edge.makeLine(s[1],s[2]))
        else:edges.append(cq.Edge.makeThreePointArc(s[1],s[2],s[3]))
    return cq.Wire.assembleEdges(edges)


def sweep(segments,diameter):
    path=path_wire(segments);plane=cq.Plane(origin=segments[0][1],normal=tangent(segments[0]))
    return cq.Workplane(plane).circle(diameter/2).sweep(cq.Workplane(obj=path),isFrenet=False,transition='round')


def length(segments):return path_wire(segments).Length()


def min_radius(segments):return min((s[5] for s in segments if s[0]=='arc'),default=None)


def seg_length(s):
    if s[0]=='line':return (s[2]-s[1]).Length
    a,m,b,c,r=s[1:]
    return r*math.acos(max(-1,min(1,(a-c).normalized().dot((b-c).normalized()))))


def sample(segments,n):
    """n points evenly spaced along the route, both ends included (for the viewer's animated wires)."""
    lens=[seg_length(s) for s in segments];total=sum(lens);out=[]
    for k in range(n):
        u=total*k/(n-1);i=0
        while i<len(segments)-1 and u>lens[i]:u-=lens[i];i+=1
        s=segments[i];f=min(max(u/lens[i],0.0),1.0) if lens[i]>0 else 0.0
        if s[0]=='line':p=s[1]+(s[2]-s[1])*f
        else:
            a,m,b,c,r=s[1:];e1=(a-c).normalized();e2=(a-c).cross(b-c).normalized().cross(e1)
            phi=lens[i]/r*f;p=c+e1*(r*math.cos(phi))+e2*(r*math.sin(phi))
        out.append((round(p.x,3),round(p.y,3),round(p.z,3)))
    return out
