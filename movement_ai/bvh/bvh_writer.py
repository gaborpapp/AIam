class BvhWriter:
    def __init__(self, hierarchy, frame_time):
        self._root_joint_definition = hierarchy.get_root_joint_definition()
        self._frame_time = frame_time
        self._frames = []

    def add_pose_as_frame(self, pose):
        frame = self._pose_to_bvh_frame(pose)
        self.add_frame(frame)

    def add_frame(self, frame):
        self._frames.append(frame)

    def write(self, output_path):
        self._output = open(output_path, "w")
        self._write_header()
        self._write("MOTION\n")
        self._write("Frames: %d\n" % len(self._frames))
        self._write("Frame Time: %f\n" % self._frame_time)
        for frame in self._frames:
            self._write_frame(frame)
        self._output.close()

    def _write_header(self):
        self._write("HIERARCHY\n")
        self._indent = 0
        self._write_joint_header(self._root_joint_definition, is_root=True)
        self._write("\n")
    
    def _write_joint_header(self, joint_definition, is_root=False):
        self._write_indent()
        if is_root:
            self._write("ROOT %s" % joint_definition.name)
        else:
            if joint_definition.is_end:
                self._write("End Site")
            else:
                self._write("JOINT %s" % joint_definition.name)
        self._write("\n")
        self._write_indent()
        self._write("{\n")
        self._indent += 1

        self._write_indent()
        self._write("OFFSET\t%.4f\t%.4f\t%.4f\n" % (
                joint_definition.offset[0],
                joint_definition.offset[1],
                joint_definition.offset[2]))

        if len(joint_definition.channels) > 0:
            self._write_indent()
            self._write("CHANNELS %d %s\n" % (
                    len(joint_definition.channels),
                    " ".join(joint_definition.channels)))

        for child_definition in joint_definition.child_definitions:
            self._write_joint_header(child_definition)

        self._indent -= 1
        self._write_indent()
        self._write("}\n")

    def _write_indent(self):
        self._write("\t" * self._indent)

    def _write_frame(self, frame):
        for value in frame:
            self._write("%s " % value)
        self._write("\n")

    def _write(self, string):
        self._output.write(string)

    def _pose_to_bvh_frame(self, pose):
        return self._joint_to_bvh_frame(pose.get_root_joint())

    def _joint_to_bvh_frame(self, joint):
        result = []
        for channel in joint.definition.channels:
            result.append(self._bvh_channel_data(joint, channel))
        for child in joint.children:
            result += self._joint_to_bvh_frame(child)
        return result

    def _bvh_channel_data(self, joint, channel):
        return getattr(joint, channel)()
