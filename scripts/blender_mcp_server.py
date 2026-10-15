"""Launch the pinned MCP server with a socket budget matching the host."""
import os
import socket
from types import SimpleNamespace


def configure_socket_timeout(server, timeout):
    class BlenderSocket(socket.socket):
        def settimeout(self, value):
            # The pinned server resets this socket to 180 seconds before every read.
            super().settimeout(timeout)

    server.socket = SimpleNamespace(socket=BlenderSocket, timeout=socket.timeout,
                                   AF_INET=socket.AF_INET, SOCK_STREAM=socket.SOCK_STREAM)


if __name__ == "__main__":
    from blender_mcp import server

    configure_socket_timeout(server, float(os.environ["CAR2LEGO_MCP_TIMEOUT"]))
    server.main()
