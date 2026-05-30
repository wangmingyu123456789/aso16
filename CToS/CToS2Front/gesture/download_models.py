#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CToS 手势识别 - MediaPipe 模型文件下载脚本

MediaPipe v0.10+ 需要从 Google Storage 下载 .task 模型文件。
本脚本自动下载 hand_landmarker.task 到 models/ 目录。

用法:
    python download_models.py          # 下载模型
    python download_models.py --force  # 强制重新下载
"""
import os
import sys
import urllib.request
import hashlib

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

# 模型清单: (文件名, URL, SHA256 校验和, 说明)
MODELS = [
    {
        "name": "hand_landmarker.task",
        "url": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task",
        "sha256": None,  # 可选校验
        "desc": "手部关键点检测模型 (21个关键点)",
    },
]


def sha256_file(path: str) -> str:
    """计算文件 SHA256"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: str) -> None:
    """带进度显示的下载"""
    def report(block_num: int, block_size: int, total_size: int):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(100, downloaded * 100 // total_size)
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            sys.stdout.write(f"\r   {bar} {pct}% ({downloaded//1024}KB/{total_size//1024}KB)")
            sys.stdout.flush()

    print(f"   下载中...")
    urllib.request.urlretrieve(url, dest, reporthook=report)
    print()


def main():
    os.makedirs(MODELS_DIR, exist_ok=True)

    force = "--force" in sys.argv

    all_ok = True
    for model in MODELS:
        dest = os.path.join(MODELS_DIR, model["name"])
        exists = os.path.isfile(dest)

        if exists and not force:
            print(f"✓ {model['name']} 已存在，跳过 (使用 --force 强制重新下载)")
            continue

        print(f"\n下载 {model['name']} ...")
        print(f"  来源: {model['url']}")
        print(f"  说明: {model['desc']}")

        try:
            download(model["url"], dest)

            # 校验
            if model["sha256"]:
                hs = sha256_file(dest)
                if hs != model["sha256"]:
                    os.remove(dest)
                    print(f"✗ SHA256 校验失败 (期望 {model['sha256']}，实际 {hs})")
                    all_ok = False
                    continue

            file_size = os.path.getsize(dest)
            print(f"✓ 完成: {model['name']} ({file_size//1024}KB)")

        except Exception as e:
            print(f"✗ 下载失败: {e}")
            all_ok = False

    # 验证
    print("\n" + "─" * 48)
    if all_ok:
        required = [m["name"] for m in MODELS]
        missing = [f for f in required if not os.path.isfile(os.path.join(MODELS_DIR, f))]
        if missing:
            print(f"⚠ 以下模型文件缺失: {', '.join(missing)}")
            print("  请重新运行: python download_models.py")
            sys.exit(1)
        else:
            print("✓ 所有模型文件就绪!")
            print(f"  目录: {MODELS_DIR}")
    else:
        print("⚠ 部分模型下载失败，请检查网络后重试")
        sys.exit(1)


if __name__ == "__main__":
    main()