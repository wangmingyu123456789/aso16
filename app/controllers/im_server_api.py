import json
import tornado.web
from app.controllers.base import BaseHandler
from app.models.im import IMRepository
from app.models.im_server import ServerRegistry, UserAssigner


class AssignNodeHandler(BaseHandler):
    """为用户分配最合适的IM服务器节点"""
    @tornado.web.authenticated
    def get(self):
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        if not user_id:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 401, "msg": "用户未登录"})
            return

        # 获取当前服务器节点信息（从请求中）
        preferred_node = self.get_argument("preferred_node", "")

        node_id = UserAssigner.assign(user_id, preferred_node if preferred_node else None)
        if not node_id:
            # 没有在线节点，返回主服务器地址
            self.set_header("Content-Type", "application/json")
            self.write({
                "code": 0,
                "data": {
                    "node_id": "main",
                    "ws_url": "ws://{}/im/ws".format(self.request.host),
                    "is_main": True
                }
            })
            return

        node = ServerRegistry.get_node_by_id(node_id)
        if not node:
            self.set_header("Content-Type", "application/json")
            self.write({
                "code": 0,
                "data": {
                    "node_id": "main",
                    "ws_url": "ws://{}/im/ws".format(self.request.host),
                    "is_main": True
                }
            })
            return

        ws_url = "ws://{}:{}/im/ws".format(node["host"], node["public_port"])
        is_main = False
        internal_port = node["internal_port"]

        self.set_header("Content-Type", "application/json")
        self.write({
            "code": 0,
            "data": {
                "node_id": node_id,
                "ws_url": ws_url,
                "host": node["host"],
                "public_port": node["public_port"],
                "internal_port": internal_port,
                "connection_count": node["connection_count"],
                "load_score": node["load_score"],
                "is_main": is_main
            }
        })


class NodeStatusHandler(BaseHandler):
    """获取所有IM服务器节点状态"""
    @tornado.web.authenticated
    def get(self):
        nodes = ServerRegistry.get_all_nodes()
        assignments = UserAssigner.get_all_assignments()

        self.set_header("Content-Type", "application/json")
        self.write({
            "code": 0,
            "data": {
                "nodes": nodes,
                "assignments": assignments
            }
        })
