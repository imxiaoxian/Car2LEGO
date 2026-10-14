import numpy as np


def render(mesh, output):
    from .lego import color_visual
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    figure = plt.figure(figsize=(10, 7), dpi=130)
    axis = figure.add_subplot(111, projection="3d")
    colors = color_visual(mesh).face_colors.astype(float) / 255
    light = np.array([0.4, -0.5, 0.8]); light /= np.linalg.norm(light)
    colors[:, :3] *= (0.42 + 0.58 * np.maximum(mesh.face_normals @ light, 0))[:, None]
    axis.add_collection3d(Poly3DCollection(mesh.triangles,
        facecolors=colors, edgecolors="none", rasterized=True))
    bounds = mesh.bounds
    center = bounds.mean(axis=0)
    radius = max(mesh.extents) * 0.56
    for setter, index in ((axis.set_xlim, 0), (axis.set_ylim, 1), (axis.set_zlim, 2)):
        setter(center[index] - radius, center[index] + radius)
    axis.set_box_aspect((1, 1, 1))
    axis.view_init(elev=23, azim=-55)
    axis.set_axis_off()
    figure.tight_layout(pad=0)
    figure.savefig(output, facecolor="white", bbox_inches="tight", pad_inches=0.05)
    plt.close(figure)
