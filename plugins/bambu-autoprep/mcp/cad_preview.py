"""Orthographic CAD rendering with per-pixel depth, independent of OpenGL.

Every visible triangle participates. A painter's face ordering cannot correctly
resolve overlapping concave/hollow parts; a depth buffer can. Rendering changes
neither geometry nor its orientation in the printable files.
"""
import math

import numpy as np
from PIL import Image, ImageColor


def render_view(mesh, path, azimuth=-65, elevation=26, size=900,
                background='#F7F9F6', colour='#61AD99'):
    if not 64 <= size <= 1600:
        raise ValueError('Preview size must be between 64 and 1600 pixels')
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces)
    if not len(faces) or not np.isfinite(vertices).all():
        raise ValueError('Preview requires finite nonempty geometry')
    az, el = math.radians(azimuth), math.radians(elevation)
    toward_eye = np.array([math.cos(el)*math.cos(az), math.cos(el)*math.sin(az), math.sin(el)])
    right = np.array([-math.sin(az), math.cos(az), 0.])
    up = np.cross(toward_eye, right)
    projected = (vertices - vertices.mean(axis=0)) @ np.column_stack((right, up, toward_eye))
    # Supersampling antialiases silhouettes, without omitting tiny triangles.
    pixels = size * 2
    low, high = projected[:, :2].min(axis=0), projected[:, :2].max(axis=0)
    scale = .9 * (pixels-1) / max(float(np.max(high-low)), 1e-12)
    projected[:, :2] = (projected[:, :2] - (low+high)/2) * scale + (pixels-1)/2
    projected[:, 1] = pixels-1-projected[:, 1]
    depth = np.full((pixels, pixels), -np.inf, dtype=np.float64)
    raster = np.empty((pixels, pixels, 3), dtype=np.uint8)
    raster[:] = ImageColor.getrgb(background)
    base = np.array(ImageColor.getrgb(colour), dtype=float)
    # Fixed soft key light gives flat faces and curved CAD facets clear form.
    light = -.35*right + .65*up + .68*toward_eye
    light /= np.linalg.norm(light)
    normals = np.asarray(mesh.face_normals)
    facing = normals @ toward_eye
    shades = .47 + .53*np.maximum(0., normals @ light)
    colours = np.clip(base[None, :] * shades[:, None], 0, 255).astype(np.uint8)
    for face_index in np.flatnonzero(facing > 1e-10):
        triangle = projected[faces[face_index]]
        x0, y0, z0 = triangle[0]
        x1, y1, z1 = triangle[1]
        x2, y2, z2 = triangle[2]
        denom = (y1-y2)*(x0-x2) + (x2-x1)*(y0-y2)
        if abs(denom) < 1e-12:
            continue
        left, top = np.maximum(0, np.floor(triangle[:, :2].min(axis=0))).astype(int)
        right_edge, bottom = np.minimum(pixels-1, np.ceil(triangle[:, :2].max(axis=0))).astype(int)
        xs = np.arange(left, right_edge+1)[None, :] + .5
        # Keep temporary barycentric arrays bounded even for broad flat faces.
        for row in range(top, bottom+1, 128):
            stop = min(row+128, bottom+1)
            ys = np.arange(row, stop)[:, None] + .5
            a = ((y1-y2)*(xs-x2) + (x2-x1)*(ys-y2)) / denom
            b = ((y2-y0)*(xs-x2) + (x0-x2)*(ys-y2)) / denom
            d = 1-a-b
            z = a*z0 + b*z1 + d*z2
            previous = depth[row:stop, left:right_edge+1]
            visible = (a >= -1e-9) & (b >= -1e-9) & (d >= -1e-9) & (z > previous)
            previous[visible] = z[visible]
            raster[row:stop, left:right_edge+1][visible] = colours[face_index]
    Image.fromarray(raster).resize((size, size), Image.Resampling.LANCZOS).save(path)
