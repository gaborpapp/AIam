from skeleton import process_bvhfile
from camera import Camera

class SvgExporter:
    def __init__(self, bvh_filename, camera_x, camera_y, camera_z):
        self._skeleton = process_bvhfile(bvh_filename)
        self._camera = Camera(camera_x, camera_y, camera_z, cfx=20, ppdist=30)
        self._skelscreenedges = self._skeleton.make_skelscreenedges()
        self._floor_y = None

    def export_frame(self, svg_file, t, width, height,
                     opacity=1, x=0, y=0,
                     constrain_floor=False, auto_crop=False, stroke_width=1):
        self._skeleton.populate_skelscreenedges(self._skelscreenedges, t)

        if constrain_floor:
            frame_bottom_y = min([
                    min(screenedge.sv1.tr[1], screenedge.sv2.tr[1])
                    for screenedge in self._skelscreenedges])
            if self._floor_y is None:
                self._floor_y = frame_bottom_y
            y_offset = self._floor_y - frame_bottom_y

            for screenedge in self._skelscreenedges:
                screenedge.sv1.tr[1] += y_offset
                screenedge.sv2.tr[1] += y_offset

        screen_vertices = []
        for screenedge in self._skelscreenedges:
            screenedge.worldtocam(self._camera)
            screenedge.camtoscreen(self._camera, 1., 1.)
            sv1 = (screenedge.sv1.screenx, screenedge.sv1.screeny)
            sv2 = (screenedge.sv2.screenx, screenedge.sv2.screeny)
            screen_vertices.append((sv1, sv2))

        if auto_crop:
            screen_vertices = self._auto_crop(screen_vertices)

        for sv1, sv2 in screen_vertices:
            sv1x, sv1y = sv1
            sv2x, sv2y = sv2
            svg_file.write('<line x1="%s" y1="%s" x2="%s" y2="%s" style="stroke:black;fill:none;stroke-width:%f;stroke-opacity:%f" />\n' % (
                sv1x * width + x,
                sv1y * height + y,
                sv2x * width + x,
                sv2y * height + y,
                stroke_width,
                opacity))

    def _auto_crop(self, vertices):
        min_x = min([min(v1[0], v2[0]) for v1, v2 in vertices])
        max_x = max([max(v1[0], v2[0]) for v1, v2 in vertices])
        min_y = min([min(v1[1], v2[1]) for v1, v2 in vertices])
        max_y = max([max(v1[1], v2[1]) for v1, v2 in vertices])
        range_x = max_x - min_x
        range_y = max_y - min_y
        range_max = max(range_x, range_y)
        if range_max == 0:
            scale = 1
            print("WARNING: range_max=0 (camera too near object?)")
        else:
            scale = 1. / range_max
        translate_x = .5 - range_x * scale / 2
        translate_y = .5 - range_y * scale / 2
        return [
            ((scale * (v1[0] - min_x) + translate_x, scale * (v1[1] - min_y) + translate_y),
             (scale * (v2[0] - min_x) + translate_x, scale * (v2[1] - min_y) + translate_y))
            for v1, v2 in vertices]
