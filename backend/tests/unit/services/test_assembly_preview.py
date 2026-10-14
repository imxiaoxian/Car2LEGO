import numpy as np

from app.services.assembly_preview import rasterize_triangles


def test_overlapping_faces_use_pixel_depth_instead_of_centroid_depth():
    triangle = [[0, 0], [10, 0], [0, 10]]
    points = np.array([triangle, triangle], dtype=float)
    depths = np.array([[0, 10, 0], [4, 4, 4]], dtype=float)
    colors = np.array([[255, 0, 0], [0, 0, 255]], dtype=np.uint8)
    for order in ([0, 1], [1, 0]):
        image = rasterize_triangles(points[order], depths[order], colors[order], (10, 10))
        assert image.getpixel((1, 1)) == (255, 0, 0)
        assert image.getpixel((8, 0)) == (0, 0, 255)
        assert image.getpixel((9, 9)) == (245, 245, 247)
