import argparse
import os
import sys

from . import server as srv
from .config import Config, VERSION, default_share_dir, valid_token


def _port(value):
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("端口必须是整数")
    if port < 0 or port > 65535:
        raise argparse.ArgumentTypeError("端口必须在 0-65535 之间")
    return port


def build_parser():
    parser = argparse.ArgumentParser(
        prog="lanist",
        description="LANist - 局域网传文件：主机开一个网页，同一局域网里的设备用浏览器存取文件。",
    )
    parser.add_argument(
        "--share",
        metavar="目录",
        help="共享目录，默认 {}".format(default_share_dir()),
    )
    parser.add_argument(
        "--port",
        type=_port,
        default=0,
        metavar="端口",
        help="监听端口，默认从 8000 起自动挑一个空闲端口",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        metavar="地址",
        help="监听地址，默认 0.0.0.0（所有网卡）",
    )
    parser.add_argument("--token", metavar="口令", help="指定访问口令，并保存到配置")
    parser.add_argument(
        "--new-token", action="store_true", help="重新生成一个随机口令"
    )
    parser.add_argument(
        "--no-gui", action="store_true", help="只在终端里跑，不打开窗口"
    )
    parser.add_argument(
        "--version", action="version", version="LANist {}".format(VERSION)
    )
    return parser


def run_headless(share, token, host, port):
    try:
        server, actual_port = srv.create_server(
            share=share, token=token, host=host, port=port
        )
    except Exception as e:
        print("启动失败：{}".format(e), file=sys.stderr)
        return 1

    if host in ("127.0.0.1", "localhost"):
        urls = ["http://127.0.0.1:{}/{}/".format(actual_port, token)]
    else:
        urls = srv.urls_for(actual_port, token)
    print("LANist {}".format(VERSION))
    print("共享目录：{}".format(share))
    print("访问口令：{}".format(token))
    if urls:
        for url in urls:
            print("打开：{}".format(url))
    else:
        print("没有找到局域网 IP；服务仍在 {}:{} 监听。".format(host, actual_port))
    print("同一局域网内用浏览器打开上面的地址；Ctrl+C 停止。", flush=True)

    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    print("已停止。")
    return 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    cfg = Config()
    if args.new_token:
        cfg.reset_token()
    if args.token:
        if not valid_token(args.token):
            parser.error(
                "--token 只能包含字母、数字、点、下划线、波浪线和短横线，长度 3-64。"
            )
        cfg.set_token(args.token)
    token = args.token or cfg.ensure_token()

    share = os.path.abspath(os.path.expanduser(args.share or default_share_dir()))

    if args.no_gui or os.name != "nt":
        if not args.no_gui and os.name != "nt":
            print("窗口界面目前只支持 Windows，已改为无窗口模式。", file=sys.stderr)
        return run_headless(share, token, args.host, args.port)

    from . import gui

    return gui.run(share=share, token=token, port=args.port, host=args.host)
