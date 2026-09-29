#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发射台日更 · 一键跑
顺序：网络预检 → 拉日度 → 读销毁 → 拉估值 → 拉Arc → 出看板 → 打包（Claude 侧）
      仓库里加 --site：出看板 → 拉宏观 → 写日志 → 出网站
  拉日度失败 = 整期作废（没有手续费就没有看板）；其余步骤失败不拦截，看板上会标出缺哪块。
  ⚠️ 读销毁必须排在拉估值之前，否则 PONS 估值滞后一天（旧流程实测踩过）。

用法：
  python3 跑日更.py                             # 日常
  python3 跑日更.py --rebuild-from 2026-08-23   # 同时重算这一天以来的 PONS 逐日销毁
  python3 跑日更.py --site                      # GitHub 仓库里用：再拉宏观、写解读日志、生成 site/ 静态网站
  目录里没有的步骤脚本会自动跳过（仓库里没有 打包.py，Claude 工具目录里没有 出网站.py）。
退出码：0 正常；2 网络被拦截；3 拉日度失败；4 出看板失败；5 出网站失败
"""
import sys, subprocess, time, os
from common import BASE, preflight

PY = sys.executable


def step(name, args=()):
    if not os.path.exists(os.path.join(BASE, name)):
        print(f"── {name} 不在本目录，跳过\n")
        return True
    t = time.time()
    r = subprocess.run([PY, os.path.join(BASE, name), *args], cwd=BASE)
    print(f"── {name} {'完成' if r.returncode == 0 else '失败'}（{time.time() - t:.0f} 秒）\n")
    return r.returncode == 0


def main():
    print("── 网络预检")
    blocked = preflight()
    if "api.llama.fi" in blocked:
        print("\n⛔ DefiLlama 被网络策略拦截，今天出不了稿。需要在网络白名单放行：", "、".join(blocked))
        sys.exit(2)
    if blocked:
        print("⚠️ 部分数据源被拦截，相关板块会缺数：", "、".join(blocked))
    print()
    if not step("拉日度.py"):
        sys.exit(3)
    extra = []
    if "--rebuild-from" in sys.argv:
        extra = ["--rebuild-from", sys.argv[sys.argv.index("--rebuild-from") + 1]]
    step("读销毁.py", extra)
    step("拉估值.py")
    step("拉Arc.py")
    if not step("出看板.py"):
        sys.exit(4)
    if "--site" in sys.argv:
        step("拉宏观.py")      # 宏观四层 + 板块快照；单个数据源挂了只影响对应指标，不拦截
        step("写日志.py")      # 每日解读日志（冻结）+ 周 / 月复盘
        if not step("出网站.py"):
            sys.exit(5)
    else:
        step("打包.py")      # 刷新 输出/发布/（台账 + 工具包），随看板一起发布到 Artifact


if __name__ == "__main__":
    main()
