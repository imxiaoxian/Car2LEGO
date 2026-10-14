"""Rasterize native coloured geometry with transparent layers and cast shadows."""

from pathlib import Path
import numpy as np
from numba import njit
from PIL import Image

from app.services.ldraw_service import LDrawService


@njit(cache=True)
def raster(points, depths, colors, opacity, width, height):
    pixels = np.empty((height, width, 3), dtype=np.float64)
    pixels[:, :, 0] = 245; pixels[:, :, 1] = 245; pixels[:, :, 2] = 247
    zbuffer = np.full((height, width), np.inf)
    for pass_index in range(2):
        for index in range(len(points)):
            alpha = opacity[index]
            if (pass_index == 0 and alpha < 1) or (pass_index == 1 and alpha == 1):
                continue
            a, b, c = points[index, 0], points[index, 1], points[index, 2]
            denominator = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(denominator)<1e-9:
                continue
            left=max(0,int(np.floor(min(a[0],b[0],c[0])))); right=min(width-1,int(np.ceil(max(a[0],b[0],c[0]))))
            top=max(0,int(np.floor(min(a[1],b[1],c[1])))); bottom=min(height-1,int(np.ceil(max(a[1],b[1],c[1]))))
            for y in range(top,bottom+1):
                for x in range(left,right+1):
                    w1=((b[1]-c[1])*(x+.5-c[0])+(c[0]-b[0])*(y+.5-c[1]))/denominator
                    w2=((c[1]-a[1])*(x+.5-c[0])+(a[0]-c[0])*(y+.5-c[1]))/denominator
                    w3=1-w1-w2
                    if w1<0 or w2<0 or w3<0:
                        continue
                    z=w1*depths[index,0]+w2*depths[index,1]+w3*depths[index,2]
                    if z>=zbuffer[y,x]-.00001:
                        continue
                    if alpha==1:
                        zbuffer[y,x]=z
                    for channel in range(3):
                        pixels[y,x,channel]=colors[index,channel]*alpha+pixels[y,x,channel]*(1-alpha)
    return pixels.astype(np.uint8)


def render_scene(scene, output: Path, view="front", size=(1200,750), ids=None, highlight=None):
    from .exports import colored_geometry
    triangles, colors, alpha = [], [], []
    for part in scene.parts:
        if ids is not None and part.id not in ids:
            continue
        matrix, position=np.array(part.transform.rotation).reshape(3,3),np.array(part.transform.position)
        for c, mesh in colored_geometry(part.part_num):
            c=part.color_id if c==16 else c
            world=mesh@matrix.T+position
            color=LDrawService.get_color_hex(c)
            if highlight and part.id in highlight:
                color="#f2b632"
            rgb=np.array([int(color[i:i+2],16) for i in (1,3,5)])
            triangles.append(world);colors.append(np.tile(rgb,(len(world),1)))
            alpha.append(np.full(len(world),.32 if 32<=c<=47 else 1.))
    if not triangles:
        return
    mesh,rgb,opacity=np.concatenate(triangles),np.concatenate(colors),np.concatenate(alpha)
    orientations={"front":([.85,0.,.53],[-.22,-.91,.36]),"rear":([-.85,0.,-.53],[.22,-.91,-.36]),
                  "left":([0.,0.,1.],[0.,-1.,0.]),"right":([0.,0.,-1.],[0.,-1.,0.]),
                  "top":([1.,0.,0.],[0.,0.,1.]),"bottom":([1.,0.,0.],[0.,0.,-1.])}
    # The rasterizer keeps the minimum depth, so depth must increase away from
    # the camera. right x up points away from the viewer for front, rear and
    # both plan views; the side views use the opposite handedness.
    right,up=map(np.array,orientations[view]);depth=np.cross(right,up)
    if view in ("front", "rear", "top", "bottom"):
        depth=-depth
    projection=np.array([right,up,depth])
    normal=np.cross(mesh[:,1]-mesh[:,0],mesh[:,2]-mesh[:,0]);normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-9)
    lighting=.48+.45*np.abs(normal@np.array([.3,-.8,.5]));rgb=np.clip(rgb*lighting[:,None],0,255)
    # Project opaque geometry onto the ground along a fixed directional light.
    if view in ("front","rear"):
        shadow=mesh[opacity==1].copy(); ground=mesh[:,:,1].max()+1
        delta=ground-shadow[:,:,1]
        shadow[:,:,0]+=.3*delta;shadow[:,:,2]+=.2*delta;shadow[:,:,1]=ground
        mesh=np.concatenate((shadow,mesh));rgb=np.concatenate((np.tile([220,220,223],(len(shadow),1)),rgb));opacity=np.concatenate((np.ones(len(shadow)),opacity))
    projected=mesh@projection.T
    low,high=projected[:,:,:2].min(axis=(0,1)),projected[:,:,:2].max(axis=(0,1))
    scale=min(size[0]*.88/max(1,high[0]-low[0]),size[1]*.84/max(1,high[1]-low[1]))
    points=(projected[:,:,:2]-(low+high)/2)*scale
    points[:,:,0]+=size[0]/2;points[:,:,1]=size[1]/2-points[:,:,1]
    # Blend transparent faces from far to near against the opaque depth buffer.
    order=np.argsort(-projected[:,:,2].mean(axis=1))
    image=Image.fromarray(raster(points[order],projected[order,:,2],rgb[order],opacity[order],size[0],size[1]))
    image.save(output,"PNG")
