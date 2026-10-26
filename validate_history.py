#!/usr/bin/env python3
"""发布前校验：工作文件或待推送提交必须保留远端已发布事件的完整前缀。"""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

# 门禁运行在发布仓库；包括 Git 钩子入口在内，不能生成随后被 git add -A 收入的缓存文件。
sys.dont_write_bytecode = True

from changelog_utils import assert_history_unchanged

ROOT = Path(__file__).resolve().parent
ZERO = "0" * 40


def git(*args):
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, encoding="utf-8", errors="strict"
    )
    if result.returncode:
        # 不回显 Git stderr，避免远端 URL 中的凭据进入日志。
        raise ValueError("Git 基线读取失败；请先 fetch 已发布分支，禁止跳过校验")
    return result.stdout.strip()


def commit(ref):
    return git("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON 存在重复字段：{key}")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError(f"JSON 含非法数值：{value}")


def parse(text):
    return json.loads(text, object_pairs_hook=unique_object, parse_constant=invalid_constant)


def validate(base_ref, candidate_ref=None):
    base = commit(base_ref)
    published = parse(git("show", f"{base}:changelog.json"))
    if candidate_ref:
        candidate = commit(candidate_ref)
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", base, candidate], cwd=ROOT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ).returncode:
            raise ValueError("待发布提交必须继承已发布基线，禁止重写分支历史")
        document = parse(git("show", f"{candidate}:changelog.json"))
    else:
        document = parse((ROOT / "changelog.json").read_text(encoding="utf-8"))
    assert_history_unchanged(published, document)
    print(f"PASS 历史 {len(published['events'])} 条保持不变；追加 {len(document['events']) - len(published['events'])} 条")


def pre_push(lines):
    for line in lines:
        fields = line.split()
        if len(fields) != 4:
            raise ValueError("pre-push 输入格式无效")
        _, local_sha, remote_ref, remote_sha = fields
        if remote_ref != "refs/heads/main":
            continue
        if not all(re.fullmatch(r"[0-9a-f]{40}", sha) for sha in (local_sha, remote_sha)):
            raise ValueError("pre-push 提交 ID 无效")
        if local_sha == ZERO or remote_sha == ZERO:
            raise ValueError("禁止删除或无历史基线地重建 main")
        # 使用 Git 实际要推送的对象与远端当前对象，工作区和暂存区不能替代它们。
        validate(remote_sha, local_sha)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", help="独立的已发布基线；预检先 git fetch origin main，再用 origin/main")
    parser.add_argument("--candidate-ref", help="待发布提交；省略时检查工作区 changelog.json")
    parser.add_argument("--pre-push", action="store_true", help="Git pre-push 钩子，从 stdin 读取真实推送对象")
    args = parser.parse_args()
    if args.pre_push and (args.base_ref or args.candidate_ref):
        parser.error("--pre-push 不能与 ref 参数混用")
    if not args.pre_push and not args.base_ref:
        parser.error("必须指定已发布基线，禁止只检查候选文件自身")
    try:
        if args.pre_push:
            pre_push(sys.stdin)
        else:
            validate(args.base_ref, args.candidate_ref)
        return 0
    except (AssertionError, ValueError, KeyError, TypeError, OSError) as error:
        print(f"BLOCKED {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
