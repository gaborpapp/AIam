from connectivity.simple_osc_sender import OscSender

class AvatarOscSender:
    def __init__(self, host, port):
        self._host = host
        self._port = port
        self.reset()

    def reset(self):
        self._osc_sender = OscSender(self._host, self._port)
        self._frame_index = 0

    def get_status(self):
        return self._osc_sender.get_status()
            
class AvatarOscBvhSender(AvatarOscSender):
    def __init__(self, *args, **kwargs):
        AvatarOscSender.__init__(self, *args, **kwargs)

    def reset(self):
        AvatarOscSender.reset(self)
        self._sent_joint_ids = False
        
    def send_frame(self, avatar_index, pose, entity):
        self._ensure_sent_joint_ids(entity)
        self._osc_sender.send("/avatar_begin", avatar_index, self._frame_index)
        self._send_output_bvh_recurse(pose.get_root_joint())
        self._osc_sender.send("/avatar_end")
        self._frame_index += 1

    def _ensure_sent_joint_ids(self, entity):
        if not self._sent_joint_ids:
            self._send_joint_ids(entity)
            self._sent_joint_ids = True
            
    def _send_joint_ids(self, entity):
        self._send_output_joint_id_recurse(entity.pose.get_root_joint())

    def _send_output_joint_id(self, joint):
        self._osc_sender.send(
            "/id", joint.definition.name, joint.definition.index)

    def _send_output_bvh_recurse(self, joint):
        if not joint.definition.has_parent:
            self._send_output_joint_translation(joint)
        if joint.definition.has_rotation:
            self._send_output_joint_orientation(joint)
        for child in joint.children:
            self._send_output_bvh_recurse(child)

    def _send_output_joint_id_recurse(self, joint):
        self._send_output_joint_id(joint)
        for child in joint.children:
            self._send_output_joint_id_recurse(child)

    def _send_output_joint_translation(self, joint):
        self._osc_sender.send(
            "/translation", self._frame_index, joint.definition.index,
            joint.worldpos[0], joint.worldpos[1], joint.worldpos[2])

    def _send_output_joint_orientation(self, joint):
        self._osc_sender.send(
            "/orientation", self._frame_index, joint.definition.index,
            *joint.angles)
